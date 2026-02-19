import os
import asyncio
import logging
import sys
from pathlib import Path
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile
import yt_dlp
import imageio_ffmpeg
import subprocess

# ────────────────────────────────────────────────
#  Конфигурация логирования
# ────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────
#  Пути и константы
# ────────────────────────────────────────────────

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
MUSIC_DIR = Path("music")
MUSIC_DIR.mkdir(exist_ok=True)

MAX_TELEGRAM_SIZE = 50 * 1024 * 1024      # 50 MB
TARGET_SIZE_AFTER_COMPRESS = 45 * 1024 * 1024

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("BOT_TOKEN environment variable is not set")
    sys.exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Кэш file_id (query → file_id)
CACHE = {}

# ────────────────────────────────────────────────
#  Вспомогательные функции
# ────────────────────────────────────────────────

def is_url(text: str) -> bool:
    text = text.strip()
    return text.startswith(('http://', 'https://', 'www.'))


def extract_artist_and_title(info: dict) -> tuple[str, str]:
    title = info.get('title', 'Unknown Title').strip()
    artist = (
        info.get('artist') or
        info.get('uploader') or
        info.get('channel') or
        'Unknown Artist'
    ).strip()

    # Пытаемся распарсить "Artist - Title"
    if artist == 'Unknown Artist' and ' - ' in title:
        parts = title.split(' - ', 1)
        if len(parts) == 2:
            artist, title = parts[0].strip(), parts[1].strip()

    return artist, title


def get_duration(file_path: str | Path) -> float | None:
    file_path = str(file_path)
    ffprobe = str(Path(FFMPEG_PATH).parent / ('ffprobe.exe' if sys.platform == 'win32' else 'ffprobe'))

    if not os.path.isfile(ffprobe):
        logger.warning("ffprobe not found → duration detection disabled")
        return None

    try:
        result = subprocess.run(
            [ffprobe, '-v', 'quiet', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', file_path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
        return None
    except Exception as e:
        logger.warning(f"ffprobe failed: {e}")
        return None


def compress_audio(input_path: str | Path, target_size_bytes: int = TARGET_SIZE_AFTER_COMPRESS) -> str | None:
    input_path = Path(input_path)
    if not input_path.is_file():
        return None

    size_now = input_path.stat().st_size
    if size_now <= target_size_bytes:
        return str(input_path)

    duration = get_duration(input_path)
    if not duration or duration < 1:
        logger.warning("Cannot compress: duration unknown")
        return None

    target_bitrate = max(48, min(192, int(target_size_bytes * 8 / duration / 1000)))
    output_path = input_path.with_suffix('.compressed.mp3')

    try:
        subprocess.run([
            FFMPEG_PATH, '-y', '-i', str(input_path),
            '-b:a', f'{target_bitrate}k',
            '-ac', '2', '-ar', '44100',
            str(output_path)
        ], check=True, capture_output=True)

        new_size = output_path.stat().st_size
        if new_size > target_size_bytes + 1_000_000:  # допуск ~1MB
            logger.warning(f"Compression result still too big: {new_size / 1024**2:.1f} MB")
            output_path.unlink(missing_ok=True)
            return None

        input_path.unlink(missing_ok=True)
        output_path.rename(input_path)
        logger.info(f"Compressed → {input_path.name} ({new_size / 1024**2:.1f} MB, {target_bitrate}kbps)")
        return str(input_path)

    except Exception as e:
        logger.error(f"Compression failed: {e}")
        output_path.unlink(missing_ok=True)
        return None


def download_audio(query: str) -> tuple[Path | None, dict | None]:
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(MUSIC_DIR / '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'writethumbnail': True,
        'ffmpeg_location': '/usr/bin/',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',   # будет перезаписано при сжатии
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            if is_url(query):
                info = ydl.extract_info(query, download=True)
            else:
                info = ydl.extract_info(f"ytsearch1:{query}", download=True)['entries'][0]

            # yt-dlp после постпроцессинга меняет расширение
            expected_path = Path(ydl.prepare_filename(info))
            mp3_path = expected_path.with_suffix('.mp3')

            if mp3_path.is_file():
                return mp3_path, info

            # fallback — ищем файл с тем же id
            for file in MUSIC_DIR.glob(f"{info['id']}*"):
                if file.suffix in ('.mp3', '.m4a', '.webm', '.opus'):
                    return file, info

            logger.error("Downloaded file not found after post-processing")
            return None, None

        except Exception as e:
            logger.error(f"yt-dlp error for '{query}': {e}", exc_info=True)
            return None, None


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("🎵 Отправь название трека или ссылку (YouTube, SoundCloud и др.)")


@dp.message()
async def handle_music_request(message: Message):
    query = message.text.strip()
    if not query:
        return

    status = None  # Инициализация для безопасности
    thumb_path = None  # Инициализация для безопасности
    file_path = None   # Добавляем для безопасности в finally

    if query in CACHE:
        try:
            if status:
                await status.edit_text("📤 Отправляю из кэша...")
            await message.answer_audio(CACHE[query])
            await message.delete()
            if status:
                await status.delete()
            return
        except Exception:
            logger.warning("Cached file_id is invalid → will re-download")
            del CACHE[query]

    status = await message.answer("🔎 Поиск трека...")

    try:
        # Шаг: Поиск и скачивание
        await status.edit_text("📥 Скачивание аудио...")
        file_path, info = await asyncio.to_thread(download_audio, query)
        if not file_path or not info:
            await status.edit_text("😔 Не удалось найти или скачать трек")
            return  # Не удаляем статус в случае ошибки

        # Шаг: Проверка размера
        await status.edit_text("🔍 Проверка размера файла...")
        size = file_path.stat().st_size

        if size > MAX_TELEGRAM_SIZE:
            await status.edit_text("📦 Файл слишком большой — пытаюсь сжать...")
            compressed = compress_audio(file_path, target_size_bytes=MAX_TELEGRAM_SIZE - 5 * 1024 * 1024)  # Цель <45MB для запаса
            if compressed:
                file_path = Path(compressed)
                size = file_path.stat().st_size
            else:
                # Не удалось сжать — разбиваем на части
                await status.edit_text("❗ Сжатие не помогло — разбиваю на части...")
                parts = split_audio(file_path)  # Новая функция для разбиения (определить ниже)
                if not parts:
                    await status.edit_text("❌ Не удалось разбить файл. Попробуйте другой запрос.")
                    return  # Оставляем статус

                # Отправляем части
                await status.edit_text("📤 Отправляю части...")
                artist, title = extract_artist_and_title(info)
                for i, part_path in enumerate(parts, 1):
                    audio_part = FSInputFile(part_path, filename=f"{title} (Часть {i}).mp3")
                    await message.answer_audio(
                        audio=audio_part,
                        title=f"{title} (Часть {i})",
                        performer=artist,
                    )
                    part_path.unlink(missing_ok=True)  # Удаляем часть после отправки

                # Успех — удаляем запрос пользователя
                try:
                    await message.delete()
                except Exception:
                    pass

                await status.delete()  # Удаляем статус только при успехе
                return

        # Шаг: Поиск thumbnail
        await status.edit_text("🖼️ Поиск обложки...")
        for ext in ('.jpg', '.webp', '.png'):
            candidate = file_path.with_suffix(ext)
            if candidate.is_file():
                thumb_path = candidate
                break

        # Шаг: Отправка
        await status.edit_text("📤 Отправляю аудио...")
        artist, title = extract_artist_and_title(info)

        audio = FSInputFile(file_path, filename=f"{title}.mp3")
        thumb = FSInputFile(thumb_path) if thumb_path else None

        sent = await message.answer_audio(
            audio=audio,
            title=title,
            performer=artist,
            thumbnail=thumb,
            supports_streaming=True
        )

        CACHE[query] = sent.audio.file_id

        # Успех — удаляем запрос пользователя
        try:
            await message.delete()
        except Exception:
            pass

    except Exception as e:
        logger.exception("Critical error in download handler")
        if status:
            await status.edit_text("💥 Произошла ошибка при обработке. Попробуйте позже.")

        return  # Не удаляем статус в случае ошибки

    finally:
        # Уборка файлов (только если успех, но файлы чистим всегда)
        if file_path and file_path.is_file():
            file_path.unlink(missing_ok=True)
        if thumb_path and thumb_path.is_file():
            thumb_path.unlink(missing_ok=True)
        # Статус удаляем только в try (при успехе), здесь не трогаем

# Новая функция для разбиения аудио на части (добавьте в код)
def split_audio(input_path: Path, max_size_bytes: int = MAX_TELEGRAM_SIZE - 1 * 1024 * 1024) -> list[Path]:
    """Разбивает MP3 на части < max_size_bytes с помощью ffmpeg."""
    parts = []
    duration = get_duration(input_path)
    if not duration:
        logger.warning("Cannot split: duration unknown")
        return []

    file_size = input_path.stat().st_size
    if file_size <= max_size_bytes:
        return [input_path]  # Не нужно разбивать

    # Примерно вычисляем кол-во частей
    num_parts = int(file_size / max_size_bytes) + 1
    part_duration = duration / num_parts

    base_name = input_path.stem
    for i in range(num_parts):
        part_path = input_path.with_name(f"{base_name}_part{i+1}.mp3")
        start_time = i * part_duration
        end_time = min((i+1) * part_duration, duration)

        try:
            subprocess.run([
                FFMPEG_PATH, '-y', '-i', str(input_path),
                '-ss', str(start_time), '-t', str(end_time - start_time),
                '-c', 'copy',  # Копируем без перекодирования
                str(part_path)
            ], check=True, capture_output=True)

            if part_path.stat().st_size > max_size_bytes:
                logger.warning(f"Part {i+1} still too big — skipping")
                part_path.unlink(missing_ok=True)
                continue

            parts.append(part_path)
        except Exception as e:
            logger.error(f"Split failed for part {i+1}: {e}")
            if part_path.exists():
                part_path.unlink(missing_ok=True)

    input_path.unlink(missing_ok=True)  # Удаляем оригинал
    return parts

async def main():
    # Удаляем старый вебхук и пропускаем накопившиеся обновления
    await bot.delete_webhook(drop_pending_updates=True)
    
    logger.info("Бот успешно запущен → начинаем опрос (polling)")
    
    # Самый простой и рекомендуемый вариант для aiogram 3.x
    # allowed_updates больше не нужен — aiogram сам определяет нужные типы обновлений
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}", exc_info=True)




import os
import asyncio
import logging
import sys
import glob
import subprocess
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message
import yt_dlp

def is_url(text: str) -> bool:
    """Проверяет, является ли текст URL-ссылкой."""
    return text.startswith(('http://', 'https://', 'www.'))

def extract_artist_and_title(info: dict) -> tuple:
    """
    Извлекает исполнителя и название трека из информации yt-dlp.
    Возвращает кортеж (artist, title).
    """
    title = info.get('title', 'Unknown')
    artist = info.get('artist')
    
    # Если artist нет, пробуем uploader или channel
    if not artist:
        artist = info.get('uploader') or info.get('channel')
    
    # Если исполнителя всё ещё нет, пробуем извлечь из названия
    # Многие YouTube видео имеют формат "Artist - Song Name"
    if not artist and ' - ' in title:
        parts = title.split(' - ', 1)
        artist = parts[0].strip()
        title = parts[1].strip() if len(parts) > 1 else title
    
    return artist or 'Unknown Artist', title

def get_audio_duration(file_path: str) -> float:
    """Получает длительность аудио файла в секундах через ffprobe."""
    result = subprocess.run([
        'ffprobe', '-v', 'quiet', '-show_entries', 
        'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
        file_path
    ], capture_output=True, text=True)
    return float(result.stdout.strip())

def compress_audio(input_path: str, target_size_mb: int = 45) -> str:
    """Сжимает аудио файл до целевого размера через FFmpeg."""
    file_size_mb = os.path.getsize(input_path) / (1024 * 1024)
    
    if file_size_mb <= target_size_mb:
        return input_path
    
    # Вычисляем нужный битрейт для целевого размера
    duration = get_audio_duration(input_path)
    # Формула: target_bitrate (kbps) = (target_size_mb * 8 * 1024) / duration
    target_bitrate = int((target_size_mb * 8 * 1024) / duration)
    
    # Ограничиваем битрейт разумными значениями (минимум 64kbps, максимум 192kbps)
    target_bitrate = max(64, min(target_bitrate, 192))
    
    output_path = input_path.rsplit('.', 1)[0] + '_compressed.mp3'
    
    logging.info(f"Compressing audio: {file_size_mb:.2f}MB -> target {target_size_mb}MB, bitrate: {target_bitrate}kbps")
    
    subprocess.run([
        'ffmpeg', '-y', '-i', input_path,
        '-b:a', f'{target_bitrate}k',
        '-ac', '2',  # Стерео
        output_path
    ], check=True, capture_output=True)
    
    # Удаляем оригинал и переименовываем сжатый файл
    os.remove(input_path)
    os.rename(output_path, input_path)
    
    new_size_mb = os.path.getsize(input_path) / (1024 * 1024)
    logging.info(f"Compression complete: {new_size_mb:.2f}MB")
    
    return input_path

# Configure logging
logging.basicConfig(level=logging.INFO)

# Ensure the music directory exists
os.makedirs('music', exist_ok=True)

BOT_TOKEN = "8409897167:AAHC4RqLJHVb_qk-ouHmFu3gTuFeWfKtJss"
# os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    sys.exit("Error: BOT_TOKEN environment variable is not set.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# In-memory cache for file_ids
CACHE = {}

@dp.message(CommandStart())
async def start(message: Message):
    """Handler for the /start command."""
    await message.answer("🚀 ULTRA Music Bot готов! Отправь название или ссылку")

def download_video(query: str):
    """Synchronous function to download audio using yt-dlp."""
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'music/%(id)s.%(ext)s',
        'quiet': True,
        'writethumbnail': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            if is_url(query):
                # Прямая ссылка - извлекаем напрямую
                info = ydl.extract_info(query, download=True)
            else:
                # Поисковый запрос - ищем на YouTube
                info = ydl.extract_info(f"ytsearch:{query}", download=True)['entries'][0]
            # After post-processing, yt-dlp replaces the extension in the info dict
            # and prepare_filename will return the correct path.
            file_path = ydl.prepare_filename(info)
            return file_path, info
        except IndexError:
            logging.warning(f"yt-dlp found no results for query: {query}")
            return None, None
        except Exception as e:
            logging.error(f"yt-dlp download error for query '{query}': {e}")
            return None, None


@dp.message()
async def download_music(message: Message):
    """Handles music download requests."""
    query = message.text

    if query in CACHE:
        try:
            await message.answer_audio(CACHE[query])
            return
        except Exception as e:
            logging.warning(f"Could not send audio from cache: {e}. Re-downloading.")
            del CACHE[query]

    status_message = await message.answer("🔍 Поиск ULTRA...")

    loop = asyncio.get_running_loop()
    
    # Run the synchronous download function in a separate thread
    file_path, info = await loop.run_in_executor(
        None, download_video, query
    )

    if not file_path or not info:
        await status_message.edit_text("❌ Не удалось найти или скачать трек.")
        return

    # yt-dlp с пост-процессором FFmpegExtractAudio меняет расширение на mp3
    # prepare_filename может вернуть путь с оригинальным расширением
    if not os.path.exists(file_path):
        base_path = os.path.splitext(file_path)[0]
        mp3_path = base_path + '.mp3'
        if os.path.exists(mp3_path):
            file_path = mp3_path
        else:
            # Пробуем найти любой файл с тем же базовым именем
            pattern = base_path + '.*'
            matches = glob.glob(pattern)
            if matches:
                file_path = matches[0]
    
    if not os.path.exists(file_path):
        logging.error(f"File not found after download: {file_path}")
        await status_message.edit_text("❌ Файл не найден после загрузки.")
        return
    
    # Проверка лимита Telegram (50MB для ботов)
    file_size = os.path.getsize(file_path)
    if file_size > 50 * 1024 * 1024:
        logging.info(f"File too large ({file_size / (1024*1024):.2f}MB), compressing...")
        await status_message.edit_text("📦 Файл слишком большой, сжимаю...")
        
        try:
            file_path = compress_audio(file_path, target_size_mb=45)
            file_size = os.path.getsize(file_path)
            
            # Если после сжатия всё ещё больше 50MB - сжимаем сильнее
            if file_size > 50 * 1024 * 1024:
                logging.info(f"Still too large after first compression, compressing more...")
                file_path = compress_audio(file_path, target_size_mb=40)
                file_size = os.path.getsize(file_path)
                
            # Финальная проверка
            if file_size > 50 * 1024 * 1024:
                logging.error(f"File still too large after compression: {file_size} bytes")
                await status_message.edit_text("❌ Не удалось сжать файл до допустимого размера (лимит 50MB).")
                if os.path.exists(file_path):
                    os.remove(file_path)
                return
                
            await status_message.edit_text("✅ Сжатие завершено, отправляю...")
        except Exception as e:
            logging.error(f"Compression failed: {e}")
            await status_message.edit_text("❌ Ошибка при сжатии файла.")
            if os.path.exists(file_path):
                os.remove(file_path)
            return

    try:
        # Извлекаем исполнителя и название
        artist, track_title = extract_artist_and_title(info)
        
        # Найти thumbnail
        base_path = os.path.splitext(file_path)[0]
        thumbnail_path = None
        for ext in ['.jpg', '.webp', '.png']:
            potential_thumb = base_path + ext
            if os.path.exists(potential_thumb):
                thumbnail_path = potential_thumb
                break
        
        audio_file = types.FSInputFile(file_path, filename=f"{track_title}.mp3")
        thumbnail = types.FSInputFile(thumbnail_path) if thumbnail_path else None
        
        sent_message = await message.answer_audio(
            audio_file,
            title=track_title,
            performer=artist,
            thumbnail=thumbnail,
        )
        # Cache the file_id for future requests
        CACHE[query] = sent_message.audio.file_id
    except Exception as e:
        logging.error(f"Failed to send audio: {e}")
        await status_message.edit_text("❌ Произошла ошибка при отправке аудио.")
    finally:
        # Clean up the downloaded file and thumbnail
        if os.path.exists(file_path):
            os.remove(file_path)
        if thumbnail_path and os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
        await status_message.delete()


async def main():
    """Starts the bot."""
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


import os
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message
import yt_dlp

def is_url(text: str) -> bool:
    """Проверяет, является ли текст URL-ссылкой."""
    return text.startswith(('http://', 'https://', 'www.'))

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
            await message.answer_audio(CACHE[query], caption="⚡ Из кеша ULTRA")
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

    try:
        audio_file = types.FSInputFile(file_path, filename=info.get('title', 'audio.mp3'))
        sent_message = await message.answer_audio(
            audio_file,
            caption="🔥 ULTRA качество",
            title=info.get("title"),
        )
        # Cache the file_id for future requests
        CACHE[query] = sent_message.audio.file_id
    except Exception as e:
        logging.error(f"Failed to send audio: {e}")
        await status_message.edit_text("❌ Произошла ошибка при отправке аудио.")
    finally:
        # Clean up the downloaded file
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_message.delete()


async def main():
    """Starts the bot."""
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

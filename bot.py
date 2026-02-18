import asyncio
import logging
import os
import uuid
import json

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile

import yt_dlp

LAST = {}
# ========= CONFIG =========

BOT_TOKEN = os.getenv("BOT_TOKEN")

DOWNLOAD = "downloads"
CACHE_FILE = "cache.json"

os.makedirs(DOWNLOAD, exist_ok=True)

logging.basicConfig(level=logging.INFO)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ========= CACHE =========

if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        CACHE = json.load(f)
else:
    CACHE = {}

def save_cache():
    with open(CACHE_FILE, "w") as f:
        json.dump(CACHE, f)


# ========= START =========

@dp.message(CommandStart())
async def start(msg: types.Message):

    await msg.answer(
        "🎵 Отправь ссылку\n\n"
        "⚡ Быстро\n"
        "🖼 С обложкой\n"
        "🚀 Без ограничений"
    )


# ========= PROGRESS =========

async def progress_bar(status, percent):

   LAST = {}

async def progress_bar(status, percent):

    message_id = status.message_id

    percent_int = int(percent)

    if LAST.get(message_id) == percent_int:
        return

    LAST[message_id] = percent_int

    bars = percent_int // 10

    bar = "▓" * bars + "░" * (10 - bars)

    try:

        await status.edit_text(
            f"📥 Загрузка...\n\n"
            f"{bar} {percent_int}%"
        )

    except:
        pass


# ========= HANDLER =========

@dp.message()
@dp.message()
async def handler(msg: types.Message):
    unique = str(uuid.uuid4())

    audio_path = None
    thumb_path = None

    url = msg.text

    status = await msg.answer("🔍 Проверка...")

    # ✅ СОЗДАЕМ unique ЗДЕСЬ
    unique = str(uuid.uuid4())

    def hook(d):

        if d['status'] == 'downloading':

            percent = float(
                d['_percent_str']
                .replace('%', '')
                .strip()
            )

            asyncio.create_task(
                progress_bar(status, percent)
            )

    ydl_opts = {

        'format': 'bestaudio[ext=m4a]',

        'outtmpl': f'downloads/{unique}.%(ext)s',

        'progress_hooks': [hook],

        'writethumbnail': True,

        'convert_thumbnails': 'jpg',

        'quiet': True,

    }



    try:

        await status.edit_text("📥 Начинаю загрузку...")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(url, download=True)


        title = info.get("title", "Music")
        performer = info.get("uploader", "Unknown")

        audio_path = None
        thumb_path = None


        for f in os.listdir(DOWNLOAD):

            if f.startswith(unique) and f.endswith((".m4a",".webm")):

                audio_path = f"{DOWNLOAD}/{f}"

            if f.startswith(unique) and f.endswith(".jpg"):

                thumb_path = f"{DOWNLOAD}/{f}"


        await status.edit_text("📤 Отправляю...")


        audio = FSInputFile(audio_path)


        if thumb_path:

            thumb = FSInputFile(thumb_path)

            sent = await msg.answer_audio(

                audio=audio,
                title=title,
                performer=performer,
                thumbnail=thumb

            )

        else:

            sent = await msg.answer_audio(

                audio=audio,
                title=title,
                performer=performer

            )


        # ========= SAVE CACHE =========

        CACHE[url] = sent.audio.file_id

        save_cache()


        # ========= DELETE LINK =========

        await status.edit_text("🧹 Удаляю ссылку...")

        await asyncio.sleep(1)

        await msg.delete()

        await status.delete()


        # ========= CLEAN =========

        os.remove(audio_path)

        if thumb_path:
            os.remove(thumb_path)


    except Exception as e:

        logging.error(e)

        await status.edit_text("❌ Ошибка")


# ========= MAIN =========

async def main():

    await dp.start_polling(bot)


asyncio.run(main())





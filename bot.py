import asyncio
import logging
import os
import uuid
import json

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile

import yt_dlp

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

    bars = int(percent / 10)

    bar = "▓" * bars + "░" * (10 - bars)

    await status.edit_text(
        f"📥 Загрузка...\n\n"
        f"{bar} {percent:.0f}%"
    )


# ========= HANDLER =========

@dp.message()
async def handler(msg: types.Message):

    url = msg.text

    status = await msg.answer("🔍 Проверка...")

    # ========= CACHE =========

    if url in CACHE:

        await status.edit_text("⚡ Отправляю из кеша...")

        file_id = CACHE[url]

        await msg.answer_audio(file_id)

        await msg.delete()

        await status.delete()

        return


    unique = str(uuid.uuid4())

    # ========= OPTIONS =========

    def hook(d):

        if d['status'] == 'downloading':

            percent = float(
                d['_percent_str']
                .replace('%','')
                .strip()
            )

            asyncio.create_task(
                progress_bar(status, percent)
            )


    ydl_opts = {

        'format': 'bestaudio[ext=m4a]/bestaudio/best',

        'outtmpl': f'{DOWNLOAD}/{unique}.%(ext)s',

        'writethumbnail': True,

        'convert_thumbnails': 'jpg',

        'progress_hooks': [hook],

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

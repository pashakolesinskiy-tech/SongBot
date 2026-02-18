import asyncio
import logging
import os
import uuid
import json

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile

import yt_dlp

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

DOWNLOAD = "downloads"
CACHE_FILE = "cache.json"

os.makedirs(DOWNLOAD, exist_ok=True)

# загрузка кеша
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r", encoding="utf8") as f:
        CACHE = json.load(f)
else:
    CACHE = {}


def save_cache():
    with open(CACHE_FILE, "w", encoding="utf8") as f:
        json.dump(CACHE, f)


# прогресс бар
def progress_bar(percent):

    bars = int(percent / 10)

    return "▓" * bars + "░" * (10 - bars)


@dp.message(CommandStart())
async def start(msg: types.Message):

    await msg.answer("🎵 Отправь ссылку")


@dp.message()
async def handler(msg: types.Message):

    url = msg.text

    status = await msg.answer("⏳ Проверяю...")

    # кеш проверка
    if url in CACHE:

        await status.edit_text("⚡ Мгновенная отправка")

        await msg.answer_audio(CACHE[url])

        await msg.delete()

        await status.delete()

        return

    unique = str(uuid.uuid4())

    filename = f"{DOWNLOAD}/{unique}.m4a"

    last_percent = 0

    # прогресс
    async def progress(d):

        nonlocal last_percent

        if d['status'] == 'downloading':

            percent = d.get('_percent_str', '0').replace('%','')

            try:

                percent = float(percent)

            except:
                percent = 0

            if int(percent) != last_percent:

                last_percent = int(percent)

                bar = progress_bar(percent)

                try:
                    await status.edit_text(
                        f"📥 Загрузка...\n\n[{bar}] {int(percent)}%"
                    )
                except:
                    pass


    ydl_opts = {

        'format': 'bestaudio',

        'outtmpl': f'{DOWNLOAD}/{unique}.%(ext)s',

        'progress_hooks': [lambda d: asyncio.create_task(progress(d))],

        'quiet': True

    }

    try:

        with yt_dlp.YoutubeDL({
    'format': 'bestaudio[ext=m4a]/bestaudio/best',
    'outtmpl': f'{DOWNLOAD}/{unique}.%(ext)s',
    'writethumbnail': True,
    'convert_thumbnails': 'jpg',
    'postprocessors': [{
        'key': 'EmbedThumbnail',
    }],
}) as ydl:
    info = ydl.extract_info(url, download=True)

title = info.get("title", "Music")
performer = info.get("uploader", "Unknown")

# ищем аудио файл
audio_path = None
thumb_path = None

for f in os.listdir(DOWNLOAD):
    if f.startswith(unique) and f.endswith((".m4a", ".webm", ".mp3")):
        audio_path = f"{DOWNLOAD}/{f}"
    if f.startswith(unique) and f.endswith(".jpg"):
        thumb_path = f"{DOWNLOAD}/{f}"

audio = FSInputFile(audio_path)

if thumb_path and os.path.exists(thumb_path):
    thumb = FSInputFile(thumb_path)

    await msg.answer_audio(
        audio=audio,
        title=title,
        performer=performer,
        thumbnail=thumb
    )
else:
    await msg.answer_audio(
        audio=audio,
        title=title,
        performer=performer
    )

        # сохранить кеш
        CACHE[url] = sent.audio.file_id

        save_cache()

        await msg.delete()

        await status.delete()

    except Exception as e:

        logging.error(e)

        await status.edit_text("❌ Ошибка")


async def main():

    await dp.start_polling(bot)



asyncio.run(main())

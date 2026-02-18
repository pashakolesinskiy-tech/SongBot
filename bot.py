import os
import asyncio
import logging
import uuid
import time

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile

import yt_dlp

BOT_TOKEN = "8409897167:AAHC4RqLJHVb_qk-ouHmFu3gTuFeWfKtJss"

DOWNLOAD = "downloads"
FFMPEG_PATH = r"C:\ffmpeg\bin"

os.makedirs(DOWNLOAD, exist_ok=True)

logging.basicConfig(level=logging.INFO)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


# ===== ПРОГРЕСС БАР =====

progress_data = {}


def progress_hook(d):

    if d['status'] == 'downloading':

        total = d.get("total_bytes") or d.get("total_bytes_estimate")

        downloaded = d.get("downloaded_bytes", 0)

        if total:

            percent = int(downloaded * 100 / total)

            progress_data['percent'] = percent

    if d['status'] == 'finished':

        progress_data['percent'] = 100


async def progress_updater(message, status_msg):

    while True:

        percent = progress_data.get("percent", 0)

        bar = "▓" * (percent // 5) + "░" * (20 - percent // 5)

        try:

            await status_msg.edit_text(
                f"⬇️ Загрузка\n\n[{bar}] {percent}%"
            )
        except:
            pass

        if percent >= 100:
            break

        await asyncio.sleep(1)


# ===== START =====

@dp.message(CommandStart())
async def start(msg: types.Message):

    await msg.answer(
        "🎵 Отправь ссылку\n\n⚡ PRO бот"
    )


# ===== MAIN =====

@dp.message()
async def handler(msg: types.Message):

    url = msg.text

    status = await msg.answer("⏳ Подготовка...")

    unique = str(uuid.uuid4())

    filename = f"{DOWNLOAD}/{unique}.mp3"

    progress_data.clear()

    ydl_opts = {

        'format': 'bestaudio/best',

        'outtmpl': f'{DOWNLOAD}/{unique}.%(ext)s',

        'ffmpeg_location': FFMPEG_PATH,

        'noplaylist': True,

        'concurrent_fragment_downloads': 5,

        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }],

        'writethumbnail': True,

        'progress_hooks': [progress_hook],

        'quiet': True
    }

    try:

        progress_task = asyncio.create_task(
            progress_updater(msg, status)
        )

        start_time = time.time()

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(url, download=True)

        await progress_task

        title = info.get("title", "Music")
        performer = info.get("uploader", "Unknown")

        thumb = None

        for file in os.listdir(DOWNLOAD):

            if file.startswith(unique) and file.endswith(".jpg"):

                thumb = f"{DOWNLOAD}/{file}"

        await status.edit_text("📤 Отправка...")

        audio = FSInputFile(filename)

        if thumb:

            await msg.answer_audio(
                audio,
                title=title,
                performer=performer,
                thumbnail=FSInputFile(thumb)
            )

        else:

            await msg.answer_audio(
                audio,
                title=title,
                performer=performer
            )

        # удаление ссылки

        await msg.delete()

        speed = round(time.time() - start_time, 1)

        await status.edit_text(
            f"✅ Готово за {speed} сек ⚡"
        )

        await asyncio.sleep(2)

        await status.delete()

        os.remove(filename)

        if thumb:
            os.remove(thumb)

    except Exception as e:

        logging.error(e)

        await status.edit_text("❌ Ошибка")


# ===== RUN =====

async def main():

    await dp.start_polling(bot)


asyncio.run(main())

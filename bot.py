import asyncio
import logging
import os
import uuid

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile

import yt_dlp

BOT_TOKEN = "8409897167:AAHC4RqLJHVb_qk-ouHmFu3gTuFeWfKtJss"

logging.basicConfig(level=logging.INFO)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

DOWNLOAD = "downloads"
os.makedirs(DOWNLOAD, exist_ok=True)


@dp.message(CommandStart())
async def start(msg: types.Message):
    await msg.answer("🎵 Отправь ссылку")


@dp.message()
async def handler(msg: types.Message):

    url = msg.text

    status = await msg.answer("⏳ Загружаю")

    unique = str(uuid.uuid4())

    filename = f"{DOWNLOAD}/{unique}.mp3"
    thumb = None

    ydl_opts = {
    'format': 'bestaudio/best',

    'outtmpl': f'{DOWNLOAD}/{unique}.%(ext)s',

    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '320',
    }],

    'writethumbnail': True,
}




    try:

        await status.edit_text("📥 Скачиваю.")
        await asyncio.sleep(0.5)
        await status.edit_text("📥 Скачиваю..")
        await asyncio.sleep(0.5)
        await status.edit_text("📥 Скачиваю...")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        title = info.get("title", "Music")
        performer = info.get("uploader", "Unknown")

        for f in os.listdir(DOWNLOAD):
            if f.startswith(unique) and f.endswith(".jpg"):
                thumb = f"{DOWNLOAD}/{f}"

        await status.edit_text("📤 Отправляю")

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

        # красивая анимация удаления
        await status.edit_text("🧹 Удаляю ссылку.")
        await asyncio.sleep(0.3)

        await status.edit_text("🧹 Удаляю ссылку..")
        await asyncio.sleep(0.3)

        await status.edit_text("🧹 Удаляю ссылку...")
        await asyncio.sleep(0.3)

        await msg.delete()

        await status.edit_text("✅ Готово")

        await asyncio.sleep(1)

        await status.delete()

        os.remove(filename)

        if thumb:
            os.remove(thumb)

    except Exception as e:

        logging.error(e)

        await status.edit_text("❌ Ошибка")


async def main():
    await dp.start_polling(bot)


asyncio.run(main())
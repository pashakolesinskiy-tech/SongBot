
import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message
import yt_dlp

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

CACHE = {}

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("🚀 ULTRA Music Bot готов! Отправь название или ссылку")

@dp.message()
async def download_music(message: Message):
    query = message.text

    if query in CACHE:
        await message.answer_audio(CACHE[query], caption="⚡ Из кеша ULTRA")
        return

    status = await message.answer("🔍 Поиск ULTRA...")

    ydl_opts = {
        'format': 'bestaudio',
        'outtmpl': 'music.%(ext)s',
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch:{query}", download=True)['entries'][0]
        file = ydl.prepare_filename(info)

    audio = types.FSInputFile(file)

    CACHE[query] = audio

    await status.delete()
    await message.answer_audio(audio,
        title=info.get("title"),
        performer=info.get("uploader"),
        caption="🔥 ULTRA качество"
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

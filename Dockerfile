# Используем официальный Python slim (лёгкий, но с возможностью ставить пакеты)
FROM python:3.13-slim

# Устанавливаем ffmpeg + ffprobe + необходимые зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копируем requirements.txt (если у тебя есть) и устанавливаем зависимости
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код бота
COPY . .

# Запускаем бота
CMD ["python", "bot.py"]

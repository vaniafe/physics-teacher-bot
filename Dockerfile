# Используем официальный образ Python 3.12
FROM python:3.12-slim

# Рабочая папка внутри сервера
WORKDIR /app

# Копируем список библиотек и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем ВСЕ файлы бота в сервер
COPY . .

# Команда запуска
CMD ["python", "main.py"]

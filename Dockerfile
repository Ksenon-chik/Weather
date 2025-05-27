# Dockerfile

# 1. Базовый образ: лёгкий Debian с Python 3.12
FROM python:3.12-slim

# 2. Рабочая папка внутри контейнера
WORKDIR /app

# 3. Копируем файл зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Копируем весь код приложения
COPY . .

# 5. Открываем порт 5000
EXPOSE 5000

# 6. По умолчанию запускаем gunicorn, binding на все интерфейсы
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]

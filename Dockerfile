FROM python:3.13-slim

RUN apt-get update && apt-get install -y ffmpeg gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "bot.py"]

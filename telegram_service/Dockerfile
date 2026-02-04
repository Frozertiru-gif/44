FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN apt-get update \
    && apt-get install -y postgresql-client gnupg \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/scripts/entrypoint.sh

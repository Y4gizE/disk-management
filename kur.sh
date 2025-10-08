#!/bin/bash

# 1. .env kontrolü
if [ ! -f ".env" ]; then
    echo "FLASK_DEBUG=0" > .env
    echo "PYTHONUNBUFFERED=1" >> .env
    echo ".env oluşturuldu."
else
    echo ".env dosyası bulundu, yüklendi."
    export $(grep -v '^#' .env | xargs)
fi

# 2. Docker Compose build & up
docker compose up -d --build

# 3. Container çalışıyor mu kontrol
CONTAINER_NAME="disk-storage-container"
if docker ps | grep -q "$CONTAINER_NAME"; then
    echo "Container çalışıyor: $CONTAINER_NAME"
else
    echo "Container başlatılamadı."
    exit 1
fi

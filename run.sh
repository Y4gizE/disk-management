#!/bin/bash

# 0. Script’in bulunduğu dizine geç
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# 1. .env kontrolü ve yükleme
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
    echo ".env dosyası bulundu ve yüklendi."
else
    echo ".env dosyası bulunamadı, varsayılan ayarlar kullanılacak."
fi

# 2. Sanal ortam kontrolü ve oluşturma
if [ ! -d ".venv" ]; then
    echo "Sanal ortam bulunamadı, oluşturuluyor..."
    python3 -m venv .venv
    echo "Sanal ortam oluşturuldu."
fi

# 3. Sanal ortamı aktif et
echo "Sanal ortam aktif ediliyor..."
source .venv/bin/activate
echo "Sanal ortam aktif."

# 4. Gerekli paketlerin kurulması (requirements.txt varsa)
if [ -f "requirements.txt" ]; then
    echo "Gerekli paketler yükleniyor..."
    pip install --no-cache-dir -r requirements.txt
    echo "Paketler yüklendi."
fi

# 5. Docker Compose build & up (opsiyonel, container varsa)
if [ -f "docker-compose.yml" ]; then
    echo "Docker Compose build & up çalıştırılıyor..."
    docker compose up -d --build
fi

# 6. Python uygulamasını çalıştır
if [ -f "main.py" ]; then
    echo "Python uygulaması başlatılıyor..."
    python3 main.py server
else
    echo "HATA: main.py bulunamadı!"
fi

# 7. Terminalin açık kalması
echo "Uygulama tamamlandı veya durdu. Terminali kapatmak için Enter'a basın..."
read -r

#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# === .env yükle ===
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
    echo ".env dosyası yüklendi."
fi

# === Sanal ortamı aktif et ===
if [ ! -f ".venv/bin/activate" ]; then
    echo "HATA: Sanal ortam bulunamadı. kur.sh çalıştırılmalı."
    exit 1
fi

source .venv/bin/activate
echo "Sanal ortam aktif."

# === Uygulamayı çalıştır ===
if [ -f "main.py" ]; then
    python3 main.py server
else
    echo "HATA: main.py bulunamadı!"
fi

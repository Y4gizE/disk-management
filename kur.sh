#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# === 1. .env dosyasını yükle veya oluştur ===
if [ ! -f ".env" ]; then
    echo "FLASK_DEBUG=0" > .env
    echo "PYTHONUNBUFFERED=1" >> .env
    echo ".env oluşturuldu."
else
    export $(grep -v '^#' .env | xargs)
    echo ".env dosyası bulundu ve yüklendi."
fi

# === 2. Python venv ve gerekli paketler ===
if ! python3 -m venv --help >/dev/null 2>&1; then
    echo "python3-venv eksik, yükleniyor..."
    apt update -y
    apt install -y python3-venv python3-pip python3-dev build-essential libmagic-dev
fi

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "Sanal ortam oluşturuldu."
fi

source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel

if [ -f "requirements.txt" ]; then
    echo "Python paketleri yükleniyor..."
    pip install --no-cache-dir -r requirements.txt
    echo "Python paketleri yüklendi."
fi

# === 3. Docker / Podman kurulum ===
if ! command -v docker >/dev/null 2>&1 && ! command -v podman >/dev/null 2>&1; then
    echo "Docker veya Podman yüklü değil, kuruluyor..."
    apt install -y docker.io podman || true
fi

if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files | grep -q docker.service; then
    systemctl enable --now docker || true
fi

echo "Kurulum tamamlandı."

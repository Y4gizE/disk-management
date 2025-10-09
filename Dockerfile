# Python 3.9 slim tabanlı imaj
FROM python:3.9-slim

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y \
    wget \
    build-essential \
    gcc \
    g++ \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# unrar kurulumu (rarfile için)
RUN mkdir -p /tmp/unrar && \
    cd /tmp/unrar && \
    wget https://www.rarlab.com/rar/unrarsrc-6.2.6.tar.gz && \
    tar -xzf unrarsrc-6.2.6.tar.gz && \
    cd unrar && \
    make -j$(nproc) && \
    make install && \
    cd / && \
    rm -rf /tmp/unrar

# Çalışma dizini
WORKDIR /app

# Requirements dosyasını kopyala ve yükle
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY . .

# Port aç
EXPOSE 5000

# Paylaşılan klasör
VOLUME ["/shared_storage"]

# Uygulamayı başlat
CMD ["python", "main.py", "server"]

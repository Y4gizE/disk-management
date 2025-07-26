#!/bin/bash

echo "Dağıtık Depolama Sistemi Kurulumu"
echo "================================="
echo ""

# Docker yüklü mü?
echo "Docker kontrol ediliyor..."
if command -v docker &> /dev/null; then
    echo "Docker zaten yüklü."
    # Docker çalışıyor mu kontrol et
    if docker ps &> /dev/null; then
        echo "Docker çalışır durumda."
    else
        echo "Docker çalışmıyor. Başlatılıyor..."
        sudo systemctl start docker
        # Tekrar kontrol et
        if ! docker ps &> /dev/null; then
            echo "HATA: Docker başlatılamadı. Lütfen manuel olarak başlatmayı deneyin: 'sudo systemctl start docker'"
            exit 1
        fi
    fi
else
    echo "Docker bulunamadı. Yükleme işlemi başlatılıyor..."
    echo ""
    echo "1. Gerekli paketler yükleniyor..."
    sudo apt-get update
    sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common

    echo "2. Docker'ın resmi GPG anahtarı ekleniyor..."
    sudo systemctl start docker
    
    # Wait for Docker to start
    sleep 5
    
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}Docker başlatılamadı. Lütfen manuel olarak başlatıp tekrar deneyin.${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓ Docker yüklü ve çalışıyor.${NC}"

# Check if update is needed
NEED_UPDATE=0

echo -e "${GREEN}Kontrol ediliyor: Güncellemeler...${NC}"

# Check if image exists
if ! docker images -q disk-storage >/dev/null 2>&1; then
    echo -e "${YELLOW}Yeni kurulum tespit edildi. Gerekli dosyalar indirilecek...${NC}"
    NEED_UPDATE=1
else
    echo -e "${GREEN}Mevcut kurulum kontrol ediliyor...${NC}"
    # Check if container exists
    if docker ps -a --filter "name=disk-storage-container" --format '{{.Names}}' | grep -q "disk-storage-container"; then
        echo -e "${YELLOW}Mevcut konteyner durduruluyor...${NC}"
        docker stop disk-storage-container >/dev/null 2>&1
        docker rm disk-storage-container >/dev/null 2>&1
        NEED_UPDATE=1
    fi
fi

# Create shared folder with full permissions
SHARED_FOLDER="$HOME/Downloads/DiskStorage"

# Ensure the shared folder exists and has correct permissions
echo -e "${GREEN}Paylaşılan klasör ayarlanıyor: $SHARED_FOLDER${NC}"
if [ ! -d "$SHARED_FOLDER" ]; then
    mkdir -p "$SHARED_FOLDER"
    chmod 777 "$SHARED_FOLDER"
    echo -e "${GREEN}Paylaşılan klasör oluşturuldu: $SHARED_FOLDER${NC}"
else
    echo -e "${GREEN}Paylaşılan klasör zaten mevcut: $SHARED_FOLDER${NC}"
fi

# Simple disk quota notice
echo -e "${YELLOW}Not: Disk kotası manuel olarak kontrol edilecek. Maksimum 5GB kullanabilirsiniz.${NC}"

# Perform update if needed
if [ "$NEED_UPDATE" -eq 1 ]; then
    echo -e "\n${GREEN}===================================================${NC}"
    echo -e "${GREEN}  Güncelleme yapılıyor..."
    echo -e "===================================================${NC}"
    
    # Build the new image
    echo -e "${GREEN}Docker imajı oluşturuluyor...${NC}"
    if ! docker build -t disk-storage .; then
        echo -e "${RED}Hata: Konteyner oluşturulamadı.${NC}"
        exit 1
    fi

    # Start the container
    echo -e "${GREEN}Konteyner başlatılıyor...${NC}"
    if ! docker run -d \
        -p 5000:5000 \
        --name disk-storage-container \
        -v "$SHARED_FOLDER:/shared_storage" \
        -v /var/run/docker.sock:/var/run/docker.sock \
        --restart unless-stopped \
        --user $(id -u):$(id -g) \
        disk-storage; then
        
        echo -e "${RED}Hata: Konteyner başlatılamadı.${NC}"
        exit 1
    fi
    
    echo -e "\n${GREEN}✓ Güncelleme başarıyla tamamlandı!${NC}"
else
    # Just start the existing container
    echo -e "\n${GREEN}Güncelleme gerekmiyor. Mevcut kurulum başlatılıyor...${NC}"
    docker start disk-storage-container >/dev/null 2>&1
fi

echo -e "\n${GREEN}===================================================${NC}"
echo -e "${GREEN}  Disk Storage başarıyla kuruldu ve çalışıyor!${NC}"
echo -e "${GREEN}  Web Arayüzü: http://localhost:5000${NC}"
echo -e "${GREEN}  Paylaşılan Klasör: $SHARED_FOLDER${NC}"
echo -e "\n  Bu klasörü kullanarak dosyalarınızı paylaşabilirsiniz."
echo -e "  5GB'lık bir disk kotası uygulanmıştır."
echo -e "${GREEN}===================================================${NC}\n"

# Open browser if xdg-utils is installed
if command -v xdg-open &> /dev/null; then
    xdg-open "http://localhost:5000" &
elif command -v gnome-open &> /dev/null; then
    gnome-open "http://localhost:5000" &
fi

echo -e "${GREEN}İstemci eklemek için şu komutu kullanın:${NC}"
echo "python main.py client register localhost --device-id CIHAZ_ADI --share /paylasilan/klasor"
echo ""
echo "Örnek:"
echo "python main.py client register localhost --device-id bilgisayarim --share /home/kullanici/Belgeler"

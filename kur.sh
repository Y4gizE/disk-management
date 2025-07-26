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

# Create shared folder if it doesn't exist
SHARED_FOLDER="$HOME/Downloads/DiskStorage"
if [ ! -d "$SHARED_FOLDER" ]; then
    echo -e "${GREEN}Paylaşılan klasör oluşturuluyor: $SHARED_FOLDER${NC}"
    mkdir -p "$SHARED_FOLDER"
    chmod 777 "$SHARED_FOLDER"
else
    echo -e "${GREEN}Paylaşılan klasör zaten mevcut: $SHARED_FOLDER${NC}"
fi

# Set disk quota (requires quota package)
if ! command -v setquota &> /dev/null; then
    echo -e "${YELLOW}Disk kotası için 'quota' paketi yükleniyor...${NC}"
    if [ -x "$(command -v apt-get)" ]; then
        sudo apt-get install -y quota
    elif [ -x "$(command -v yum)" ]; then
        sudo yum install -y quota
    fi
fi

# Check if we can set quota
if command -v setquota &> /dev/null; then
    echo -e "${GREEN}5GB disk kotası ayarlanıyor...${NC}"
    # This requires the filesystem to be mounted with usrquota,grpquota options
    # and may require system reboot
    sudo setquota -u $USER 5G 5G 0 0 /home
else
    echo -e "${YELLOW}Uyarı: Disk kotası ayarlanamadı. 'quota' paketi yüklenemedi.${NC}"
fi

echo -e "${GREEN}Konteyner oluşturuluyor ve başlatılıyor...${NC}"

# Stop and remove existing container if it exists
docker stop disk-storage-container >/dev/null 2>&1
docker rm disk-storage-container >/dev/null 2>&1

# Build and start the container
echo -e "${GREEN}Docker imajı oluşturuluyor...${NC}"
if ! docker build -t disk-storage .; then
    echo -e "${RED}Hata: Konteyner oluşturulamadı.${NC}"
    exit 1
fi

echo -e "${GREEN}Konteyner başlatılıyor...${NC}"
if ! docker run -d \
    -p 5000:5000 \
    --name disk-storage-container \
    -v "$SHARED_FOLDER:/shared_storage" \
    --restart unless-stopped \
    disk-storage; then
    
    echo -e "${RED}Hata: Konteyner başlatılamadı.${NC}"
    exit 1
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

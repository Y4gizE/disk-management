#!/bin/bash

# Renk tanımları
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Ayarlar
MAX_RETRIES=3
RETRY_DELAY=5

echo -e "${GREEN}Dağıtık Depolama Sistemi Kurulumu${NC}"
echo -e "${GREEN}=================================${NC}"
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

# Check for network connectivity
echo -e "${BLUE}Ağ bağlantısı kontrol ediliyor...${NC}"

# Check internet connectivity
check_internet() {
    if ! ping -c 1 8.8.8.8 &> /dev/null; then
        echo -e "${YELLOW}Uyarı: İnternet bağlantısı yok. Sadece yerel ağda çalışılacak.${NC}"
        return 1
    fi
    return 0
}

# Get public IP
get_public_ip() {
    local ip=""
    if check_internet; then
        ip=$(curl -s https://api.ipify.org)
    fi
    echo "$ip"
}

# Check if port is open
check_port() {
    local ip=$1
    local port=$2
    timeout 1 bash -c "</dev/tcp/$ip/$port &>/dev/null"
    return $?
}

# Ensure the shared folder exists and has correct permissions
echo -e "\n${GREEN}Paylaşılan klasör ayarlanıyor: $SHARED_FOLDER${NC}"

# Check if we have a public IP
PUBLIC_IP=$(get_public_ip)
if [ -n "$PUBLIC_IP" ]; then
    echo -e "${GREEN}Genel IP adresiniz: $PUBLIC_IP${NC}"
else
    echo -e "${YELLOW}Uyarı: Genel IP adresi alınamadı. Sadece yerel ağda erişilebilir olacaksınız.${NC}"
fi
if [ ! -d "$SHARED_FOLDER" ]; then
    echo -e "${YELLOW}Klasör oluşturuluyor: $SHARED_FOLDER${NC}"
    mkdir -p "$SHARED_FOLDER"
    if [ $? -ne 0 ]; then
        echo -e "${RED}Hata: Klasör oluşturulamadı. İzinleri kontrol edin.${NC}"
        exit 1
    fi
    # Set full permissions
    chmod 777 "$SHARED_FOLDER"
    if [ $? -ne 0 ]; then
        echo -e "${YELLOW}Uyarı: Klasör izinleri değiştirilemedi. Kşıtlamalı erişim olabilir.${NC}"
    fi
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
    
    # Retry logic for docker build
    for i in $(seq 1 $MAX_RETRIES); do
        if docker build -t disk-storage .; then
            break
        else
            if [ $i -eq $MAX_RETRIES ]; then
                echo -e "${RED}Hata: Konteyner oluşturulamadı (Deneme $i/$MAX_RETRIES).${NC}"
                exit 1
            fi
            echo -e "${YELLOW}Uyarı: Oluşturma başarısız oldu, yeniden deneniyor ($((i+1))/$MAX_RETRIES)...${NC}"
            sleep $RETRY_DELAY
        fi
    done

    # Start the container with additional network settings
    echo -e "${GREEN}Konteyner başlatılıyor...${NC}"
    
    # Additional network parameters for better connectivity
    NETWORK_PARAMS=""
    if [ -n "$PUBLIC_IP" ]; then
        NETWORK_PARAMS="--network host"
        echo -e "${GREEN}Geniş ağ erişimi etkinleştirildi.${NC}"
    else
        NETWORK_PARAMS="-p 5000:5000"
        echo -e "${YELLOW}Sadece 5000 portu üzerinden erişim sağlanacak.${NC}"
    fi
    
    # Start the container with retry logic
    for i in $(seq 1 $MAX_RETRIES); do
        if docker run -d \
            $NETWORK_PARAMS \
            --name disk-storage-container \
            -v "$SHARED_FOLDER:/shared_storage" \
            -v /var/run/docker.sock:/var/run/docker.sock \
            --restart unless-stopped \
            --user $(id -u):$(id -g) \
            disk-storage; then
            break
        else
            if [ $i -eq $MAX_RETRIES ]; then
                echo -e "${RED}Hata: Konteyner başlatılamadı (Deneme $i/$MAX_RETRIES).${NC}"
                exit 1
            fi
            echo -e "${YELLOW}Uyarı: Başlatma başarısız oldu, yeniden deneniyor ($((i+1))/$MAX_RETRIES)...${NC}"
            sleep $RETRY_DELAY
        fi
    done
    
    echo -e "\n${GREEN}✓ Güncelleme başarıyla tamamlandı!${NC}"
    
    # Show connection information
    echo -e "\n${BLUE}=== Bağlantı Bilgileri ===${NC}"
    echo -e "Yerel Ağ: http://$(hostname -I | awk '{print $1}'):5000"
    if [ -n "$PUBLIC_IP" ]; then
        echo -e "Genel Ağ: http://$PUBLIC_IP:5000"
        echo -e "\n${YELLOW}NOT: Genel ağdan erişim için 5000 portunun yönlendirildiğinden emin olun.${NC}"
    fi
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

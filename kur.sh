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
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

    echo "3. Docker deposu ekleniyor..."
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    echo "4. Docker yükleniyor..."
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io

    echo "5. Docker servisi başlatılıyor..."
    sudo systemctl start docker
    sudo systemctl enable docker

    echo "6. Kullanıcının docker grubuna eklenmesi..."
    sudo usermod -aG docker $USER

    echo ""
    echo "Docker başarıyla yüklendi!"
    echo "Yüklemenin etkili olması için oturumunuzu kapatıp tekrar açmanız gerekebilir."
    echo "Kurulumu tamamlamak için bu betiği tekrar çalıştırın."
    echo ""
    exit 0
fi

echo ""
echo "Docker imajı oluşturuluyor..."
docker build -t distributed-storage .
if [ $? -ne 0 ]; then
    echo "HATA: Docker imajı oluşturulurken bir hata oluştu."
    exit 1
fi

echo ""
echo "Sunucu başlatılıyor..."
docker run -d -p 5000:5000 --name storage-server distributed-storage
if [ $? -ne 0 ]; then
    echo "UYARI: Sunucu zaten çalışıyor olabilir. Eski konteyner durdurulup yeniden başlatılıyor..."
    docker stop storage-server &> /dev/null
    docker rm storage-server &> /dev/null
    docker run -d -p 5000:5000 --name storage-server distributed-storage
fi

echo ""
echo "================================="
echo "Sunucu başarıyla başlatıldı!"
echo "Sunucu adresi: http://localhost:5000"
echo ""
echo "İstemci eklemek için şu komutu kullanın:"
echo "python main.py client register localhost --device-id CIHAZ_ADI --share /paylasilan/klasor"
echo ""
echo "Örnek:"
echo "python main.py client register localhost --device-id bilgisayarim --share /home/kullanici/Belgeler"

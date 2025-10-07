# Distributed Storage System

A distributed file storage system with web interface, supporting file sharing over local network with built-in RAR archive support.

## Özellikler (EKSİKLER GÜNCELLENECEKTİR ve KURULUM KOLAYLIĞI SAĞLANACAKTIR)

- Ağ üzerinden dosya paylaşımı
- Web arayüzü üzerinden dosya yükleme/indirme/silme
- Otomatik cihaz keşfi (mDNS/Zeroconf)
- ZIP ve RAR arşiv içeriği görüntüleme
- RAR arşivlerinde içerik önizleme (metin, resim, PDF)
- İç içe klasör gezinme desteği
- Çok seviyeli klasör yapısı desteği

## RAR Desteği

Sistem, RAR arşivlerini görüntülemek için entegre bir işlemci kullanır. Bu özellik Docker konteyneri içinde çalışarak RAR arşivlerinin içeriğini güvenli bir şekilde görüntülemenizi sağlar.

### Gereksinimler

- Docker Desktop (Windows/Mac) veya Docker Engine (Linux)
- Python 3.9+
- Gerekli Python paketleri (`requirements.txt` dosyasında listelenmiştir)

## Kurulum

1.**Dosya izinlerini ayarlayın (Linux için):**  
   ```bash
   chmod 777 -R disk-management
   ```
2. **Sanal ortam oluşturun ve etkinleştirin (Linux için önerilir):**  
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Gerekli Python paketlerini yükleyin:**  
   ```bash
   pip install -r requirements.txt
   ```

4. **Docker imajını oluşturun ve uygulamayı başlatın:**  
   ```bash
   # Docker imajını oluştur
   docker build -t disk-management .
   
   # Konteyneri başlat (RAR işlemcisi otomatik olarak etkinleştirilecektir)
   docker run -d --name disk-management      -p 5000:5000      -p 5001:5001      -v "$HOME/Downloads/DiskStorage:/app/shared_storage"      -e ENABLE_RAR_PROCESSOR=true      disk-management
   ```

   **Alternatif olarak doğrudan Python ile çalıştırmak için:**  
   ```bash
   export ENABLE_RAR_PROCESSOR=true
   python main.py
   ```

## RAR İşlemcisi Özellikleri

- RAR arşivlerinin içeriğini tarayıcıda görüntüleme
- Metin dosyalarını doğrudan tarayıcıda önizleme
- Resim ve PDF dosyalarını doğrudan görüntüleme
- Arşiv içinde gezinebilir klasör yapısı
- Dosya bilgilerini (boyut, değiştirilme tarihi) görüntüleme

## Kullanım

1. Tarayıcınızda `http://localhost:5000` adresine gidin
2. Varsayılan şifre: `1234`
3. Dosya yükleyin, indirin veya silin
4. ZIP/RAR dosyalarının içeriğini görüntülemek için üzerlerine tıklayın
5. RAR içindeki dosyaları görüntülemek için dosya adının yanındaki göz simgesine tıklayın
6. Klasörler arasında gezinmek için klasör adlarına tıklayın
7. Üst klasöre dönmek için "Üst Dizine Git" bağlantısını kullanın

### RAR İçeriği Görüntüleme

1. Herhangi bir RAR dosyasına tıklayın
2. Açılan sayfada dosya listesini göreceksiniz
3. Bir dosyayı görüntülemek için yanındaki göz simgesine tıklayın
4. Dosya içeriği doğrudan tarayıcıda görüntülenecektir
5. İndirmek için indir simgesini kullanabilirsiniz

## Bilinen Sorunlar ve Sınırlamalar

- Şifre korumalı RAR dosyaları desteklenmemektedir
- Çok büyük RAR dosyalarında (2GB+) performans düşebilir
- RAR5 formatı sınırlı destek sunmaktadır
- Windows'ta Docker kullanırken dosya izinlerine dikkat edilmelidir
- Linux'ta depolanan ortak klasör /root/Downloads/DiskStorage/ dizininde yer almaktadır.

## Sorun Giderme

### RAR İşlemcisi Çalışmıyorsa

1. Docker'ın çalıştığından emin olun
2. Konteyner günlüklerini kontrol edin:
   ```bash
   docker logs disk-management
   ```
3. RAR işlemcisinin çalıştığını doğrulayın:
   ```bash
   curl http://localhost:5001/health
   ```
4. Gerekirse konteyneri yeniden başlatın:
   ```bash
   docker restart disk-management
   ```

## Ekran Görüntüsü

![Arayüz Görüntüsü](https://github.com/user-attachments/assets/3bdf1e37-7d0b-42d5-b445-86bfb615d17f)

# Disk Yönetim Sistemi

Bu uygulama, farklı cihazlar arasında dosya paylaşımı yapmanızı sağlayan bir dağıtık depolama çözümüdür. Hem yerel ağda hem de internet üzerinden çalışabilir.

## Hızlı Başlangıç

### Windows'ta Kurulum

1. Komut istemini yönetici olarak açın:
   ```cmd
   kur.bat
   ```

### Linux'ta Kurulum

1. Terminali açın ve şu komutları çalıştırın:
   ```bash
   chmod +x kur.sh
   ./kur.sh
   ```

## Farklı Ağlardan Bağlantı

### Genel Ağ Erişimi

1. **Yönlendiricide Port Açma (NAT/Port Forwarding):**
   - Yönlendiricinizin yönetim paneline giriş yapın (genellikle `http://192.168.1.1` veya `http://192.168.0.1`)
   - "Port Yönlendirme" veya "Port Forwarding" bölümüne gidin
   - Yeni bir kural ekleyin:
     - Dış Port: `5000`
     - İç IP: [Bilgisayarınızın yerel IP adresi]
     - İç Port: `5000`
     - Protokol: `TCP` (veya `TCP/UDP`)

2. **Güvenlik Duvarı Ayarları:**
   ```bash
   # Linux'ta
   sudo ufw allow 5000/tcp
   ```
   
   ```powershell
   # Windows'ta (Yönetici olarak çalıştırın)
   netsh advfirewall firewall add rule name="Disk Yönetim Sistemi" dir=in action=allow protocol=TCP localport=5000
   ```

### Yerel Ağ Erişimi

- Aynı ağdaki diğer cihazlardan erişmek için:
  ```
  http://[BİLGİSAYAR_IP]:5000
  ```
  Örnek: `http://192.168.1.5:5000`

## Gelişmiş Yapılandırma

### Docker Ağ Ayarları

Varsayılan olarak uygulama `host` ağ modunda çalışır. Özel bir ağ yapılandırması için:

```bash
# Özel bir ağ oluşturma
docker network create disk-network

# Konteyneri özel ağda çalıştırma
docker run -d \
  --network disk-network \
  --name disk-storage-container \
  -p 5000:5000 \
  -v "$HOME/Downloads/DiskStorage:/shared_storage" \
  disk-storage
```

## Sorun Giderme

### Bağlantı Sorunları

1. **Port Kontrolü:**
   ```bash
   # Linux'ta
   sudo netstat -tuln | grep 5000
   
   # Veya
   ss -tuln | grep 5000
   ```

2. **Docker Loglarını Görüntüleme:**
   ```bash
   docker logs disk-storage-container
   ```

3. **Docker Konteyner Durumu:**
   ```bash
   docker ps -a
   ```

## Lisans

Bu proje MIT lisansı altında lisanslanmıştır.
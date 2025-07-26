@echo off
echo Dağıtık Depolama Sistemi Kurulumu
echo =================================
echo.

:: Docker'ın kurulu olup olmadığını kontrol et
echo Docker kontrol ediliyor...
docker --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo HATA: Docker bulunamadı. Lütfen Docker'ı yükleyin: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

echo Docker çalışıyor mu kontrol ediliyor...
docker ps >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo HATA: Docker çalışmıyor. Lütfen Docker Desktop'ı başlatın ve tekrar deneyin.
    pause
    exit /b 1
)

echo.
echo Docker imajı oluşturuluyor...
docker build -t distributed-storage .
if %ERRORLEVEL% NEQ 0 (
    echo HATA: Docker imajı oluşturulurken bir hata oluştu.
    pause
    exit /b 1
)

echo.
echo Sunucu başlatılıyor...
docker run -d -p 5000:5000 --name storage-server distributed-storage
if %ERRORLEVEL% NEQ 0 (
    echo UYARI: Sunucu zaten çalışıyor olabilir. Mevcut konteyner durdurulup yeniden başlatılıyor...
    docker stop storage-server >nul 2>&1
    docker rm storage-server >nul 2>&1
    docker run -d -p 5000:5000 --name storage-server distributed-storage
)

echo.
echo =================================
echo Sunucu başarıyla başlatıldı!
echo Sunucu adresi: http://localhost:5000
echo.
echo İstemci eklemek için şu komutu kullanın:
echo python main.py client register localhost --device-id CIHAZ_ADI --share PAYLASILACAK_KLASOR
echo.
echo Örnek:
echo python main.py client register localhost --device-id bilgisayarim --share C:\PaylasilanDosyalar
echo.
pause

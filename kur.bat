@echo off
setlocal enabledelayedexpansion
echo Dağıtık Depolama Sistemi Kurulumu
echo =================================
echo.

:: Docker'ın kurulu olup olmadığını kontrol et
echo Docker kontrol ediliyor...
docker --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Docker zaten yüklü.
    goto :docker_running
)

echo Docker bulunamadı. Yükleme işlemi başlatılıyor...
echo Lütfen Docker Desktop'ı indirin ve yükleyin: https://desktop.docker.com/win/stable/amd64/Docker%20Desktop%20Installer.exe
echo.
echo Yükleme tamamlandığında bu pencereyi kapatın ve tekrar kur.bat dosyasını çalıştırın.
echo.
start "" "https://desktop.docker.com/win/stable/amd64/Docker%20Desktop%20Installer.exe"
pause
exit /b 0

:docker_running
echo Docker çalışıyor mu kontrol ediliyor...
docker ps >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo HATA: Docker çalışmıyor. Lütfen Docker Desktop'ı başlatın ve tekrar deneyin.
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo Lütfen Docker Desktop'ın başlamasını bekleyin ve ardından bu pencereyi kapatıp tekrar deneyin.
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

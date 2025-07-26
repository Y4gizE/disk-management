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
@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo Disk Storage Güncelleme ve Yapılandırma
echo ===================================================
echo.

:: Check if Docker is installed
docker --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [HATA] Docker bulunamadı. Lütfen önce Docker Desktop yükleyin:
    echo https://www.docker.com/products/docker-desktop
    echo Yükleme sonrası bilgisayarınızı yeniden başlatıp bu betiği tekrar çalıştırın.
    pause
    exit /b 1
)

:: Check if Docker is running
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [UYARI] Docker çalışmıyor. Başlatılıyor...
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    echo Docker'in başlaması bekleniyor...
    timeout /t 30 /nobreak >nul
    
    :: Check again if Docker is running
    docker info >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo [HATA] Docker başlatılamadı. Lütfen Docker Desktop'ı manuel olarak başlatıp tekrar deneyin.
        pause
        exit /b 1
    )
)

echo [OK] Docker yüklü ve çalışıyor.
echo.

:: Check for container updates
echo Kontrol ediliyor: Güncellemeler...
set "NEEDS_UPDATE=0"

:: Check if image exists and is up to date
docker images -q disk-storage >nul
if %ERRORLEVEL% neq 0 (
    echo Yeni kurulum tespit edildi. Gerekli dosyalar indirilecek...
    set "NEEDS_UPDATE=1"
) else (
    echo Mevcut kurulum kontrol ediliyor...
    for /f "tokens=*" %%i in ('docker ps -a --filter "name=disk-storage-container" --format "{{.Names}}"') do (
        if "%%i"=="disk-storage-container" (
            echo Mevcut konteyner durduruluyor...
            docker stop disk-storage-container >nul 2>&1
            docker rm disk-storage-container >nul 2>&1
            set "NEEDS_UPDATE=1"
        )
    )
)

:: Create shared folder if it doesn't exist
set "SHARED_FOLDER=%USERPROFILE%\Downloads\DiskStorage"
if not exist "%SHARED_FOLDER%" (
    echo [YENİ] Paylaşılan klasör oluşturuluyor: %SHARED_FOLDER%
    mkdir "%SHARED_FOLDER%"
) else (
    echo [OK] Paylaşılan klasör mevcut: %SHARED_FOLDER%
)

if "%NEEDS_UPDATE%"=="1" (
    echo.
    echo ===================================================
    echo Güncelleme yapılıyor...
    echo ===================================================
    
    :: Build the new image
    echo Yeni Docker imajı oluşturuluyor...
    docker build -t disk-storage .
    if %ERRORLEVEL% neq 0 (
        echo [HATA] Konteyner oluşturulamadı.
        pause
        exit /b 1
    )
    
    echo Yeni konteyner başlatılıyor...
    docker run -d ^
        -p 5000:5000 ^
        --name disk-storage-container ^
        -v "%SHARED_FOLDER%:/shared_storage" ^
        --restart unless-stopped ^
        disk-storage
    
    if %ERRORLEVEL% neq 0 (
        echo [HATA] Konteyner başlatılamadı.
        pause
        exit /b 1
    )
    
    echo [OK] Güncelleme başarıyla tamamlandı!
) else (
    echo.
    echo [BİLGİ] Güncelleme gerekmiyor. Mevcut kurulum kullanılıyor.
    docker start disk-storage-container >nul 2>&1
)

echo.
echo ===================================================
echo Disk Storage basariyla kuruldu ve calisiyor!
echo Web Arayuzu: http://localhost:5000
echo Paylasilan Klasor: %SHARED_FOLDER%
echo.
echo Bu klasoru kullanarak dosyalarinizi paylasabilirsiniz.
echo 5GB'lık bir disk kotasi uygulanmistir.
echo ===================================================
echo.

:: Open browser
start http://localhost:5000

pause

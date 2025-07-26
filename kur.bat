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
echo Disk Storage Kurulum ve Yapilandirma
echo ===================================================
echo.

:: Check if Docker is installed
docker --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Docker bulunamadi. Lutfen Docker Desktop'i yukleyin:
    echo https://www.docker.com/products/docker-desktop
    echo Yükleme tamamlandiktan sonra bilgisayarinizi yeniden baslatin ve bu betigi tekrar calistirin.
    pause
    exit /b 1
)

:: Check if Docker is running
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Docker calismiyor. Docker Desktop baslatiliyor...
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    echo Docker'in baslamasi bekleniyor...
    timeout /t 30 /nobreak >nul
    
    :: Check again if Docker is running
    docker info >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo Docker baslatilamadi. Lutfen Docker Desktop'i manuel olarak baslatin ve bu betigi tekrar calistirin.
        pause
        exit /b 1
    )
)

echo Docker yuklu ve calisiyor.
echo.

:: Create shared folder if it doesn't exist
set "SHARED_FOLDER=%USERPROFILE%\Downloads\DiskStorage"
if not exist "%SHARED_FOLDER%" (
    echo Paylasilan klasor olusturuluyor: %SHARED_FOLDER%
    mkdir "%SHARED_FOLDER%"
    echo Klasor olusturuldu: %SHARED_FOLDER%
) else (
    echo Paylasilan klasor zaten mevcut: %SHARED_FOLDER%
)

echo.
echo Konteyner olusturuluyor ve baslatiliyor...

:: Stop and remove existing container if it exists
docker stop disk-storage-container >nul 2>&1
docker rm disk-storage-container >nul 2>&1

:: Build and start the container
docker build -t disk-storage .
if %ERRORLEVEL% neq 0 (
    echo Hata: Konteyner olusturulamadi.
    pause
    exit /b 1
)

docker run -d ^
    -p 5000:5000 ^
    --name disk-storage-container ^
    -v "%SHARED_FOLDER%:/shared_storage" ^
    --restart unless-stopped ^
    disk-storage

if %ERRORLEVEL% neq 0 (
    echo Hata: Konteyner baslatilamadi.
    pause
    exit /b 1
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

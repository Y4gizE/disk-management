@echo off
setlocal enabledelayedexpansion

:: Hata ayıklama için komut penceresini açık tut
if "%DEBUG%"=="" (
    set DEBUG=1
    cmd /k "%~dpnx0" %*
    exit /b %ERRORLEVEL%
)

:: Çalışma dizinini ayarla
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: Yükleme ayarları
set "SHARED_FOLDER=%USERPROFILE%\Downloads\DiskStorage"
set "MAX_RETRIES=3"
set "RETRY_DELAY=5"

:: Basit renk kodu tanımları
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "NC=[0m"

echo =================================
echo    Dağıtık Depolama Sistemi Kurulumu
echo =================================
echo.

:: Docker kontrolü
echo.
echo === Docker Kontrolü ===
docker --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Docker zaten yüklü.
) else (
    echo [UYARI] Docker bulunamadı. Yükleme işlemi başlatılıyor...
    start "" "https://desktop.docker.com/win/stable/amd64/Docker%20Desktop%20Installer.exe"
    echo.
    echo Lütfen Docker Desktop'ı yükleyin ve kurulum tamamlandığında bu pencereyi kapatıp tekrar deneyin.
    echo.
    pause
    exit /b 0
)

:: Docker servisini başlat
echo.
echo === Docker Servisi Kontrolü ===
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [UYARI] Docker çalışmıyor. Başlatılıyor...
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    
    echo Docker'in başlaması bekleniyor...
    for /l %%i in (1,1,30) do (
        docker info >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            echo [OK] Docker başarıyla başlatıldı.
            goto :docker_running
        )
        timeout /t 1 >nul
        echo .\c
    )
    
    echo [HATA] Docker başlatılamadı. Lütfen Docker Desktop'ı manuel olarak başlatıp tekrar deneyin.
    pause
    exit /b 1
) else (
    echo [OK] Docker çalışıyor.
)

:docker_running
:: Konteyner kontrolü
echo.
echo === Konteyner Kontrolü ===
docker ps -a --filter "name=disk-storage-container" --format "{{.Names}}" | findstr /i "disk-storage-container" >nul
if %ERRORLEVEL% EQU 0 (
    echo Konteyner bulundu, durumu kontrol ediliyor...
    docker ps --filter "name=disk-storage-container" --format "{{.Names}}" | findstr /i "disk-storage-container" >nul
    if %ERRORLEVEL% EQU 0 (
        echo [OK] Konteyner zaten çalışıyor.
        goto :show_info
    ) else (
        echo [UYARI] Konteyner durdurulmuş, yeniden başlatılıyor...
        docker start disk-storage-container >nul
        if %ERRORLEVEL% EQU 0 (
            echo [OK] Konteyner başarıyla başlatıldı.
            goto :show_info
        ) else (
            echo [HATA] Konteyner başlatılamadı.
            goto :rebuild_container
        )
    )
) else (
    echo [UYARI] Konteyner bulunamadı, oluşturuluyor...
    goto :rebuild_container
)

:: Konteyner oluşturma
:rebuild_container
echo [İŞLEM] Yeni konteyner oluşturuluyor...

:: Paylaşılan klasörü oluştur
if not exist "%SHARED_FOLDER%" (
    echo Paylaşılan klasör oluşturuluyor: %SHARED_FOLDER%
    mkdir "%SHARED_FOLDER%"
    icacls "%SHARED_FOLDER%" /grant "Everyone:(OI)(CI)F" /T
)

:: İmajı oluştur
echo Docker imajı oluşturuluyor...
docker build -t disk-storage .
if %ERRORLEVEL% NEQ 0 (
    echo [HATA] Docker imajı oluşturulamadı.
    pause
    exit /b 1
)

:: Konteynerı başlat
echo Konteyner başlatılıyor...
docker run -d ^
    --name disk-storage-container ^
    -p 5000:5000 ^
    -v "%SHARED_FOLDER%:/shared_storage" ^
    -v //var/run/docker.sock:/var/run/docker.sock ^
    --restart unless-stopped ^
    disk-storage

if %ERRORLEVEL% NEQ 0 (
    echo %RED%Hata: Konteyner başlatılamadı.%NC%
    pause
    exit /b 1
)

echo [OK] Konteyner başarıyla oluşturuldu ve başlatıldı.

:: Bağlantı bilgilerini göster
:show_info
echo.
echo =================================
echo === Bağlantı Bilgileri ===
echo Yerel Ağ: http://localhost:5000

:: Yerel IP'yi al
for /f "tokens=14 delims= " %%i in ('ipconfig ^| findstr "IPv4"') do set "LOCAL_IP=%%i"
if defined LOCAL_IP (
    echo Yerel Ağ (Diğer Cihazlar): http://%LOCAL_IP%:5000
)

echo.
echo =================================
echo [TAMAMLANDI] Kurulum başarıyla tamamlandı!
echo Tarayıcınızda açılıyor...
echo =================================
start "" "http://localhost:5000"

echo.
echo Çıkmak için bir tuşa basın...
pause >nul
exit /b 0
    
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

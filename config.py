# ===========================================
# config.py - Konfigürasyon ayarları
# ===========================================

import os
from pathlib import Path
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

class Config:
    """Temel konfigürasyon sınıfı"""
    
    # ===========================================
    # Temel Flask Ayarları
    # ===========================================
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24)
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes', 'on']
    TESTING = False
    
    # ===========================================
    # Güvenlik Ayarları
    # ===========================================
    DEFAULT_PASSWORD = os.environ.get('DEFAULT_PASSWORD', '1234')
    PASSWORD_HASH = None  # Runtime'da generate_password_hash ile ayarlanacak
    SESSION_PERMANENT = False
    SESSION_TYPE = 'filesystem'
    
    # ===========================================
    # Dosya ve Depolama Ayarları
    # ===========================================
    # Ana paylaşım klasörü
    SHARED_FOLDER = os.environ.get('SHARED_FOLDER') or os.path.join(
        str(Path.home()), 'Downloads', 'DiskStorage'
    )
    
    # Depolama limiti (varsayılan 5GB)
    STORAGE_LIMIT = int(os.environ.get('STORAGE_LIMIT', 5 * 1024 * 1024 * 1024))
    
    # Yükleme ayarları
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB
    UPLOAD_FOLDER = SHARED_FOLDER
    ALLOWED_EXTENSIONS = set(os.environ.get('ALLOWED_EXTENSIONS', 
        'txt,pdf,png,jpg,jpeg,gif,zip,rar,doc,docx,xls,xlsx,ppt,pptx,mp3,mp4,avi,mkv').split(','))
    
    # Temp dosya ayarları
    TEMP_FOLDER = os.environ.get('TEMP_FOLDER') or os.path.join(SHARED_FOLDER, '.temp')
    
    # ===========================================
    # Ağ ve Sunucu Ayarları
    # ===========================================
    DEFAULT_PORT = int(os.environ.get('DEFAULT_PORT', 5000))
    HOST_IP = os.environ.get('HOST_IP', '0.0.0.0')
    
    # ZeroConf servisi ayarları
    SERVICE_NAME = os.environ.get('SERVICE_NAME', 'DiskStorage')
    SERVICE_TYPE = os.environ.get('SERVICE_TYPE', '_http._tcp.local.')
    
    # Timeout ayarları
    NETWORK_TIMEOUT = int(os.environ.get('NETWORK_TIMEOUT', 10))
    DISCOVERY_TIMEOUT = int(os.environ.get('DISCOVERY_TIMEOUT', 5))
    
    # ===========================================
    # RAR İşlemci Ayarları
    # ===========================================
    # RAR işlemci servisi etkin mi? (Docker tabanlı çözücüyü kullanılacak mı?)
    RAR_PROCESSOR_ENABLED = False  # Disable the RAR processor
    HAS_RARFILE = False
    HAS_UNRAR = False

    try:
        import rarfile
        HAS_RARFILE = True
        
        # On Windows, try to find WinRAR installation
        if os.name == 'nt':
            possible_paths = [
                r"C:\Program Files\WinRAR\UnRAR.exe",
                r"C:\Program Files (x86)\WinRAR\UnRAR.exe",
                r"C:\Program Files\WinRAR\Rar.exe",
                r"C:\Program Files (x86)\WinRAR\Rar.exe"
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    rarfile.UNRAR_TOOL = path
                    break
    except ImportError:
        HAS_RARFILE = False
        print("WARNING: 'rarfile' package not found. RAR support will be disabled.")
        print("Install with: pip install rarfile")
    
    # Disable unrar completely
    HAS_UNRAR = False
    
    # Eğer hiçbir RAR kütüphanesi yüklü değilse uyarı ver
    if not HAS_RARFILE and not HAS_UNRAR:
        print("UYARI: RAR dosyalarını işleyebilmek için 'rarfile' veya 'unrar' kütüphanesi yüklü değil.")
        print("Yüklemek için: pip install rarfile unrar")
    
    # Varsayılan olarak yerel işlemeyi etkinleştir (eğer kütüphane yüklüyse)
    LOCAL_RAR_PROCESSING = HAS_RARFILE or HAS_UNRAR
    
    # İşlem zaman aşımı (saniye)
    RAR_PROCESSOR_TIMEOUT = int(os.environ.get('RAR_PROCESSOR_TIMEOUT', '30'))
    
    # ===========================================
    # Relay Sunucu Ayarları
    # ===========================================
    RELAY_SERVERS = [
        {
            'url': os.environ.get('RELAY_SERVER_1', 'http://relay1.example.com:5000'),
            'status': 'unknown',
            'region': 'europe'
        },
        {
            'url': os.environ.get('RELAY_SERVER_2', 'http://relay2.example.com:5000'),
            'status': 'unknown',
            'region': 'america'
        }
    ]
    
    # Relay ayarları
    RELAY_ENABLED = os.environ.get('RELAY_ENABLED', 'false').lower() == 'true'
    RELAY_CAPACITY = int(os.environ.get('RELAY_CAPACITY', 100))
    RELAY_REGION = os.environ.get('RELAY_REGION', 'auto')
    
    # ===========================================
    # Cihaz Keşfi Ayarları
    # ===========================================
    DEVICE_DISCOVERY_ENABLED = os.environ.get('DEVICE_DISCOVERY_ENABLED', 'true').lower() == 'true'
    DEVICE_TIMEOUT = int(os.environ.get('DEVICE_TIMEOUT', 300))  # 5 dakika
    DEVICE_CLEANUP_INTERVAL = int(os.environ.get('DEVICE_CLEANUP_INTERVAL', 60))  # 1 dakika
    
    # ===========================================
    # Dosya İzleme Ayarları
    # ===========================================
    FILE_WATCHER_ENABLED = os.environ.get('FILE_WATCHER_ENABLED', 'true').lower() == 'true'
    SYNC_ENABLED = os.environ.get('SYNC_ENABLED', 'false').lower() == 'true'
    
    # ===========================================
    # Logging Ayarları
    # ===========================================
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    LOG_FILE = os.environ.get('LOG_FILE') or os.path.join(SHARED_FOLDER, 'app.log')
    LOG_MAX_SIZE = int(os.environ.get('LOG_MAX_SIZE', 10 * 1024 * 1024))  # 10MB
    LOG_BACKUP_COUNT = int(os.environ.get('LOG_BACKUP_COUNT', 5))
    
    # ===========================================
    # Performans Ayarları
    # ===========================================
    THREADED = os.environ.get('THREADED', 'true').lower() == 'true'
    PROCESSES = int(os.environ.get('PROCESSES', 1))
    
    # Önbellek ayarları
    CACHE_ENABLED = os.environ.get('CACHE_ENABLED', 'true').lower() == 'true'
    CACHE_TIMEOUT = int(os.environ.get('CACHE_TIMEOUT', 300))  # 5 dakika
    
    # ===========================================
    # Arşiv İşleme Ayarları
    # ===========================================
    ARCHIVE_PREVIEW_ENABLED = os.environ.get('ARCHIVE_PREVIEW_ENABLED', 'true').lower() == 'true'
    MAX_ARCHIVE_ENTRIES = int(os.environ.get('MAX_ARCHIVE_ENTRIES', 1000))
    ARCHIVE_CACHE_SIZE = int(os.environ.get('ARCHIVE_CACHE_SIZE', 100))
    
    # ===========================================
    # Güvenlik ve Erişim Kontrolü
    # ===========================================
    ALLOWED_IPS = os.environ.get('ALLOWED_IPS', '').split(',') if os.environ.get('ALLOWED_IPS') else []
    BLOCKED_IPS = os.environ.get('BLOCKED_IPS', '').split(',') if os.environ.get('BLOCKED_IPS') else []
    
    # Dosya türü kısıtlamaları
    BLOCKED_EXTENSIONS = set(os.environ.get('BLOCKED_EXTENSIONS', 
        'exe,bat,cmd,scr,vbs,js,jar').split(','))
    
    # Dizin traversal koruması
    PROTECT_TRAVERSAL = os.environ.get('PROTECT_TRAVERSAL', 'true').lower() == 'true'
    
    # ===========================================
    # API Ayarları
    # ===========================================
    API_ENABLED = os.environ.get('API_ENABLED', 'true').lower() == 'true'
    API_PREFIX = os.environ.get('API_PREFIX', '/api')
    API_RATE_LIMIT = os.environ.get('API_RATE_LIMIT', '100/hour')
    
    # CORS ayarları
    CORS_ENABLED = os.environ.get('CORS_ENABLED', 'true').lower() == 'true'
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    
    # ===========================================
    # Yardımcı Metodlar
    # ===========================================
    @staticmethod
    def init_app(app):
        """Flask uygulamasını konfigürasyonla başlat"""
        # Gerekli klasörleri oluştur
        os.makedirs(Config.SHARED_FOLDER, exist_ok=True)
        os.makedirs(Config.TEMP_FOLDER, exist_ok=True)
        
        # Log klasörünü oluştur
        log_dir = os.path.dirname(Config.LOG_FILE)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
    
    @classmethod
    def get_storage_info(cls):
        """Depolama bilgilerini döndür"""
        import shutil
        
        total, used, free = shutil.disk_usage(cls.SHARED_FOLDER)
        
        return {
            'total_disk': total,
            'used_disk': used,
            'free_disk': free,
            'storage_limit': cls.STORAGE_LIMIT,
            'shared_folder': cls.SHARED_FOLDER
        }
    
    @classmethod
    def is_allowed_file(cls, filename):
        """Dosya uzantısının izin verilen türde olup olmadığını kontrol et"""
        if not filename:
            return False
            
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        # Yasaklı uzantıları kontrol et
        if ext in cls.BLOCKED_EXTENSIONS:
            return False
            
        # İzin verilen uzantıları kontrol et (boşsa hepsine izin ver)
        if cls.ALLOWED_EXTENSIONS:
            return ext in cls.ALLOWED_EXTENSIONS
            
        return True

class DevelopmentConfig(Config):
    """Geliştirme ortamı konfigürasyonu"""
    DEBUG = True
    TESTING = False
    LOG_LEVEL = 'DEBUG'
    
    # Geliştirme için daha düşük limitler
    STORAGE_LIMIT = 1 * 1024 * 1024 * 1024  # 1GB
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB

class ProductionConfig(Config):
    """Üretim ortamı konfigürasyonu"""
    DEBUG = False
    TESTING = False
    
    # Üretim için güvenlik artırımları
    PROTECT_TRAVERSAL = True
    
    # Daha katı dosya kontrolleri
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'rar'}
    BLOCKED_EXTENSIONS = {'exe', 'bat', 'cmd', 'scr', 'vbs', 'js', 'jar', 'sh', 'ps1'}

class TestingConfig(Config):
    """Test ortamı konfigürasyonu"""
    TESTING = True
    DEBUG = True
    
    # Test için geçici klasör
    SHARED_FOLDER = '/tmp/test_disk_storage'
    STORAGE_LIMIT = 100 * 1024 * 1024  # 100MB
    
    # Test için hızlı ayarlar
    DEVICE_TIMEOUT = 10
    DISCOVERY_TIMEOUT = 1
    CACHE_TIMEOUT = 10

# Konfigürasyon seçimi
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config(config_name=None):
    """Konfigürasyon sınıfını döndür"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    return config_map.get(config_name, DevelopmentConfig)

# ===========================================
# .env dosyası örneği
# ===========================================

ENV_EXAMPLE = """
# .env dosyası örneği
# Bu dosyayı .env olarak kaydedin ve değerleri düzenleyin

# Flask ayarları
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
DEFAULT_PASSWORD=1234

# Dosya ayarları
SHARED_FOLDER=/path/to/your/shared/folder
STORAGE_LIMIT=5368709120
MAX_CONTENT_LENGTH=16777216

# Ağ ayarları
DEFAULT_PORT=5000
HOST_IP=0.0.0.0

# RAR işlemci
RAR_PROCESSOR_ENABLED=false
RAR_PROCESSOR_URL=http://localhost:5001

# Cihaz keşfi
DEVICE_DISCOVERY_ENABLED=true
DEVICE_TIMEOUT=300

# Logging
LOG_LEVEL=INFO
LOG_FILE=app.log

# Güvenlik
ALLOWED_IPS=192.168.1.0/24,10.0.0.0/8
BLOCKED_EXTENSIONS=exe,bat,scr

# API
API_ENABLED=true
CORS_ENABLED=true
"""

if __name__ == '__main__':
    # Konfigürasyon test kodu
    config = get_config()
    print(f"Config class: {config.__name__}")
    print(f"Shared folder: {config.SHARED_FOLDER}")
    print(f"Storage limit: {config.STORAGE_LIMIT}")
    print(f"Debug mode: {config.DEBUG}")
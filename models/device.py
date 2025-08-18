from dataclasses import dataclass
from typing import List
from datetime import datetime

@dataclass
class Device:
    """Cihaz bilgilerini tutan sınıf"""
    device_id: str
    ip: str
    port: int
    shared_folders: List[str]
    last_seen: float = 0.0
    is_online: bool = False
    is_relay: bool = False
    relay_capacity: int = 0
    region: str = ''
    
    def to_dict(self):
        """Cihaz bilgilerini sözlük olarak döndürür"""
        return {
            'device_id': self.device_id,
            'ip': self.ip,
            'port': self.port,
            'shared_folders': self.shared_folders,
            'last_seen': self.last_seen,
            'is_online': self.is_online,
            'is_relay': self.is_relay,
            'relay_capacity': self.relay_capacity,
            'region': self.region
        }
    
    def update_last_seen(self):
        """Son görülme zamanını günceller"""
        self.last_seen = datetime.now().timestamp()
        self.is_online = True
    
    def check_online_status(self, timeout=300):
        """Cihazın çevrimiçi durumunu kontrol eder"""
        current_time = datetime.now().timestamp()
        self.is_online = (current_time - self.last_seen) < timeout
        return self.is_online

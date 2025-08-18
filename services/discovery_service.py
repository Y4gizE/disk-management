
import time
import socket
import threading
from zeroconf import ServiceBrowser, Zeroconf
from config import Config
from models.device import Device

class DiscoveryService:
    def __init__(self, network_service):
        self.network_service = network_service
        self.zeroconf = None
        self.browser = None
        self.running = False
        self.thread = None
    
    def start_discovery_thread(self):
        """Start the discovery service in a background thread"""
        if self.running:
            return
            
        self.running = True
        self.zeroconf = Zeroconf()
        self.listener = self.DeviceListener(self.network_service)
        self.browser = ServiceBrowser(self.zeroconf, "_http._tcp.local.", self.listener)
        
        def discovery_loop():
            try:
                while self.running:
                    time.sleep(1)
            except Exception as e:
                print(f"Discovery thread error: {e}")
            finally:
                self.zeroconf.close()
                
        self.thread = threading.Thread(target=discovery_loop, daemon=True)
        self.thread.start()
        return True
    
    def stop_discovery(self):
        """Stop the discovery service"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None
        if self.zeroconf:
            self.zeroconf.close()
            self.zeroconf = None
    
    def discover_devices(self):
        """Discover other devices on the local network"""
        if not self.zeroconf:
            self.start_discovery_thread()
        return []
    
    class DeviceListener:
        def __init__(self, network_service):
            self.network_service = network_service
            
        def remove_service(self, zeroconf, type, name):
            print(f"Service {name} removed")
            
        def add_service(self, zeroconf, type, name):
            info = zeroconf.get_service_info(type, name)
            if info:
                print(f"Service {name} added, service info: {info}")
                
        def update_service(self, zeroconf, type, name):
            # This method is called when a service is updated
            info = zeroconf.get_service_info(type, name)
            if info:
                print(f"Service {name} updated, service info: {info}")
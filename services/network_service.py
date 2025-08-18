import socket
import logging
from typing import Optional, Dict, Any
from zeroconf import ServiceInfo, Zeroconf, IPVersion
import ifaddr
import ipaddress

class NetworkService:
    def __init__(self, service_name: str, service_port: int, service_properties: Dict[str, str] = None):
        """
        Initialize the NetworkService for handling network discovery and information.
        
        Args:
            service_name (str): Name of the service for Zeroconf
            service_port (int): Port the service is running on
            service_properties (Dict[str, str], optional): Additional service properties
        """
        self.service_name = service_name
        self.service_port = service_port
        self.service_properties = service_properties or {}
        self.zeroconf = None
        self.service_info = None
        self.logger = logging.getLogger(__name__)
    
    def get_local_ip(self) -> str:
        """Get the local IP address of the machine."""
        try:
            # Create a socket connection to a public DNS server
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1)
            # Doesn't actually connect, just gets the local IP that would be used
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception as e:
            self.logger.error(f"Error getting local IP: {e}")
            return "127.0.0.1"
    
    def get_network_interfaces(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all network interfaces.
        
        Returns:
            Dict containing interface information keyed by interface name
        """
        interfaces = {}
        try:
            for adapter in ifaddr.get_adapters():
                for ip in adapter.ips:
                    if ip.is_IPv4 and not ipaddress.ip_address(ip.ip).is_loopback:
                        interfaces[adapter.nice_name] = {
                            'ip': ip.ip,
                            'netmask': ip.network_prefix,
                            'name': adapter.nice_name,
                            'friendly_name': adapter.name
                        }
                        break
        except Exception as e:
            self.logger.error(f"Error getting network interfaces: {e}")
        
        return interfaces
    
    def register_service(self) -> bool:
        """Register the service using Zeroconf."""
        try:
            local_ip = self.get_local_ip()
            if not local_ip or local_ip == "127.0.0.1":
                self.logger.error("Could not determine local IP address")
                return False
            
            service_type = "_http._tcp.local."
            service_name = f"{self.service_name}._http._tcp.local."
            
            self.service_info = ServiceInfo(
                service_type,
                service_name,
                addresses=[socket.inet_aton(local_ip)],
                port=self.service_port,
                properties=self.service_properties,
                server=f"{socket.gethostname()}.local.",
            )
            
            self.zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
            self.zeroconf.register_service(self.service_info)
            self.logger.info(f"Registered service {service_name} at {local_ip}:{self.service_port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to register service: {e}")
            return False
    
    def unregister_service(self) -> None:
        """Unregister the Zeroconf service."""
        try:
            if self.zeroconf and self.service_info:
                self.zeroconf.unregister_service(self.service_info)
                self.zeroconf.close()
                self.logger.info("Unregistered service")
        except Exception as e:
            self.logger.error(f"Error unregistering service: {e}")
        finally:
            self.zeroconf = None
            self.service_info = None
    
    def discover_services(self, service_type: str = "_http._tcp.local.", timeout: int = 5) -> list:
        """
        Discover services of the specified type on the local network.
        
        Args:
            service_type (str): The service type to discover (default: _http._tcp.local.)
            timeout (int): Time in seconds to wait for responses
            
        Returns:
            List of discovered services with their information
        """
        services = []
        zeroconf = None
        
        class ServiceListener:
            def __init__(self):
                self.services = []
                
            def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                info = zc.get_service_info(type_, name)
                if info:
                    service_info = {
                        'name': name.replace(f".{service_type}", ""),
                        'type': type_,
                        'addresses': [socket.inet_ntoa(addr) for addr in info.addresses],
                        'port': info.port,
                        'properties': {}
                    }
                    
                    if info.properties:
                        for key, value in info.properties.items():
                            try:
                                service_info['properties'][key.decode()] = (
                                    value.decode() if isinstance(value, bytes) else value
                                )
                            except Exception as e:
                                self.logger.warning(f"Error decoding property {key}: {e}")
                    
                    self.services.append(service_info)
        
        try:
            listener = ServiceListener()
            zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
            browser = ServiceBrowser(zeroconf, service_type, listener)
            
            # Wait for responses
            import time
            time.sleep(timeout)
            
            services = listener.services
            self.logger.debug(f"Discovered {len(services)} services of type {service_type}")
            
        except Exception as e:
            self.logger.error(f"Error discovering services: {e}")
            
        finally:
            if zeroconf:
                zeroconf.close()
                
        return services
    
    def get_public_ip(self) -> Optional[str]:
        """
        Get the public IP address of the machine.
        
        Returns:
            str: Public IP address or None if could not be determined
        """
        try:
            import requests
            response = requests.get('https://api.ipify.org?format=json', timeout=5)
            response.raise_for_status()
            return response.json().get('ip')
        except Exception as e:
            self.logger.error(f"Error getting public IP: {e}")
            return None

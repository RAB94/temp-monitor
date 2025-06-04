#!/usr/bin/env python3
"""
Network Utilities
=================

Network-related utility functions for interface detection, validation,
and network topology discovery.
"""

import socket
import subprocess
import asyncio
import logging
import time
import ipaddress
import psutil
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
import json

logger = logging.getLogger(__name__)

@dataclass
class NetworkInterface:
    """Network interface information"""
    name: str
    addresses: List[str]
    status: str
    mtu: int
    speed: Optional[int]
    duplex: Optional[str]
    type: str
    statistics: Dict[str, int]

@dataclass
class RouteInfo:
    """Network route information"""
    destination: str
    gateway: str
    interface: str
    metric: int

class NetworkInterfaceMonitor:
    """Monitor network interfaces and their status"""
    
    def __init__(self):
        self.interfaces = {}
        self.last_stats = {}
    
    def get_all_interfaces(self) -> Dict[str, NetworkInterface]:
        """Get all network interfaces with detailed information"""
        
        interfaces = {}
        
        try:
            # Get interface addresses
            if_addrs = psutil.net_if_addrs()
            if_stats = psutil.net_if_stats()
            io_counters = psutil.net_io_counters(pernic=True)
            
            for interface_name in if_addrs:
                # Skip loopback and virtual interfaces by default
                if self._should_monitor_interface(interface_name):
                    addresses = []
                    
                    for addr in if_addrs[interface_name]:
                        if addr.family == socket.AF_INET:
                            addresses.append(addr.address)
                        elif addr.family == socket.AF_INET6:
                            addresses.append(addr.address)
                    
                    # Get interface stats
                    stats = if_stats.get(interface_name)
                    io_stats = io_counters.get(interface_name)
                    
                    # Get additional interface info
                    interface_info = self._get_interface_details(interface_name)
                    
                    interface = NetworkInterface(
                        name=interface_name,
                        addresses=addresses,
                        status='up' if stats and stats.isup else 'down',
                        mtu=stats.mtu if stats else 0,
                        speed=stats.speed if stats else None,
                        duplex=stats.duplex.name if stats and stats.duplex else None,
                        type=interface_info.get('type', 'unknown'),
                        statistics={
                            'bytes_sent': io_stats.bytes_sent if io_stats else 0,
                            'bytes_recv': io_stats.bytes_recv if io_stats else 0,
                            'packets_sent': io_stats.packets_sent if io_stats else 0,
                            'packets_recv': io_stats.packets_recv if io_stats else 0,
                            'errin': io_stats.errin if io_stats else 0,
                            'errout': io_stats.errout if io_stats else 0,
                            'dropin': io_stats.dropin if io_stats else 0,
                            'dropout': io_stats.dropout if io_stats else 0
                        }
                    )
                    
                    interfaces[interface_name] = interface
            
            return interfaces
            
        except Exception as e:
            logger.error(f"Error getting network interfaces: {e}")
            return {}
    
    def _should_monitor_interface(self, interface_name: str) -> bool:
        """Determine if interface should be monitored"""
        
        # Skip loopback interfaces
        if interface_name.startswith(('lo', 'lo0')):
            return False
        
        # Skip Docker interfaces
        if interface_name.startswith(('docker', 'br-', 'veth')):
            return False
        
        # Skip virtual interfaces
        if interface_name.startswith(('tun', 'tap', 'virbr')):
            return False
        
        return True
    
    def _get_interface_details(self, interface_name: str) -> Dict[str, Any]:
        """Get additional interface details"""
        
        details = {'type': 'unknown'}
        
        try:
            # Try to determine interface type
            if interface_name.startswith(('eth', 'en')):
                details['type'] = 'ethernet'
            elif interface_name.startswith(('wlan', 'wifi', 'wl')):
                details['type'] = 'wifi'
            elif interface_name.startswith(('ppp', 'wwan')):
                details['type'] = 'cellular'
            elif interface_name.startswith('usb'):
                details['type'] = 'usb'
            
            # Get additional info from /sys/class/net on Linux
            sys_path = Path(f"/sys/class/net/{interface_name}")
            if sys_path.exists():
                # Read carrier status
                carrier_path = sys_path / "carrier"
                if carrier_path.exists():
                    try:
                        with open(carrier_path, 'r') as f:
                            details['carrier'] = f.read().strip() == '1'
                    except:
                        pass
                
                # Read speed
                speed_path = sys_path / "speed"
                if speed_path.exists():
                    try:
                        with open(speed_path, 'r') as f:
                            details['link_speed'] = int(f.read().strip())
                    except:
                        pass
                
                # Read duplex
                duplex_path = sys_path / "duplex"
                if duplex_path.exists():
                    try:
                        with open(duplex_path, 'r') as f:
                            details['duplex'] = f.read().strip()
                    except:
                        pass
        
        except Exception as e:
            logger.debug(f"Error getting interface details for {interface_name}: {e}")
        
        return details
    
    def get_interface_utilization(self, interface_name: str) -> Dict[str, float]:
        """Calculate interface utilization"""
        
        try:
            io_counters = psutil.net_io_counters(pernic=True)
            current_stats = io_counters.get(interface_name)
            
            if not current_stats:
                return {'rx_utilization': 0.0, 'tx_utilization': 0.0}
            
            current_time = time.time()
            
            # Calculate utilization if we have previous stats
            if interface_name in self.last_stats:
                last_stats, last_time = self.last_stats[interface_name]
                time_delta = current_time - last_time
                
                if time_delta > 0:
                    # Calculate bytes per second
                    rx_bps = (current_stats.bytes_recv - last_stats.bytes_recv) / time_delta
                    tx_bps = (current_stats.bytes_sent - last_stats.bytes_sent) / time_delta
                    
                    # Get interface speed
                    if_stats = psutil.net_if_stats().get(interface_name)
                    speed_bps = (if_stats.speed * 1024 * 1024 / 8) if if_stats and if_stats.speed else 1000000000  # Default to 1Gbps
                    
                    utilization = {
                        'rx_utilization': min(100.0, (rx_bps / speed_bps) * 100),
                        'tx_utilization': min(100.0, (tx_bps / speed_bps) * 100),
                        'rx_bps': rx_bps,
                        'tx_bps': tx_bps,
                        'interface_speed_bps': speed_bps
                    }
                else:
                    utilization = {'rx_utilization': 0.0, 'tx_utilization': 0.0}
            else:
                utilization = {'rx_utilization': 0.0, 'tx_utilization': 0.0}
            
            # Store current stats for next calculation
            self.last_stats[interface_name] = (current_stats, current_time)
            
            return utilization
            
        except Exception as e:
            logger.error(f"Error calculating interface utilization: {e}")
            return {'rx_utilization': 0.0, 'tx_utilization': 0.0}

class NetworkTopologyDiscovery:
    """Discover network topology and routing information"""
    
    @staticmethod
    async def get_routing_table() -> List[RouteInfo]:
        """Get system routing table"""
        
        routes = []
        
        try:
            # Try different commands based on OS
            commands = [
                ['ip', 'route', 'show'],  # Linux
                ['route', '-n'],          # Linux/macOS
                ['netstat', '-rn']        # Cross-platform
            ]
            
            for cmd in commands:
                try:
                    result = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await result.communicate()
                    
                    if result.returncode == 0:
                        routes = NetworkTopologyDiscovery._parse_routes(
                            stdout.decode(), cmd[0]
                        )
                        break
                        
                except (FileNotFoundError, OSError):
                    continue
            
            return routes
            
        except Exception as e:
            logger.error(f"Error getting routing table: {e}")
            return []
    
    @staticmethod
    def _parse_routes(output: str, command: str) -> List[RouteInfo]:
        """Parse routing table output"""
        
        routes = []
        lines = output.strip().split('\n')
        
        try:
            if command == 'ip':
                # Parse 'ip route' output
                for line in lines:
                    if 'via' in line or 'dev' in line:
                        parts = line.split()
                        if len(parts) >= 3:
                            destination = parts[0] if parts[0] != 'default' else '0.0.0.0/0'
                            gateway = ''
                            interface = ''
                            metric = 0
                            
                            for i, part in enumerate(parts):
                                if part == 'via' and i + 1 < len(parts):
                                    gateway = parts[i + 1]
                                elif part == 'dev' and i + 1 < len(parts):
                                    interface = parts[i + 1]
                                elif part == 'metric' and i + 1 < len(parts):
                                    metric = int(parts[i + 1])
                            
                            routes.append(RouteInfo(
                                destination=destination,
                                gateway=gateway,
                                interface=interface,
                                metric=metric
                            ))
            
            elif command in ['route', 'netstat']:
                # Parse traditional route output
                for line in lines[1:]:  # Skip header
                    parts = line.split()
                    if len(parts) >= 8:
                        destination = parts[0]
                        gateway = parts[1]
                        interface = parts[-1]
                        metric = int(parts[4]) if parts[4].isdigit() else 0
                        
                        routes.append(RouteInfo(
                            destination=destination,
                            gateway=gateway,
                            interface=interface,
                            metric=metric
                        ))
        
        except Exception as e:
            logger.error(f"Error parsing routes: {e}")
        
        return routes
    
    @staticmethod
    async def discover_gateway() -> Optional[str]:
        """Discover default gateway"""
        
        try:
            routes = await NetworkTopologyDiscovery.get_routing_table()
            
            for route in routes:
                if route.destination in ['0.0.0.0/0', 'default']:
                    return route.gateway
            
            return None
            
        except Exception as e:
            logger.error(f"Error discovering gateway: {e}")
            return None
    
    @staticmethod
    async def discover_dns_servers() -> List[str]:
        """Discover configured DNS servers"""
        
        dns_servers = []
        
        try:
            # Try reading /etc/resolv.conf on Unix systems
            resolv_conf = Path('/etc/resolv.conf')
            if resolv_conf.exists():
                with open(resolv_conf, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('nameserver'):
                            parts = line.split()
                            if len(parts) >= 2:
                                dns_servers.append(parts[1])
            
            # Fallback: use system DNS resolution
            if not dns_servers:
                result = await asyncio.create_subprocess_exec(
                    'nslookup', 'google.com',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode == 0:
                    output = stdout.decode()
                    for line in output.split('\n'):
                        if 'Server:' in line:
                            server = line.split('Server:')[1].strip()
                            if server and server != '127.0.0.1':
                                dns_servers.append(server)
                            break
            
            return dns_servers
            
        except Exception as e:
            logger.error(f"Error discovering DNS servers: {e}")
            return ['8.8.8.8', '1.1.1.1']  # Fallback

class NetworkValidator:
    """Validate network configurations and connectivity"""
    
    @staticmethod
    def validate_ip_address(ip: str) -> bool:
        """Validate IP address"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_hostname(hostname: str) -> bool:
        """Validate hostname"""
        try:
            # Basic hostname validation
            if not hostname or len(hostname) > 253:
                return False
            
            if hostname[-1] == ".":
                hostname = hostname[:-1]
            
            import re
            allowed = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$")
            
            return all(allowed.match(label) for label in hostname.split("."))
            
        except Exception:
            return False
    
    @staticmethod
    def validate_port(port: int) -> bool:
        """Validate port number"""
        return 1 <= port <= 65535
    
    @staticmethod
    def validate_target(target: str) -> Dict[str, Any]:
        """Validate monitoring target"""
        
        result = {
            'valid': False,
            'type': 'unknown',
            'ip_address': None,
            'hostname': None,
            'error': None
        }
        
        try:
            # Check if it's an IP address
            if NetworkValidator.validate_ip_address(target):
                result.update({
                    'valid': True,
                    'type': 'ip',
                    'ip_address': target
                })
            
            # Check if it's a hostname
            elif NetworkValidator.validate_hostname(target):
                try:
                    ip = socket.gethostbyname(target)
                    result.update({
                        'valid': True,
                        'type': 'hostname',
                        'hostname': target,
                        'ip_address': ip
                    })
                except socket.gaierror as e:
                    result['error'] = f"DNS resolution failed: {e}"
            
            else:
                result['error'] = "Invalid IP address or hostname format"
        
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    @staticmethod
    async def check_port_connectivity(host: str, port: int, timeout: float = 5.0) -> bool:
        """Check if a port is reachable"""
        
        try:
            future = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(future, timeout=timeout)
            writer.close()
            await writer.wait_closed()
            return True
            
        except Exception:
            return False

class NetworkEnvironmentDetector:
    """Detect network environment characteristics"""
    
    @staticmethod
    def detect_network_type() -> str:
        """Detect primary network connection type"""
        
        try:
            interfaces = psutil.net_if_stats()
            
            # Check for active interfaces
            active_interfaces = [
                name for name, stats in interfaces.items()
                if stats.isup and not name.startswith(('lo', 'docker', 'br-'))
            ]
            
            for interface in active_interfaces:
                if 'wlan' in interface.lower() or 'wifi' in interface.lower():
                    return 'wifi'
                elif 'eth' in interface.lower() or 'en' in interface.lower():
                    return 'ethernet'
                elif 'ppp' in interface.lower() or 'wwan' in interface.lower():
                    return 'cellular'
                elif 'usb' in interface.lower():
                    return 'usb'
            
            return 'unknown'
            
        except Exception as e:
            logger.error(f"Error detecting network type: {e}")
            return 'unknown'
    
    @staticmethod
    def detect_deployment_environment() -> Dict[str, Any]:
        """Detect deployment environment characteristics"""
        
        environment = {
            'is_container': False,
            'is_cloud': False,
            'is_edge_device': False,
            'platform': 'unknown',
            'constraints': []
        }
        
        try:
            import platform
            import os
            
            # Basic platform detection
            environment['platform'] = platform.system().lower()
            
            # Container detection
            if os.path.exists('/.dockerenv') or os.path.exists('/proc/1/cgroup'):
                environment['is_container'] = True
                environment['constraints'].append('container_limits')
            
            # Cloud detection (basic)
            cloud_indicators = [
                '/sys/hypervisor/uuid',
                '/sys/class/dmi/id/product_name'
            ]
            
            for indicator in cloud_indicators:
                if os.path.exists(indicator):
                    try:
                        with open(indicator, 'r') as f:
                            content = f.read().lower()
                            if any(cloud in content for cloud in ['amazon', 'google', 'microsoft', 'azure']):
                                environment['is_cloud'] = True
                                break
                    except:
                        pass
            
            # Edge device detection
            edge_indicators = [
                'raspberry pi' in platform.platform().lower(),
                os.path.exists('/opt/vc/bin/vcgencmd'),  # Raspberry Pi
                psutil.virtual_memory().total < 2 * 1024**3,  # Less than 2GB RAM
            ]
            
            if any(edge_indicators):
                environment['is_edge_device'] = True
                environment['constraints'].extend(['limited_memory', 'limited_cpu'])
            
            # Additional constraints
            if psutil.virtual_memory().total < 1024**3:  # Less than 1GB
                environment['constraints'].append('very_limited_memory')
            
            if psutil.cpu_count() <= 2:
                environment['constraints'].append('limited_cpu_cores')
        
        except Exception as e:
            logger.error(f"Error detecting environment: {e}")
        
        return environment
    
    @staticmethod
    def get_optimal_monitoring_config() -> Dict[str, Any]:
        """Get optimal monitoring configuration based on environment"""
        
        environment = NetworkEnvironmentDetector.detect_deployment_environment()
        
        config = {
            'monitoring_interval': 30,
            'timeout': 10,
            'max_targets': 10,
            'enable_enhanced_metrics': True,
            'enable_ai': True,
            'ai_config': {
                'model_complexity': 'standard',
                'training_frequency': 'hourly'
            }
        }
        
        # Adjust for edge devices
        if environment['is_edge_device']:
            config.update({
                'monitoring_interval': 60,
                'timeout': 15,
                'max_targets': 5,
                'enable_enhanced_metrics': True,
                'ai_config': {
                    'model_complexity': 'lightweight',
                    'training_frequency': 'daily'
                }
            })
        
        # Adjust for containers
        if environment['is_container']:
            config.update({
                'timeout': 5,
                'max_targets': 8
            })
        
        # Adjust for memory constraints
        if 'very_limited_memory' in environment['constraints']:
            config.update({
                'enable_enhanced_metrics': False,
                'ai_config': {
                    'model_complexity': 'minimal',
                    'training_frequency': 'weekly'
                }
            })
        
        return config

# Utility functions

def get_default_interface() -> Optional[str]:
    """Get default network interface"""
    
    try:
        # Get default route
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        
        # Find first active non-loopback interface
        for interface_name, interface_stats in stats.items():
            if (interface_stats.isup and 
                not interface_name.startswith(('lo', 'docker', 'br-')) and
                interface_name in addrs):
                return interface_name
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting default interface: {e}")
        return None

def get_local_ip() -> Optional[str]:
    """Get local IP address"""
    
    try:
        # Connect to a remote address to determine local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    
    except Exception:
        return None

async def ping_host(host: str, count: int = 1) -> Dict[str, Any]:
    """Simple ping utility"""
    
    try:
        cmd = ['ping', '-c', str(count), host]
        
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await result.communicate()
        
        success = result.returncode == 0
        output = stdout.decode() if success else stderr.decode()
        
        return {
            'success': success,
            'output': output,
            'returncode': result.returncode
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'returncode': -1
        }

def format_bytes(bytes_value: int) -> str:
    """Format bytes to human readable string"""
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"

def calculate_network_score(metrics: Dict[str, float]) -> float:
    """Calculate overall network health score"""
    
    score = 100.0
    
    # Latency scoring (0-40 points)
    latency = metrics.get('icmp_ping_time', 0)
    if latency > 0:
        if latency <= 20:
            latency_score = 40
        elif latency <= 50:
            latency_score = 30
        elif latency <= 100:
            latency_score = 20
        elif latency <= 200:
            latency_score = 10
        else:
            latency_score = 0
    else:
        latency_score = 0
    
    # Packet loss scoring (0-30 points)
    packet_loss = metrics.get('packet_loss', 0)
    if packet_loss == 0:
        loss_score = 30
    elif packet_loss <= 1:
        loss_score = 25
    elif packet_loss <= 3:
        loss_score = 15
    elif packet_loss <= 5:
        loss_score = 5
    else:
        loss_score = 0
    
    # Jitter scoring (0-20 points)
    jitter = metrics.get('jitter', 0)
    if jitter <= 1:
        jitter_score = 20
    elif jitter <= 5:
        jitter_score = 15
    elif jitter <= 10:
        jitter_score = 10
    elif jitter <= 20:
        jitter_score = 5
    else:
        jitter_score = 0
    
    # Connection errors scoring (0-10 points)
    errors = metrics.get('connection_errors', 0)
    if errors == 0:
        error_score = 10
    elif errors <= 2:
        error_score = 5
    else:
        error_score = 0
    
    total_score = latency_score + loss_score + jitter_score + error_score
    
    return min(100.0, max(0.0, total_score))

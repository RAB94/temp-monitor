#!/usr/bin/env python3
"""
Enhanced Network Metrics Collector
==================================

Comprehensive network health metrics collection including:
- Advanced TCP/UDP connection analysis
- QoS metrics (jitter, MOS, burst loss)
- Interface-level statistics
- Application-layer performance
- Network path analysis
- SNMP integration capabilities
- Modern streaming telemetry support
"""

import asyncio
import logging
import socket
import subprocess
import time
import statistics
import struct
import json
import aiohttp
import psutil
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from pathlib import Path
import ssl

logger = logging.getLogger(__name__)

@dataclass
class EnhancedNetworkMetrics:
    """Enhanced network metrics data structure"""
    timestamp: float
    target_host: str
    
    # Core connectivity metrics
    tcp_handshake_time: float
    icmp_ping_time: float
    dns_resolve_time: float
    
    # Enhanced latency metrics
    tcp_connect_time: float
    tcp_ssl_handshake_time: float
    http_response_time: float
    http_first_byte_time: float
    
    # Quality metrics
    packet_loss: float
    jitter: float
    burst_loss_rate: float
    out_of_order_packets: float
    duplicate_packets: float
    
    # Throughput metrics
    bandwidth_download: float
    bandwidth_upload: float
    concurrent_connections: int
    connection_setup_rate: float
    
    # Application metrics
    http_status_code: int
    http_content_length: int
    certificate_days_remaining: int
    redirect_count: int
    
    # Interface metrics
    interface_utilization: float
    interface_errors: int
    interface_drops: int
    interface_collisions: int
    
    # Path analysis
    hop_count: int
    path_mtu: int
    route_changes: int
    
    # Quality of Service
    mos_score: float  # Mean Opinion Score for voice quality
    r_factor: float   # R-factor for voice quality
    delay_variation: float
    
    # Error tracking
    connection_errors: int
    dns_errors: int
    timeout_errors: int
    
    # Metadata
    source_interface: str
    network_type: str
    measurement_duration: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with proper handling of None values"""
        result = asdict(self)
        # Replace None values with appropriate defaults
        for key, value in result.items():
            if value is None:
                if key.endswith('_time') or key.endswith('_rate') or key == 'jitter':
                    result[key] = 0.0
                elif key.endswith('_count') or key.endswith('_errors'):
                    result[key] = 0
                elif key == 'mos_score':
                    result[key] = 0.0
                elif key == 'http_status_code':
                    result[key] = 0
        return result

class QualityCalculator:
    """Calculate network quality metrics like MOS and R-factor"""
    
    @staticmethod
    def calculate_mos_score(latency_ms: float, jitter_ms: float, 
                          packet_loss_percent: float) -> float:
        """Calculate Mean Opinion Score (MOS) for voice quality"""
        
        # ITU-T G.107 E-model simplified calculation
        # R-factor calculation
        r_factor = QualityCalculator.calculate_r_factor(
            latency_ms, jitter_ms, packet_loss_percent
        )
        
        # Convert R-factor to MOS
        if r_factor < 0:
            return 1.0
        elif r_factor > 100:
            return 4.4
        elif r_factor < 60:
            return 1.0 + 0.035 * r_factor + 7e-6 * r_factor * (r_factor - 60) * (100 - r_factor)
        else:
            return 1.0 + 0.035 * r_factor + 7e-6 * r_factor * (r_factor - 60) * (100 - r_factor)
    
    @staticmethod
    def calculate_r_factor(latency_ms: float, jitter_ms: float, 
                          packet_loss_percent: float) -> float:
        """Calculate R-factor for voice quality assessment"""
        
        # Base R-factor
        r0 = 94.2
        
        # Impairment due to delay
        if latency_ms < 160:
            id_factor = 0
        else:
            id_factor = 0.024 * latency_ms + 0.11 * (latency_ms - 177.3) * (latency_ms > 177.3)
        
        # Impairment due to packet loss
        ie_factor = 0
        if packet_loss_percent > 0:
            ie_factor = 11 + 40 * np.log(1 + 10 * packet_loss_percent / 100)
        
        # Impairment due to jitter (simplified)
        ij_factor = min(jitter_ms * 0.1, 10)  # Cap at 10
        
        # Calculate R-factor
        r_factor = r0 - id_factor - ie_factor - ij_factor
        
        return max(0, min(100, r_factor))

class HTTPMetricsCollector:
    """Collect HTTP-specific metrics"""
    
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.session = None
    
    async def initialize(self):
        """Initialize HTTP session"""
        
        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=10,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
    
    async def collect_http_metrics(self, url: str) -> Dict[str, Any]:
        """Collect comprehensive HTTP metrics"""
        
        metrics = {
            'http_response_time': 0.0,
            'http_first_byte_time': 0.0,
            'http_status_code': 0,
            'http_content_length': 0,
            'certificate_days_remaining': 0,
            'redirect_count': 0,
            'tcp_connect_time': 0.0,
            'tcp_ssl_handshake_time': 0.0
        }
        
        if not self.session:
            return metrics
        
        start_time = time.perf_counter()
        
        try:
            # Custom connector to measure connection times
            trace_config = aiohttp.TraceConfig()
            
            connection_start = None
            dns_end = None
            connection_end = None
            ssl_end = None
            first_byte_time = None
            
            async def on_dns_resolvehost_start(session, trace_config_ctx, params):
                nonlocal connection_start
                connection_start = time.perf_counter()
            
            async def on_dns_resolvehost_end(session, trace_config_ctx, params):
                nonlocal dns_end
                dns_end = time.perf_counter()
            
            async def on_connection_create_end(session, trace_config_ctx, params):
                nonlocal connection_end
                connection_end = time.perf_counter()
            
            async def on_connection_ssl_end(session, trace_config_ctx, params):
                nonlocal ssl_end
                ssl_end = time.perf_counter()
            
            async def on_response_chunk_received(session, trace_config_ctx, params):
                nonlocal first_byte_time
                if first_byte_time is None:
                    first_byte_time = time.perf_counter()
            
            trace_config.on_dns_resolvehost_start.append(on_dns_resolvehost_start)
            trace_config.on_dns_resolvehost_end.append(on_dns_resolvehost_end)
            trace_config.on_connection_create_end.append(on_connection_create_end)
            trace_config.on_connection_ssl_end.append(on_connection_ssl_end)
            trace_config.on_response_chunk_received.append(on_response_chunk_received)
            
            # Make the request
            async with self.session.get(url, trace_configs=[trace_config], 
                                      allow_redirects=True) as response:
                
                content = await response.read()
                end_time = time.perf_counter()
                
                # Calculate timing metrics
                metrics['http_response_time'] = (end_time - start_time) * 1000
                
                if first_byte_time:
                    metrics['http_first_byte_time'] = (first_byte_time - start_time) * 1000
                
                if connection_start and connection_end:
                    metrics['tcp_connect_time'] = (connection_end - connection_start) * 1000
                
                if connection_end and ssl_end:
                    metrics['tcp_ssl_handshake_time'] = (ssl_end - connection_end) * 1000
                
                # Response metrics
                metrics['http_status_code'] = response.status
                metrics['http_content_length'] = len(content)
                metrics['redirect_count'] = len(response.history)
                
                # SSL certificate metrics
                if url.startswith('https://'):
                    metrics['certificate_days_remaining'] = await self._get_cert_expiry_days(url)
        
        except Exception as e:
            logger.debug(f"HTTP metrics collection failed for {url}: {e}")
        
        return metrics
    
    async def _get_cert_expiry_days(self, url: str) -> int:
        """Get SSL certificate expiry days"""
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            hostname = parsed.hostname
            port = parsed.port or 443
            
            # Get certificate
            ssl_context = ssl.create_default_context()
            
            with socket.create_connection((hostname, port), timeout=5) as sock:
                with ssl_context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    
                    # Parse expiry date
                    expiry_str = cert['notAfter']
                    expiry_date = time.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
                    expiry_timestamp = time.mktime(expiry_date)
                    
                    days_remaining = (expiry_timestamp - time.time()) / 86400
                    return max(0, int(days_remaining))
        
        except Exception as e:
            logger.debug(f"Certificate expiry check failed: {e}")
            return 0

class PathAnalyzer:
    """Network path analysis using traceroute and MTU discovery"""
    
    @staticmethod
    async def analyze_path(target: str) -> Dict[str, Any]:
        """Analyze network path to target"""
        
        metrics = {
            'hop_count': 0,
            'path_mtu': 1500,  # Default MTU
            'route_changes': 0
        }
        
        try:
            # Traceroute analysis
            hop_count = await PathAnalyzer._get_hop_count(target)
            metrics['hop_count'] = hop_count
            
            # MTU discovery
            mtu = await PathAnalyzer._discover_mtu(target)
            metrics['path_mtu'] = mtu
            
        except Exception as e:
            logger.debug(f"Path analysis failed for {target}: {e}")
        
        return metrics
    
    @staticmethod
    async def _get_hop_count(target: str) -> int:
        """Get hop count using traceroute"""
        
        try:
            # Use system traceroute command
            cmd = f"traceroute -m 30 -w 2 {target}"
            
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                output = stdout.decode()
                lines = output.split('\n')
                
                # Count hops (lines with hop numbers)
                hop_count = 0
                for line in lines:
                    line = line.strip()
                    if line and line[0].isdigit():
                        hop_parts = line.split()
                        if hop_parts and hop_parts[0].isdigit():
                            hop_count = max(hop_count, int(hop_parts[0]))
                
                return hop_count
        
        except Exception as e:
            logger.debug(f"Hop count detection failed: {e}")
        
        return 0
    
    @staticmethod
    async def _discover_mtu(target: str) -> int:
        """Discover path MTU"""
        
        try:
            # Binary search for MTU
            low, high = 68, 9000
            mtu = 1500
            
            for _ in range(10):  # Limit iterations
                test_size = (low + high) // 2
                
                # Test with ping
                cmd = f"ping -c 1 -M do -s {test_size - 28} {target}"  # -28 for IP+ICMP headers
                
                process = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                await process.communicate()
                
                if process.returncode == 0:
                    mtu = test_size
                    low = test_size + 1
                else:
                    high = test_size - 1
                
                if low > high:
                    break
            
            return mtu
        
        except Exception as e:
            logger.debug(f"MTU discovery failed: {e}")
            return 1500

class InterfaceMonitor:
    """Monitor network interface statistics"""
    
    @staticmethod
    def get_interface_metrics(interface_name: str = None) -> Dict[str, Any]:
        """Get interface-level metrics"""
        
        metrics = {
            'interface_utilization': 0.0,
            'interface_errors': 0,
            'interface_drops': 0,
            'interface_collisions': 0,
            'source_interface': 'unknown'
        }
        
        try:
            # Get network interface statistics
            net_io = psutil.net_io_counters(pernic=True)
            
            if interface_name:
                # Specific interface
                if interface_name in net_io:
                    stats = net_io[interface_name]
                    metrics['interface_errors'] = stats.errin + stats.errout
                    metrics['interface_drops'] = stats.dropin + stats.dropout
                    metrics['source_interface'] = interface_name
            else:
                # Aggregate all interfaces
                total_errors = 0
                total_drops = 0
                
                for iface_name, stats in net_io.items():
                    if not iface_name.startswith('lo'):  # Skip loopback
                        total_errors += stats.errin + stats.errout
                        total_drops += stats.dropin + stats.dropout
                
                metrics['interface_errors'] = total_errors
                metrics['interface_drops'] = total_drops
                metrics['source_interface'] = 'aggregate'
        
        except Exception as e:
            logger.debug(f"Interface metrics collection failed: {e}")
        
        return metrics

class BurstLossDetector:
    """Detect burst packet loss patterns"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.loss_history = []
    
    def add_measurement(self, packet_lost: bool):
        """Add packet loss measurement"""
        
        self.loss_history.append(1 if packet_lost else 0)
        
        # Keep only recent measurements
        if len(self.loss_history) > self.window_size:
            self.loss_history.pop(0)
    
    def get_burst_loss_rate(self) -> float:
        """Calculate burst loss rate"""
        
        if len(self.loss_history) < 10:
            return 0.0
        
        # Detect consecutive losses (bursts)
        bursts = 0
        in_burst = False
        
        for loss in self.loss_history:
            if loss == 1:
                if not in_burst:
                    bursts += 1
                    in_burst = True
            else:
                in_burst = False
        
        # Calculate burst rate
        total_losses = sum(self.loss_history)
        if total_losses == 0:
            return 0.0
        
        return (bursts / total_losses) * 100

class EnhancedNetworkCollector:
    """Enhanced network metrics collector with comprehensive monitoring"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.targets = config.get('targets', ['8.8.8.8', '1.1.1.1', 'google.com'])
        self.timeout = config.get('timeout', 10)
        
        # Component collectors
        self.http_collector = HTTPMetricsCollector(timeout=self.timeout)
        self.burst_detectors = {}  # Per-target burst loss detectors
        
        # History for jitter calculation
        self.ping_history = {}
        self.quality_calculator = QualityCalculator()
        
        # Threading for CPU-intensive operations
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def initialize(self):
        """Initialize the enhanced collector"""
        
        await self.http_collector.initialize()
        
        # Initialize burst detectors for each target
        for target in self.targets:
            self.burst_detectors[target] = BurstLossDetector()
        
        logger.info("Enhanced network collector initialized")
    
    async def close(self):
        """Close the collector"""
        
        await self.http_collector.close()
        self.executor.shutdown(wait=True)
    
    async def collect_enhanced_metrics(self, target: str = None) -> Optional[EnhancedNetworkMetrics]:
        """Collect comprehensive enhanced network metrics"""
        
        if not target:
            target = self.targets[0]
        
        start_time = time.time()
        
        try:
            # Collect metrics concurrently where possible
            tasks = [
                self._measure_core_connectivity(target),
                self._measure_quality_metrics(target),
                self._collect_http_metrics_if_applicable(target),
                self._analyze_network_path(target),
                self._collect_interface_metrics(),
                self._measure_bandwidth(target)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine results
            core_metrics = results[0] if not isinstance(results[0], Exception) else {}
            quality_metrics = results[1] if not isinstance(results[1], Exception) else {}
            http_metrics = results[2] if not isinstance(results[2], Exception) else {}
            path_metrics = results[3] if not isinstance(results[3], Exception) else {}
            interface_metrics = results[4] if not isinstance(results[4], Exception) else {}
            bandwidth_metrics = results[5] if not isinstance(results[5], Exception) else {}
            
            # Calculate quality scores
            latency = core_metrics.get('icmp_ping_time', 0)
            jitter = quality_metrics.get('jitter', 0)
            packet_loss = quality_metrics.get('packet_loss', 0)
            
            mos_score = self.quality_calculator.calculate_mos_score(latency, jitter, packet_loss)
            r_factor = self.quality_calculator.calculate_r_factor(latency, jitter, packet_loss)
            
            # Create comprehensive metrics object
            metrics = EnhancedNetworkMetrics(
                timestamp=start_time,
                target_host=target,
                
                # Core connectivity
                tcp_handshake_time=core_metrics.get('tcp_handshake_time', 0.0),
                icmp_ping_time=core_metrics.get('icmp_ping_time', 0.0),
                dns_resolve_time=core_metrics.get('dns_resolve_time', 0.0),
                
                # Enhanced latency
                tcp_connect_time=http_metrics.get('tcp_connect_time', 0.0),
                tcp_ssl_handshake_time=http_metrics.get('tcp_ssl_handshake_time', 0.0),
                http_response_time=http_metrics.get('http_response_time', 0.0),
                http_first_byte_time=http_metrics.get('http_first_byte_time', 0.0),
                
                # Quality metrics
                packet_loss=quality_metrics.get('packet_loss', 0.0),
                jitter=quality_metrics.get('jitter', 0.0),
                burst_loss_rate=quality_metrics.get('burst_loss_rate', 0.0),
                out_of_order_packets=quality_metrics.get('out_of_order_packets', 0.0),
                duplicate_packets=quality_metrics.get('duplicate_packets', 0.0),
                
                # Throughput
                bandwidth_download=bandwidth_metrics.get('download_mbps', 0.0),
                bandwidth_upload=bandwidth_metrics.get('upload_mbps', 0.0),
                concurrent_connections=core_metrics.get('concurrent_connections', 0),
                connection_setup_rate=core_metrics.get('connection_setup_rate', 0.0),
                
                # Application metrics
                http_status_code=http_metrics.get('http_status_code', 0),
                http_content_length=http_metrics.get('http_content_length', 0),
                certificate_days_remaining=http_metrics.get('certificate_days_remaining', 0),
                redirect_count=http_metrics.get('redirect_count', 0),
                
                # Interface metrics
                interface_utilization=interface_metrics.get('interface_utilization', 0.0),
                interface_errors=interface_metrics.get('interface_errors', 0),
                interface_drops=interface_metrics.get('interface_drops', 0),
                interface_collisions=interface_metrics.get('interface_collisions', 0),
                
                # Path analysis
                hop_count=path_metrics.get('hop_count', 0),
                path_mtu=path_metrics.get('path_mtu', 1500),
                route_changes=path_metrics.get('route_changes', 0),
                
                # Quality scores
                mos_score=mos_score,
                r_factor=r_factor,
                delay_variation=quality_metrics.get('delay_variation', 0.0),
                
                # Error tracking
                connection_errors=core_metrics.get('connection_errors', 0),
                dns_errors=core_metrics.get('dns_errors', 0),
                timeout_errors=core_metrics.get('timeout_errors', 0),
                
                # Metadata
                source_interface=interface_metrics.get('source_interface', 'unknown'),
                network_type=self._detect_network_type(),
                measurement_duration=(time.time() - start_time) * 1000
            )
            
            logger.debug(f"Enhanced metrics collected for {target} in {metrics.measurement_duration:.2f}ms")
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting enhanced metrics for {target}: {e}")
            return None
    
    async def _measure_core_connectivity(self, target: str) -> Dict[str, Any]:
        """Measure core connectivity metrics"""
        
        metrics = {
            'tcp_handshake_time': 0.0,
            'icmp_ping_time': 0.0,
            'dns_resolve_time': 0.0,
            'concurrent_connections': 0,
            'connection_setup_rate': 0.0,
            'connection_errors': 0,
            'dns_errors': 0,
            'timeout_errors': 0
        }
        
        try:
            # TCP handshake measurement
            tcp_time = await self._measure_tcp_handshake_enhanced(target)
            metrics['tcp_handshake_time'] = tcp_time
            
            # ICMP ping measurement
            icmp_time, packet_loss = await self._measure_icmp_ping_enhanced(target)
            metrics['icmp_ping_time'] = icmp_time
            
            # DNS resolution measurement
            dns_time = await self._measure_dns_resolution_enhanced(target)
            metrics['dns_resolve_time'] = dns_time
            
            # Connection statistics
            concurrent = await self._count_concurrent_connections(target)
            metrics['concurrent_connections'] = concurrent
            
        except Exception as e:
            logger.debug(f"Core connectivity measurement failed: {e}")
            metrics['connection_errors'] += 1
        
        return metrics
    
    async def _measure_tcp_handshake_enhanced(self, host: str, port: int = 80) -> float:
        """Enhanced TCP handshake measurement with better error handling"""
        
        try:
            # Resolve hostname first if needed
            if not self._is_ip_address(host):
                host = socket.gethostbyname(host)
            
            start_time = time.perf_counter()
            
            # Create socket with optimal settings
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(self.timeout)
            
            try:
                result = sock.connect_ex((host, port))
                handshake_time = (time.perf_counter() - start_time) * 1000
                
                if result == 0:
                    return handshake_time
                else:
                    return -1.0
                    
            finally:
                sock.close()
                
        except Exception as e:
            logger.debug(f"TCP handshake measurement failed: {e}")
            return -1.0
    
    async def _measure_icmp_ping_enhanced(self, host: str, count: int = 5) -> Tuple[float, float]:
        """Enhanced ICMP ping with burst loss detection"""
        
        try:
            cmd = f"ping -c {count} -i 0.2 -W 3 {host}"
            
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                output = stdout.decode()
                
                ping_times = []
                packet_loss = 0.0
                lost_packets = []
                
                lines = output.split('\n')
                for i, line in enumerate(lines):
                    if 'packet loss' in line:
                        parts = line.split('%')[0].split()
                        packet_loss = float(parts[-1])
                    elif 'time=' in line:
                        time_part = line.split('time=')[1].split()[0]
                        ping_times.append(float(time_part))
                        lost_packets.append(False)
                    elif 'no answer' in line or 'timeout' in line:
                        lost_packets.append(True)
                
                # Update burst loss detector
                if host in self.burst_detectors:
                    for lost in lost_packets:
                        self.burst_detectors[host].add_measurement(lost)
                
                if ping_times:
                    avg_time = statistics.mean(ping_times)
                    return avg_time, packet_loss
                else:
                    return -1.0, 100.0
            else:
                return -1.0, 100.0
                
        except Exception as e:
            logger.debug(f"Enhanced ICMP ping failed: {e}")
            return -1.0, 100.0
    
    async def _measure_dns_resolution_enhanced(self, hostname: str) -> float:
        """Enhanced DNS resolution measurement"""
        
        try:
            start_time = time.perf_counter()
            
            # Perform DNS resolution with timeout
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.getaddrinfo(hostname, None), 
                timeout=self.timeout
            )
            
            resolve_time = (time.perf_counter() - start_time) * 1000
            return resolve_time
            
        except asyncio.TimeoutError:
            logger.debug(f"DNS resolution timeout for {hostname}")
            return -1.0
        except Exception as e:
            logger.debug(f"DNS resolution error for {hostname}: {e}")
            return -1.0
    
    async def _measure_quality_metrics(self, target: str) -> Dict[str, Any]:
        """Measure network quality metrics"""
        
        metrics = {
            'jitter': 0.0,
            'packet_loss': 0.0,
            'burst_loss_rate': 0.0,
            'out_of_order_packets': 0.0,
            'duplicate_packets': 0.0,
            'delay_variation': 0.0
        }
        
        try:
            # Enhanced ping for jitter calculation
            ping_times = []
            for _ in range(10):  # Multiple pings for jitter
                ping_time, _ = await self._measure_icmp_ping_enhanced(target, count=1)
                if ping_time > 0:
                    ping_times.append(ping_time)
                await asyncio.sleep(0.1)  # 100ms interval
            
            if len(ping_times) >= 3:
                # Calculate jitter (average deviation between consecutive pings)
                differences = [abs(ping_times[i] - ping_times[i-1]) 
                             for i in range(1, len(ping_times))]
                metrics['jitter'] = statistics.mean(differences)
                
                # Calculate delay variation (standard deviation)
                metrics['delay_variation'] = statistics.stdev(ping_times)
            
            # Get burst loss rate
            if target in self.burst_detectors:
                metrics['burst_loss_rate'] = self.burst_detectors[target].get_burst_loss_rate()
            
        except Exception as e:
            logger.debug(f"Quality metrics measurement failed: {e}")
        
        return metrics
    
    async def _collect_http_metrics_if_applicable(self, target: str) -> Dict[str, Any]:
        """Collect HTTP metrics if target supports HTTP"""
        
        # Check if target looks like a hostname/domain
        if self._is_ip_address(target):
            return {}
        
        # Try HTTP and HTTPS
        for protocol in ['https', 'http']:
            url = f"{protocol}://{target}"
            try:
                metrics = await self.http_collector.collect_http_metrics(url)
                if metrics.get('http_status_code', 0) > 0:
                    return metrics
            except Exception:
                continue
        
        return {}
    
    async def _analyze_network_path(self, target: str) -> Dict[str, Any]:
        """Analyze network path to target"""
        
        return await PathAnalyzer.analyze_path(target)
    
    async def _collect_interface_metrics(self) -> Dict[str, Any]:
        """Collect interface-level metrics"""
        
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, InterfaceMonitor.get_interface_metrics
        )
    
    async def _measure_bandwidth(self, target: str) -> Dict[str, Any]:
        """Measure bandwidth to target"""
        
        metrics = {
            'download_mbps': 0.0,
            'upload_mbps': 0.0
        }
        
        try:
            # Simple download test using HTTP if available
            if not self._is_ip_address(target):
                url = f"http://{target}"
                
                start_time = time.perf_counter()
                
                async with self.http_collector.session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        
                        transfer_time = time.perf_counter() - start_time
                        bytes_transferred = len(content)
                        
                        if transfer_time > 0:
                            mbps = (bytes_transferred * 8) / (transfer_time * 1_000_000)
                            metrics['download_mbps'] = mbps
        
        except Exception as e:
            logger.debug(f"Bandwidth measurement failed: {e}")
        
        return metrics
    
    async def _count_concurrent_connections(self, target: str) -> int:
        """Count concurrent connections to target"""
        
        try:
            # Use netstat to count connections
            connections = psutil.net_connections()
            
            count = 0
            for conn in connections:
                if conn.raddr and len(conn.raddr) > 0:
                    if target in str(conn.raddr[0]):
                        count += 1
            
            return count
            
        except Exception as e:
            logger.debug(f"Connection counting failed: {e}")
            return 0
    
    def _is_ip_address(self, address: str) -> bool:
        """Check if string is an IP address"""
        try:
            socket.inet_aton(address)
            return True
        except socket.error:
            return False
    
    def _detect_network_type(self) -> str:
        """Detect network type (ethernet, wifi, cellular, etc.)"""
        
        try:
            # Simple heuristic based on interface names
            interfaces = psutil.net_if_stats()
            
            for name, stats in interfaces.items():
                if stats.isup:
                    name_lower = name.lower()
                    if 'eth' in name_lower or 'en' in name_lower:
                        return 'ethernet'
                    elif 'wlan' in name_lower or 'wifi' in name_lower or 'wl' in name_lower:
                        return 'wifi'
                    elif 'ppp' in name_lower or 'wwan' in name_lower:
                        return 'cellular'
            
            return 'unknown'
            
        except Exception:
            return 'unknown'
    
    async def test_enhanced_connectivity(self, targets: List[str] = None) -> Dict[str, Dict[str, Any]]:
        """Test enhanced connectivity to multiple targets"""
        
        if not targets:
            targets = self.targets
        
        results = {}
        
        for target in targets:
            try:
                metrics = await self.collect_enhanced_metrics(target)
                if metrics:
                    results[target] = {
                        'status': 'success',
                        'latency': metrics.icmp_ping_time,
                        'jitter': metrics.jitter,
                        'packet_loss': metrics.packet_loss,
                        'mos_score': metrics.mos_score,
                        'quality_rating': self._rate_connection_quality(metrics)
                    }
                else:
                    results[target] = {
                        'status': 'failed',
                        'error': 'Failed to collect metrics'
                    }
                    
            except Exception as e:
                results[target] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        return results
    
    def _rate_connection_quality(self, metrics: EnhancedNetworkMetrics) -> str:
        """Rate overall connection quality"""
        
        score = 0
        
        # Latency scoring
        if metrics.icmp_ping_time <= 20:
            score += 25
        elif metrics.icmp_ping_time <= 50:
            score += 20
        elif metrics.icmp_ping_time <= 100:
            score += 15
        elif metrics.icmp_ping_time <= 200:
            score += 10
        
        # Packet loss scoring
        if metrics.packet_loss == 0:
            score += 25
        elif metrics.packet_loss <= 1:
            score += 20
        elif metrics.packet_loss <= 3:
            score += 15
        elif metrics.packet_loss <= 5:
            score += 10
        
        # Jitter scoring
        if metrics.jitter <= 1:
            score += 25
        elif metrics.jitter <= 5:
            score += 20
        elif metrics.jitter <= 10:
            score += 15
        elif metrics.jitter <= 20:
            score += 10
        
        # MOS score contribution
        if metrics.mos_score >= 4.0:
            score += 25
        elif metrics.mos_score >= 3.5:
            score += 20
        elif metrics.mos_score >= 3.0:
            score += 15
        elif metrics.mos_score >= 2.5:
            score += 10
        
        # Rating based on total score
        if score >= 90:
            return 'excellent'
        elif score >= 75:
            return 'good'
        elif score >= 60:
            return 'fair'
        elif score >= 40:
            return 'poor'
        else:
            return 'bad'

# Utility functions

async def quick_enhanced_test(targets: List[str] = None) -> Dict[str, Any]:
    """Quick enhanced connectivity test"""
    
    if not targets:
        targets = ['8.8.8.8', '1.1.1.1', 'google.com']
    
    collector = EnhancedNetworkCollector({'targets': targets, 'timeout': 5})
    
    try:
        await collector.initialize()
        results = await collector.test_enhanced_connectivity(targets)
        return results
    finally:
        await collector.close()

def create_metrics_summary(metrics: EnhancedNetworkMetrics) -> Dict[str, Any]:
    """Create summary of enhanced metrics for dashboard"""
    
    return {
        'timestamp': metrics.timestamp,
        'target': metrics.target_host,
        'connectivity': {
            'latency_ms': metrics.icmp_ping_time,
            'jitter_ms': metrics.jitter,
            'packet_loss_pct': metrics.packet_loss,
            'quality_rating': 'good' if metrics.mos_score > 3.5 else 'poor'
        },
        'performance': {
            'tcp_handshake_ms': metrics.tcp_handshake_time,
            'dns_resolve_ms': metrics.dns_resolve_time,
            'http_response_ms': metrics.http_response_time,
            'bandwidth_mbps': metrics.bandwidth_download
        },
        'quality_scores': {
            'mos_score': metrics.mos_score,
            'r_factor': metrics.r_factor,
            'overall_rating': 'excellent' if metrics.mos_score > 4.0 else 'good' if metrics.mos_score > 3.0 else 'poor'
        },
        'network_health': {
            'interface_errors': metrics.interface_errors,
            'path_hops': metrics.hop_count,
            'certificate_days': metrics.certificate_days_remaining,
            'connection_errors': metrics.connection_errors
        }
    }

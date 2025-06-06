#!/usr/bin/env python3
"""
Prometheus Metrics Exporter
===========================

Export network intelligence metrics in Prometheus format for Grafana Alloy collection.
Features:
- Comprehensive network metrics exposition
- Custom metric types (gauges, counters, histograms)
- Multi-dimensional labels for rich querying
- Automatic metric registration and cleanup
- Edge device optimized memory usage
"""

 
import time
import logging
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from prometheus_client import (
    Gauge, Counter, Histogram, Info, Enum,
    CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
)
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, HistogramMetricFamily
from flask import Flask, Response
import json

# Import the new metrics definition
from src.networkquality.prometheus_metrics import NetworkQualityPrometheusMetrics


logger = logging.getLogger(__name__)

class NetworkIntelligenceMetrics:
    """Prometheus metrics for network intelligence monitoring"""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()
        self._setup_metrics()
        
        self._lock = threading.Lock()
        
        self._latency_history = []
        self._jitter_history = []
        self._max_history_size = 1000
    
    def _setup_metrics(self):
        """Setup all Prometheus metrics"""
        
        # === Core Connectivity Metrics ===
        self.tcp_handshake_duration = Gauge(
            'network_tcp_handshake_duration_seconds',
            'TCP 3-way handshake duration in seconds',
            ['target', 'port', 'source_interface'],
            registry=self.registry
        )
        
        self.icmp_ping_duration = Gauge(
            'network_icmp_ping_duration_seconds',
            'ICMP ping round-trip time in seconds',
            ['target', 'source_interface'],
            registry=self.registry
        )
        
        self.dns_resolution_duration = Gauge(
            'network_dns_resolution_duration_seconds',
            'DNS resolution time in seconds',
            ['target', 'resolver', 'record_type'],
            registry=self.registry
        )
        
        # === Quality Metrics ===
        self.packet_loss_ratio = Gauge(
            'network_packet_loss_ratio',
            'Packet loss ratio (0-1)',
            ['target', 'source_interface'],
            registry=self.registry
        )
        
        self.jitter_seconds = Gauge(
            'network_jitter_seconds',
            'Network jitter in seconds',
            ['target', 'source_interface'],
            registry=self.registry
        )
        
        self.mos_score = Gauge(
            'network_mos_score',
            'Mean Opinion Score for voice quality (1-5)',
            ['target', 'calculation_method'],
            registry=self.registry
        )

        self.r_factor = Gauge(
            'network_r_factor',
            'R-factor for voice quality (0-100)',
            ['target', 'calculation_method'],
            registry=self.registry
        )
        
        self.burst_loss_rate = Gauge(
            'network_burst_loss_rate',
            'Burst packet loss rate percentage',
            ['target', 'window_size'],
            registry=self.registry
        )
        
        # === HTTP/Application Metrics ===
        self.http_response_duration = Gauge(
            'network_http_response_duration_seconds',
            'HTTP response time in seconds',
            ['target', 'method', 'status_code', 'protocol'],
            registry=self.registry
        )
        
        self.http_first_byte_duration = Gauge(
            'network_http_first_byte_duration_seconds',
            'Time to first byte in seconds',
            ['target', 'protocol'],
            registry=self.registry
        )
        
        self.ssl_handshake_duration = Gauge(
            'network_ssl_handshake_duration_seconds',
            'SSL/TLS handshake duration in seconds',
            ['target', 'protocol_version'],
            registry=self.registry
        )
        
        self.certificate_expiry_days = Gauge(
            'network_certificate_expiry_days',
            'Days until SSL certificate expiry',
            ['target', 'issuer', 'subject'],
            registry=self.registry
        )
        
        # === Throughput Metrics ===
        self.bandwidth_download_bps = Gauge(
            'network_bandwidth_download_bits_per_second',
            'Download bandwidth in bits per second',
            ['target', 'test_method'],
            registry=self.registry
        )
        
        self.bandwidth_upload_bps = Gauge(
            'network_bandwidth_upload_bits_per_second',
            'Upload bandwidth in bits per second',
            ['target', 'test_method'],
            registry=self.registry
        )
        
        # === Interface Metrics ===
        self.interface_utilization_ratio = Gauge(
            'network_interface_utilization_ratio',
            'Network interface utilization ratio (0-1)',
            ['interface', 'direction'],
            registry=self.registry
        )
        
        self.interface_errors_total = Counter(
            'network_interface_errors_total',
            'Total network interface errors',
            ['interface', 'type'],
            registry=self.registry
        )
        
        self.interface_drops_total = Counter(
            'network_interface_drops_total',
            'Total network interface packet drops',
            ['interface', 'direction'],
            registry=self.registry
        )
        
        # === Path Analysis Metrics ===
        self.path_hops = Gauge(
            'network_path_hops',
            'Number of network hops to target',
            ['target', 'trace_method'],
            registry=self.registry
        )
        
        self.path_mtu_bytes = Gauge(
            'network_path_mtu_bytes',
            'Path MTU in bytes',
            ['target'],
            registry=self.registry
        )
        
        # === Connection Metrics ===
        self.concurrent_connections = Gauge(
            'network_concurrent_connections',
            'Number of concurrent connections',
            ['target', 'protocol'],
            registry=self.registry
        )
        
        self.connection_errors_total = Counter(
            'network_connection_errors_total',
            'Total connection errors',
            ['target', 'error_type'],
            registry=self.registry
        )
        
        # === AI/ML Metrics ===
        self.anomaly_score = Gauge(
            'network_anomaly_score',
            'AI-generated anomaly score (0-1)',
            ['target', 'model_type', 'feature_set'],
            registry=self.registry
        )
        
        self.anomaly_confidence = Gauge(
            'network_anomaly_confidence',
            'Confidence in anomaly detection (0-1)',
            ['target', 'model_type'],
            registry=self.registry
        )
        
        self.baseline_deviation_ratio = Gauge(
            'network_baseline_deviation_ratio',
            'Deviation from baseline as ratio',
            ['target', 'metric_name', 'baseline_type'],
            registry=self.registry
        )
        
        # === System Health Metrics ===
        self.measurement_duration_seconds = Gauge(
            'network_measurement_duration_seconds',
            'Time taken to collect metrics in seconds',
            ['target', 'measurement_type'],
            registry=self.registry
        )
        
        self.collector_health_status = Enum(
            'network_collector_health_status',
            'Health status of network collector',
            ['component'],
            states=['healthy', 'degraded', 'unhealthy', 'unknown'],
            registry=self.registry
        )
        
        # === Histograms for Distribution Analysis ===
        self.latency_histogram = Histogram(
            'network_latency_duration_seconds',
            'Histogram of network latency measurements',
            ['target', 'measurement_type'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=self.registry
        )
        
        self.jitter_histogram = Histogram(
            'network_jitter_duration_seconds',
            'Histogram of network jitter measurements',
            ['target'],
            buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
            registry=self.registry
        )
        
        # === Info Metrics ===
        self.network_info = Info(
            'network_target_info',
            'Information about network targets',
            ['target'],
            registry=self.registry
        )
        
        self.collector_info = Info(
            'network_collector_info',
            'Information about the network collector',
            registry=self.registry
        )
        
        # Set static collector info
        self.collector_info.info({
            'version': '1.0.0',
            'features': 'enhanced_collection,ai_detection,quality_metrics',
            'deployment_type': 'edge_optimized'
        })
    
    def update_from_enhanced_metrics(self, metrics):
        """Update all Prometheus metrics from EnhancedNetworkMetrics"""
        
        with self._lock:
            try:
                target = metrics.target_host
                interface = metrics.source_interface or 'unknown'
                
                # Core connectivity metrics
                if metrics.tcp_handshake_time > 0:
                    self.tcp_handshake_duration.labels(
                        target=target, port='80', source_interface=interface
                    ).set(metrics.tcp_handshake_time / 1000)  # Convert ms to seconds
                
                if metrics.icmp_ping_time > 0:
                    ping_seconds = metrics.icmp_ping_time / 1000
                    self.icmp_ping_duration.labels(
                        target=target, source_interface=interface
                    ).set(ping_seconds)
                    
                    # Update histogram
                    self.latency_histogram.labels(
                        target=target, measurement_type='icmp'
                    ).observe(ping_seconds)
                
                if metrics.dns_resolve_time > 0:
                    self.dns_resolution_duration.labels(
                        target=target, resolver='system', record_type='A'
                    ).set(metrics.dns_resolve_time / 1000)
                
                # Quality metrics
                self.packet_loss_ratio.labels(
                    target=target, source_interface=interface
                ).set(metrics.packet_loss / 100)  # Convert percentage to ratio
                
                if metrics.jitter > 0:
                    jitter_seconds = metrics.jitter / 1000
                    self.jitter_seconds.labels(
                        target=target, source_interface=interface
                    ).set(jitter_seconds)
                    
                    # Update histogram
                    self.jitter_histogram.labels(target=target).observe(jitter_seconds)
                
                self.mos_score.labels(
                    target=target, calculation_method='itu_g107'
                ).set(metrics.mos_score)
                
                self.r_factor.labels(
                    target=target, calculation_method='itu_g107'
                ).set(metrics.r_factor)
                
                self.burst_loss_rate.labels(
                    target=target, window_size='100'
                ).set(metrics.burst_loss_rate)
                
                # HTTP/Application metrics
                if metrics.http_response_time > 0:
                    self.http_response_duration.labels(
                        target=target,
                        method='GET',
                        status_code=str(metrics.http_status_code),
                        protocol='http'
                    ).set(metrics.http_response_time / 1000)
                
                if metrics.http_first_byte_time > 0:
                    self.http_first_byte_duration.labels(
                        target=target, protocol='http'
                    ).set(metrics.http_first_byte_time / 1000)
                
                if metrics.tcp_ssl_handshake_time > 0:
                    self.ssl_handshake_duration.labels(
                        target=target, protocol_version='tls'
                    ).set(metrics.tcp_ssl_handshake_time / 1000)
                
                if metrics.certificate_days_remaining > 0:
                    self.certificate_expiry_days.labels(
                        target=target, issuer='unknown', subject=target
                    ).set(metrics.certificate_days_remaining)
                
                # Throughput metrics
                if metrics.bandwidth_download > 0:
                    self.bandwidth_download_bps.labels(
                        target=target, test_method='http_download'
                    ).set(metrics.bandwidth_download * 1_000_000)  # Convert Mbps to bps
                
                if metrics.bandwidth_upload > 0:
                    self.bandwidth_upload_bps.labels(
                        target=target, test_method='http_upload'
                    ).set(metrics.bandwidth_upload * 1_000_000)
                
                # Interface metrics
                self.interface_utilization_ratio.labels(
                    interface=interface, direction='combined'
                ).set(metrics.interface_utilization / 100)
                
                # Path analysis
                if metrics.hop_count > 0:
                    self.path_hops.labels(
                        target=target, trace_method='traceroute'
                    ).set(metrics.hop_count)
                
                if metrics.path_mtu > 0:
                    self.path_mtu_bytes.labels(target=target).set(metrics.path_mtu)
                
                # Connection metrics
                self.concurrent_connections.labels(
                    target=target, protocol='tcp'
                ).set(metrics.concurrent_connections)
                
                # Error tracking
                if metrics.connection_errors > 0:
                    self.connection_errors_total.labels(
                        target=target, error_type='connection_failed'
                    ).inc(metrics.connection_errors)
                
                if metrics.dns_errors > 0:
                    self.connection_errors_total.labels(
                        target=target, error_type='dns_resolution'
                    ).inc(metrics.dns_errors)
                
                if metrics.timeout_errors > 0:
                    self.connection_errors_total.labels(
                        target=target, error_type='timeout'
                    ).inc(metrics.timeout_errors)
                
                # System metrics
                self.measurement_duration_seconds.labels(
                    target=target, measurement_type='comprehensive'
                ).set(metrics.measurement_duration / 1000)
                
                # Network info
                self.network_info.labels(target=target).info({
                    'network_type': metrics.network_type,
                    'source_interface': interface,
                    'last_measurement': str(int(metrics.timestamp))
                })
                
                # Health status based on metrics quality
                health_status = self._determine_health_status(metrics)
                self.collector_health_status.labels(component='network_collector').state(health_status)
                
            except Exception as e:
                logger.error(f"Error updating Prometheus metrics: {e}")
    
    def update_anomaly_metrics(self, anomaly_result, target: str):
        """Update AI/ML anomaly detection metrics"""
        
        with self._lock:
            try:
                model_type = getattr(anomaly_result, 'model_type', 'lstm_autoencoder')
                
                self.anomaly_score.labels(
                    target=target,
                    model_type=model_type,
                    feature_set='comprehensive'
                ).set(anomaly_result.anomaly_score)
                
                self.anomaly_confidence.labels(
                    target=target,
                    model_type=model_type
                ).set(anomaly_result.confidence)
                
                # Update baseline deviation for each feature
                if hasattr(anomaly_result, 'feature_contributions'):
                    for feature_name, contribution in anomaly_result.feature_contributions.items():
                        self.baseline_deviation_ratio.labels(
                            target=target,
                            metric_name=feature_name,
                            baseline_type='adaptive'
                        ).set(contribution)
                
            except Exception as e:
                logger.error(f"Error updating anomaly metrics: {e}")
    
    def update_interface_metrics(self, interface_stats: Dict[str, Any]):
        """Update interface-specific metrics"""
        
        with self._lock:
            try:
                for interface_name, stats in interface_stats.items():
                    # Error counters
                    if 'errors_in' in stats:
                        self.interface_errors_total.labels(
                            interface=interface_name, type='input'
                        ).inc(stats['errors_in'])
                    
                    if 'errors_out' in stats:
                        self.interface_errors_total.labels(
                            interface=interface_name, type='output'
                        ).inc(stats['errors_out'])
                    
                    # Drop counters
                    if 'drops_in' in stats:
                        self.interface_drops_total.labels(
                            interface=interface_name, direction='input'
                        ).inc(stats['drops_in'])
                    
                    if 'drops_out' in stats:
                        self.interface_drops_total.labels(
                            interface=interface_name, direction='output'
                        ).inc(stats['drops_out'])
                    
                    # Utilization
                    if 'utilization' in stats:
                        self.interface_utilization_ratio.labels(
                            interface=interface_name, direction='combined'
                        ).set(stats['utilization'] / 100)
                        
            except Exception as e:
                logger.error(f"Error updating interface metrics: {e}")
    
    def _determine_health_status(self, metrics) -> str:
        """Determine overall health status based on metrics"""
        
        issues = 0
        
        # Check for connectivity issues
        if metrics.icmp_ping_time <= 0:
            issues += 2
        elif metrics.icmp_ping_time > 200:  # High latency
            issues += 1
        
        # Check for quality issues
        if metrics.packet_loss > 5:  # High packet loss
            issues += 2
        elif metrics.packet_loss > 1:
            issues += 1
        
        if metrics.jitter > 50:  # High jitter
            issues += 1
        
        # Check for errors
        if metrics.connection_errors > 0:
            issues += 1
        
        # Determine status
        if issues == 0:
            return 'healthy'
        elif issues <= 2:
            return 'degraded'
        elif issues <= 4:
            return 'unhealthy'
        else:
            return 'unhealthy'
    
    def get_metrics_text(self) -> str:
        """Get metrics in Prometheus text format"""
        return generate_latest(self.registry).decode('utf-8')

class PrometheusMetricsServer:
    """HTTP server for Prometheus metrics exposition"""
    
    def __init__(self, port: int = 8000, host: str = '0.0.0.0'):
        self.port = port
        self.host = host
        self.app = Flask(__name__)
        
        # FIX: The server now holds instances of both metric sets
        self.registry = CollectorRegistry()
        self.metrics = NetworkIntelligenceMetrics(registry=self.registry)
        self.nq_metrics = NetworkQualityPrometheusMetrics(registry=self.registry) # New
        
        self._setup_routes()
        
        self.server_thread = None
        self.running = False
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/metrics')
        def metrics_endpoint():
            """Prometheus metrics endpoint"""
            try:
                # Use the shared registry to generate all metrics
                metrics_text = generate_latest(self.registry).decode('utf-8')
                return Response(metrics_text, mimetype=CONTENT_TYPE_LATEST)
            except Exception as e:
                logger.error(f"Error generating metrics: {e}")
                return Response("# Error generating metrics\n", 
                              mimetype=CONTENT_TYPE_LATEST, status=500)
        
        @self.app.route('/health')
        def health_endpoint():
            """Health check endpoint"""
            return {'status': 'healthy', 'timestamp': time.time()}
    
    def start(self):
        """Start the metrics server"""
        if self.running:
            logger.warning("Metrics server already running")
            return
        self.running = True
        
        def run_server():
            try:
                # Disable reloader to prevent errors in threads
                self.app.run(
                    host=self.host, port=self.port, debug=False, use_reloader=False, threaded=True
                )
            except Exception as e:
                logger.error(f"Metrics server error: {e}")
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        logger.info(f"Prometheus metrics server started on {self.host}:{self.port}")
    
    def stop(self):
        self.running = False
        logger.info("Prometheus metrics server stopped")

    def update_metrics(self, enhanced_metrics):
        self.metrics.update_from_enhanced_metrics(enhanced_metrics)
    
    # New method to update NetworkQuality metrics
    def update_nq_metrics(self, nq_metrics_data):
        if hasattr(nq_metrics_data, 'to_dict'):
            data = nq_metrics_data.to_dict()
        else:
            data = nq_metrics_data
        self.nq_metrics.update_metrics(data)

    def update_anomaly_metrics(self, anomaly_result, target: str):
        self.metrics.update_anomaly_metrics(anomaly_result, target)
    
    def update_interface_metrics(self, interface_stats: Dict[str, Any]):
        self.metrics.update_interface_metrics(interface_stats)


class MetricsAggregator:
    """Aggregate and batch metrics updates for efficiency"""
    
    def __init__(self, metrics_server: PrometheusMetricsServer, batch_size: int = 10):
        self.metrics_server = metrics_server
        self.batch_size = batch_size
        
        self.metrics_batch = []
        self.anomaly_batch = []
        self.interface_batch = {}
        self.nq_metrics_batch = [] # New batch for network quality metrics

        self._lock = threading.Lock()
        self._flush_thread = None
        self._running = False
        self.flush_interval = 30
    
    def start(self):
        self._running = True
        def flush_loop():
            while self._running:
                time.sleep(self.flush_interval)
                self.flush_batches()
        self._flush_thread = threading.Thread(target=flush_loop, daemon=True)
        self._flush_thread.start()
        logger.info("Metrics aggregator started")
    
    def stop(self):
        self._running = False
        self.flush_batches()
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5)
        logger.info("Metrics aggregator stopped")
    
    def add_enhanced_metrics(self, metrics):
        with self._lock:
            self.metrics_batch.append(metrics)
            if len(self.metrics_batch) >= self.batch_size:
                self._flush_metrics_batch()


    def add_networkquality_metrics(self, nq_metrics):
        """Add NetworkQuality metrics to Prometheus export"""
        try:
            # Import at runtime to avoid circular imports
            from src.networkquality.prometheus_metrics import NetworkQualityPrometheusMetrics
            
            # Always try to get/create instance - singleton will handle duplicates
            if not hasattr(self, 'nq_metrics'):
                # Pass None for registry to use existing metrics if they exist
                self.nq_metrics = NetworkQualityPrometheusMetrics(registry=None)
            
            # Update metrics
            if self.nq_metrics:
                data = nq_metrics.to_dict() if hasattr(nq_metrics, 'to_dict') else nq_metrics
                self.nq_metrics.update_metrics(data)
                logger.debug(f"Updated NetworkQuality metrics for {data.get('target_host', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Error updating NetworkQuality metrics: {e}")
            # Don't raise - just log and continue

    def add_anomaly_metrics(self, anomaly_result, target: str):
        with self._lock:
            self.anomaly_batch.append((anomaly_result, target))
            if len(self.anomaly_batch) >= self.batch_size:
                self._flush_anomaly_batch()
    
    def flush_batches(self):
        with self._lock:
            self._flush_metrics_batch()
            self._flush_anomaly_batch()
            self._flush_nq_metrics_batch() # Flush the new batch

    def _flush_metrics_batch(self):
        if not self.metrics_batch: return
        try:
            target_metrics = {m.target_host: m for m in self.metrics_batch}
            for metrics in target_metrics.values():
                self.metrics_server.update_metrics(metrics)
            logger.debug(f"Flushed {len(target_metrics)} enhanced metrics")
        except Exception as e:
            logger.error(f"Error flushing metrics batch: {e}")
        finally:
            self.metrics_batch.clear()
            
    # FIX: Add the flush logic for the new batch
    def _flush_nq_metrics_batch(self):
        """Flush the NetworkQuality metrics batch."""
        if not self.nq_metrics_batch: return
        try:
            # The NQ test has a single "target" (cloudflare), so just process the latest one
            latest_nq_metric = self.nq_metrics_batch[-1]
            self.metrics_server.update_nq_metrics(latest_nq_metric)
            logger.debug(f"Flushed {len(self.nq_metrics_batch)} NetworkQuality metrics")
        except Exception as e:
            logger.error(f"Error flushing NetworkQuality metrics batch: {e}")
        finally:
            self.nq_metrics_batch.clear()

    def _flush_anomaly_batch(self):
        if not self.anomaly_batch: return
        try:
            target_anomalies = {target: result for result, target in self.anomaly_batch}
            for target, anomaly_result in target_anomalies.items():
                self.metrics_server.update_anomaly_metrics(anomaly_result, target)
            logger.debug(f"Flushed {len(target_anomalies)} anomaly metrics")
        except Exception as e:
            logger.error(f"Error flushing anomaly batch: {e}")
        finally:
            self.anomaly_batch.clear()   

    def _flush_interface_batch(self):
        """Flush interface metrics batch"""
        
        if not self.interface_batch:
            return
        
        try:
            self.metrics_server.update_interface_metrics(self.interface_batch)
            logger.debug(f"Flushed interface metrics for {len(self.interface_batch)} interfaces")
            
        except Exception as e:
            logger.error(f"Error flushing interface batch: {e}")
        finally:
            self.interface_batch.clear()

# Integration helper functions

def create_metrics_server(config: Dict[str, Any]) -> PrometheusMetricsServer:
    """Create and configure Prometheus metrics server"""
    
    port = config.get('metrics_port', 8000)
    host = config.get('metrics_host', '0.0.0.0')
    
    server = PrometheusMetricsServer(port=port, host=host)
    return server

def create_metrics_aggregator(metrics_server: PrometheusMetricsServer, 
                            config: Dict[str, Any]) -> MetricsAggregator:
    """Create and configure metrics aggregator"""
    
    batch_size = config.get('metrics_batch_size', 10)
    aggregator = MetricsAggregator(metrics_server, batch_size=batch_size)
    
    return aggregator

def integrate_with_network_monitor(network_monitor, metrics_server: PrometheusMetricsServer):
    """Integrate metrics server with existing network monitor"""
    
    # Store reference to metrics server in monitor
    network_monitor.metrics_server = metrics_server
    
    # Override or extend the metric storage methods
    original_store_metrics = network_monitor.database.store_metrics if hasattr(network_monitor, 'database') else None
    
    async def enhanced_store_metrics(metrics):
        """Enhanced metrics storage that also updates Prometheus"""
        
        # Store in database as usual
        if original_store_metrics:
            result = await original_store_metrics(metrics)
        else:
            result = True
        
        # Update Prometheus metrics
        try:
            if hasattr(metrics, 'to_dict'):
                # Convert to enhanced metrics format if needed
                metrics_server.update_metrics(metrics)
            else:
                logger.debug("Metrics not in expected format for Prometheus export")
        except Exception as e:
            logger.error(f"Error updating Prometheus metrics: {e}")
        
        return result
    
    # Replace the store_metrics method
    if hasattr(network_monitor, 'database'):
        network_monitor.database.store_metrics = enhanced_store_metrics
    
    logger.info("Prometheus metrics integration completed")

# Utility functions for metric validation and debugging

def validate_metrics_export(metrics_server: PrometheusMetricsServer) -> Dict[str, Any]:
    """Validate that metrics are being exported correctly"""
    
    validation_results = {
        'total_metrics': 0,
        'metric_families': [],
        'sample_metrics': {},
        'errors': []
    }
    
    try:
        metrics_text = metrics_server.metrics.get_metrics_text()
        lines = metrics_text.split('\n')
        
        current_family = None
        
        for line in lines:
            line = line.strip()
            
            if not line or line.startswith('#'):
                if line.startswith('# HELP'):
                    current_family = line.split()[2]
                    validation_results['metric_families'].append(current_family)
                continue
            
            # Count metric samples
            validation_results['total_metrics'] += 1
            
            # Extract sample metrics
            if '{' in line:
                metric_name = line.split('{')[0]
                if metric_name not in validation_results['sample_metrics']:
                    validation_results['sample_metrics'][metric_name] = []
                validation_results['sample_metrics'][metric_name].append(line)
        
        validation_results['status'] = 'valid'
        
    except Exception as e:
        validation_results['errors'].append(str(e))
        validation_results['status'] = 'error'
    
    return validation_results

def generate_sample_metrics() -> str:
    """Generate sample metrics for testing"""
    
    server = PrometheusMetricsServer(port=0)  # Don't start server
    
    # Create sample enhanced metrics
    from enhanced_network_collector import EnhancedNetworkMetrics
    
    sample_metrics = EnhancedNetworkMetrics(
        timestamp=time.time(),
        target_host='google.com',
        tcp_handshake_time=25.5,
        icmp_ping_time=12.3,
        dns_resolve_time=8.7,
        tcp_connect_time=15.2,
        tcp_ssl_handshake_time=45.8,
        http_response_time=156.3,
        http_first_byte_time=89.4,
        packet_loss=0.5,
        jitter=2.1,
        burst_loss_rate=0.1,
        out_of_order_packets=0.0,
        duplicate_packets=0.0,
        bandwidth_download=85.2,
        bandwidth_upload=12.4,
        concurrent_connections=5,
        connection_setup_rate=2.3,
        http_status_code=200,
        http_content_length=1024,
        certificate_days_remaining=45,
        redirect_count=1,
        interface_utilization=15.6,
        interface_errors=0,
        interface_drops=0,
        interface_collisions=0,
        hop_count=8,
        path_mtu=1500,
        route_changes=0,
        mos_score=4.2,
        r_factor=85.6,
        delay_variation=1.8,
        connection_errors=0,
        dns_errors=0,
        timeout_errors=0,
        source_interface='eth0',
        network_type='ethernet',
        measurement_duration=234.5
    )
    
    # Update metrics
    server.update_metrics(sample_metrics)
    
    return server.metrics.get_metrics_text()

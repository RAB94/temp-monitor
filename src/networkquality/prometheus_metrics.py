#!/usr/bin/env python3
# src/networkquality/prometheus_metrics.py
"""
Prometheus metrics export for NetworkQuality-RS measurements
"""

import time
import logging
import threading
from typing import Dict, Any, Optional
from prometheus_client import Gauge, Counter, Histogram, Info, REGISTRY as DEFAULT_REGISTRY

logger = logging.getLogger(__name__)

# Thread-safe singleton implementation
_instance_lock = threading.Lock()

class NetworkQualityPrometheusMetrics:
    """Prometheus metrics collector for NetworkQuality-RS data"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls, registry=None):
        """Implement singleton pattern"""
        if cls._instance is None:
            with _instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, registry=None):
        """Initialize NetworkQuality Prometheus metrics"""
        
        # Skip if already initialized
        if NetworkQualityPrometheusMetrics._initialized:
            logger.debug("NetworkQuality metrics already initialized, skipping")
            return
        
        with _instance_lock:
            # Double-check
            if NetworkQualityPrometheusMetrics._initialized:
                return
            
            try:
                # Use provided registry or default
                if registry is None:
                    # Check if metrics already exist in default registry
                    try:
                        # Try to create a test metric to see if we can
                        test_gauge = Gauge('networkquality_test_metric', 'Test metric', registry=DEFAULT_REGISTRY)
                        # If successful, remove it and use default registry
                        DEFAULT_REGISTRY.unregister(test_gauge)
                        registry = DEFAULT_REGISTRY
                    except:
                        # Metrics might already exist, proceed without registry
                        logger.warning("NetworkQuality metrics may already exist in default registry")
                        registry = None
                
                logger.info(f"Initializing NetworkQuality metrics with registry: {registry is not None}")
                
                # Core RPM metrics
                self.rpm_download = Gauge(
                    'networkquality_rpm_download',
                    'NetworkQuality download RPM (Responsiveness Per Minute)',
                    ['target_host'],
                    registry=registry
                )
                
                self.rpm_upload = Gauge(
                    'networkquality_rpm_upload', 
                    'NetworkQuality upload RPM (Responsiveness Per Minute)',
                    ['target_host'],
                    registry=registry
                )
                
                self.rpm_average = Gauge(
                    'networkquality_rpm_average',
                    'NetworkQuality average RPM',
                    ['target_host'],
                    registry=registry
                )
                
                # RTT metrics
                self.base_rtt = Gauge(
                    'networkquality_base_rtt_milliseconds',
                    'NetworkQuality base RTT in milliseconds',
                    ['target_host'],
                    registry=registry
                )
                
                self.loaded_rtt_download = Gauge(
                    'networkquality_loaded_rtt_download_milliseconds',
                    'NetworkQuality loaded download RTT in milliseconds',
                    ['target_host'],
                    registry=registry
                )
                
                self.loaded_rtt_upload = Gauge(
                    'networkquality_loaded_rtt_upload_milliseconds',
                    'NetworkQuality loaded upload RTT in milliseconds', 
                    ['target_host'],
                    registry=registry
                )
                
                # Bufferbloat metrics
                self.download_bufferbloat = Gauge(
                    'networkquality_download_bufferbloat_milliseconds',
                    'NetworkQuality download bufferbloat in milliseconds',
                    ['target_host'],
                    registry=registry
                )
                
                self.upload_bufferbloat = Gauge(
                    'networkquality_upload_bufferbloat_milliseconds',
                    'NetworkQuality upload bufferbloat in milliseconds',
                    ['target_host'],
                    registry=registry
                )
                
                self.max_bufferbloat = Gauge(
                    'networkquality_max_bufferbloat_milliseconds',
                    'NetworkQuality maximum bufferbloat in milliseconds',
                    ['target_host'],
                    registry=registry
                )
                
                # Bufferbloat severity (encoded as numeric)
                self.bufferbloat_severity = Gauge(
                    'networkquality_bufferbloat_severity',
                    'NetworkQuality bufferbloat severity (0=none, 1=mild, 2=moderate, 3=severe, -1=unknown)',
                    ['target_host', 'severity'],
                    registry=registry
                )
                
                # Throughput metrics
                self.download_throughput = Gauge(
                    'networkquality_download_throughput_mbps',
                    'NetworkQuality download throughput in Mbps',
                    ['target_host'],
                    registry=registry
                )
                
                self.upload_throughput = Gauge(
                    'networkquality_upload_throughput_mbps',
                    'NetworkQuality upload throughput in Mbps',
                    ['target_host'],
                    registry=registry
                )
                
                # Quality metrics
                self.overall_quality_score = Gauge(
                    'networkquality_overall_quality_score',
                    'NetworkQuality overall quality score (0-1000)',
                    ['target_host'],
                    registry=registry
                )
                
                self.quality_rating = Gauge(
                    'networkquality_quality_rating',
                    'NetworkQuality rating (0=error, 1=poor, 2=fair, 3=good, 4=excellent, -1=unknown)',
                    ['target_host', 'rating'],
                    registry=registry
                )
                
                # Responsiveness scores
                self.download_responsiveness_score = Gauge(
                    'networkquality_download_responsiveness_score',
                    'NetworkQuality download responsiveness score',
                    ['target_host'],
                    registry=registry
                )
                
                self.upload_responsiveness_score = Gauge(
                    'networkquality_upload_responsiveness_score',
                    'NetworkQuality upload responsiveness score',
                    ['target_host'],
                    registry=registry
                )
                
                # Congestion detection
                self.congestion_detected = Gauge(
                    'networkquality_congestion_detected',
                    'NetworkQuality congestion detection (0=no, 1=yes)',
                    ['target_host'],
                    registry=registry
                )
                
                # Measurement metadata
                self.measurement_duration = Gauge(
                    'networkquality_measurement_duration_milliseconds',
                    'NetworkQuality measurement duration in milliseconds',
                    ['target_host'],
                    registry=registry
                )
                
                self.measurement_timestamp = Gauge(
                    'networkquality_measurement_timestamp',
                    'NetworkQuality measurement timestamp',
                    ['target_host'],
                    registry=registry
                )
                
                # Counters for tracking
                self.total_measurements = Counter(
                    'networkquality_measurements_total',
                    'Total number of NetworkQuality measurements',
                    ['target_host', 'result'],
                    registry=registry
                )
                
                self.error_count = Counter(
                    'networkquality_errors_total',
                    'Total number of NetworkQuality measurement errors',
                    ['target_host', 'error_type'],
                    registry=registry
                )
                
                # Histograms for distribution analysis
                self.rpm_histogram = Histogram(
                    'networkquality_rpm_distribution',
                    'Distribution of NetworkQuality RPM values',
                    ['target_host', 'direction'],
                    buckets=[0, 50, 100, 200, 300, 500, 700, 1000, 1500, 2000, float('inf')],
                    registry=registry
                )
                
                self.bufferbloat_histogram = Histogram(
                    'networkquality_bufferbloat_distribution_milliseconds',
                    'Distribution of NetworkQuality bufferbloat values',
                    ['target_host'],
                    buckets=[0, 5, 10, 20, 30, 50, 75, 100, 150, 200, float('inf')],
                    registry=registry
                )
                
                # Info metric for configuration
                self.config_info = Info(
                    'networkquality_config',
                    'NetworkQuality configuration information',
                    registry=registry
                )
                
                NetworkQualityPrometheusMetrics._initialized = True
                logger.info("NetworkQuality Prometheus metrics initialized successfully")
                
            except ValueError as ve:
                if "Duplicated timeseries" in str(ve):
                    logger.error("NetworkQuality metrics already exist in registry")
                    # Mark as initialized to prevent repeated attempts
                    NetworkQualityPrometheusMetrics._initialized = True
                raise
            except Exception as e:
                logger.error(f"Failed to initialize NetworkQuality metrics: {e}")
                raise
    
    def update_metrics(self, metrics_data: Dict[str, Any]):
        """Update Prometheus metrics from NetworkQuality ResponsivenessMetrics"""
        
        target_host = metrics_data.get('target_host', 'unknown')
        
        logger.debug(f"Updating NetworkQuality metrics for {target_host}")
        logger.debug(f"RPM values - download: {metrics_data.get('rpm_download')}, "
                     f"upload: {metrics_data.get('rpm_upload')}, "
                     f"average: {metrics_data.get('rpm_average')}")
        
        try:
            # Core RPM metrics
            if metrics_data.get('rpm_download') is not None:
                self.rpm_download.labels(target_host=target_host).set(metrics_data['rpm_download'])
                self.rpm_histogram.labels(target_host=target_host, direction='download').observe(metrics_data['rpm_download'])
            
            if metrics_data.get('rpm_upload') is not None:
                self.rpm_upload.labels(target_host=target_host).set(metrics_data['rpm_upload'])
                self.rpm_histogram.labels(target_host=target_host, direction='upload').observe(metrics_data['rpm_upload'])
            
            if metrics_data.get('rpm_average') is not None:
                self.rpm_average.labels(target_host=target_host).set(metrics_data['rpm_average'])
            
            # RTT metrics
            if metrics_data.get('base_rtt_ms') is not None:
                self.base_rtt.labels(target_host=target_host).set(metrics_data['base_rtt_ms'])
            
            if metrics_data.get('loaded_rtt_download_ms') is not None:
                self.loaded_rtt_download.labels(target_host=target_host).set(metrics_data['loaded_rtt_download_ms'])
            
            if metrics_data.get('loaded_rtt_upload_ms') is not None:
                self.loaded_rtt_upload.labels(target_host=target_host).set(metrics_data['loaded_rtt_upload_ms'])
            
            # Bufferbloat metrics
            if metrics_data.get('download_bufferbloat_ms') is not None:
                self.download_bufferbloat.labels(target_host=target_host).set(metrics_data['download_bufferbloat_ms'])
            
            if metrics_data.get('upload_bufferbloat_ms') is not None:
                self.upload_bufferbloat.labels(target_host=target_host).set(metrics_data['upload_bufferbloat_ms'])
            
            if metrics_data.get('max_bufferbloat_ms') is not None:
                max_bb = metrics_data['max_bufferbloat_ms']
                self.max_bufferbloat.labels(target_host=target_host).set(max_bb)
                self.bufferbloat_histogram.labels(target_host=target_host).observe(max_bb)
            
            # Bufferbloat severity
            severity_map = {'none': 0, 'mild': 1, 'moderate': 2, 'severe': 3, 'unknown': -1}
            severity = metrics_data.get('bufferbloat_severity', 'unknown')
            if severity in severity_map:
                # Reset all severity labels
                for sev_name in ['none', 'mild', 'moderate', 'severe']:
                    self.bufferbloat_severity.labels(target_host=target_host, severity=sev_name).set(
                        1 if sev_name == severity else 0
                    )
            
            # Throughput metrics
            if metrics_data.get('download_throughput_mbps') is not None:
                self.download_throughput.labels(target_host=target_host).set(metrics_data['download_throughput_mbps'])
            
            if metrics_data.get('upload_throughput_mbps') is not None:
                self.upload_throughput.labels(target_host=target_host).set(metrics_data['upload_throughput_mbps'])
            
            # Quality metrics
            if metrics_data.get('overall_quality_score') is not None:
                self.overall_quality_score.labels(target_host=target_host).set(metrics_data['overall_quality_score'])
            
            # Quality rating
            rating_map = {'error': 0, 'poor': 1, 'fair': 2, 'good': 3, 'excellent': 4, 'unknown': -1}
            rating = metrics_data.get('quality_rating', 'unknown')
            if rating in rating_map:
                # Reset all rating labels
                for rating_name in ['error', 'poor', 'fair', 'good', 'excellent']:
                    self.quality_rating.labels(target_host=target_host, rating=rating_name).set(
                        1 if rating_name == rating else 0
                    )
            
            # Responsiveness scores
            if metrics_data.get('download_responsiveness_score') is not None:
                self.download_responsiveness_score.labels(target_host=target_host).set(metrics_data['download_responsiveness_score'])
            
            if metrics_data.get('upload_responsiveness_score') is not None:
                self.upload_responsiveness_score.labels(target_host=target_host).set(metrics_data['upload_responsiveness_score'])
            
            # Congestion detection
            congestion = metrics_data.get('congestion_detected')
            if congestion is not None:
                self.congestion_detected.labels(target_host=target_host).set(1 if congestion else 0)
            
            # Measurement metadata
            if metrics_data.get('measurement_duration_ms') is not None:
                self.measurement_duration.labels(target_host=target_host).set(metrics_data['measurement_duration_ms'])
            
            self.measurement_timestamp.labels(target_host=target_host).set(metrics_data.get('timestamp', time.time()))
            
            # Update counters
            if metrics_data.get('error'):
                self.total_measurements.labels(target_host=target_host, result='error').inc()
                self.error_count.labels(target_host=target_host, error_type='measurement_failed').inc()
            else:
                self.total_measurements.labels(target_host=target_host, result='success').inc()
            
            logger.debug(f"Successfully updated NetworkQuality metrics for {target_host}")
            
        except Exception as e:
            logger.error(f"Error updating NetworkQuality Prometheus metrics: {e}", exc_info=True)
            self.error_count.labels(target_host=target_host, error_type='metric_update_failed').inc()
    
    def set_config_info(self, config_data: Dict[str, Any]):
        """Set configuration info metric"""
        try:
            # Convert config to string values for Info metric
            config_info = {}
            for key, value in config_data.items():
                if isinstance(value, (dict, list)):
                    config_info[key] = str(value)
                else:
                    config_info[key] = str(value)
            
            self.config_info.info(config_info)
            logger.debug("Updated NetworkQuality configuration info metric")
            
        except Exception as e:
            logger.error(f"Error updating NetworkQuality config info metric: {e}")

# Global singleton getter
def get_or_create_nq_metrics(registry=None):
    """Get or create the singleton NetworkQuality metrics instance"""
    return NetworkQualityPrometheusMetrics(registry=registry)

# Helper function to update metrics without creating instance
def update_networkquality_metrics_directly(metrics_data: Dict[str, Any]) -> bool:
    """Update NetworkQuality metrics directly without creating new instance"""
    try:
        # Try to get the existing instance
        if NetworkQualityPrometheusMetrics._instance:
            NetworkQualityPrometheusMetrics._instance.update_metrics(metrics_data)
            logger.debug("Updated NetworkQuality metrics via existing instance")
            return True
        else:
            logger.warning("No existing NetworkQuality metrics instance found")
            return False
            
    except Exception as e:
        logger.error(f"Failed to update NetworkQuality metrics directly: {e}")
        return False

# Integration function for the main MetricsAggregator
def integrate_networkquality_metrics(metrics_aggregator, nq_config=None):
    """Integrate NetworkQuality metrics with existing MetricsAggregator"""
    
    if not hasattr(metrics_aggregator, 'nq_metrics'):
        try:
            # Get the registry from the aggregator
            registry = getattr(metrics_aggregator.metrics_server.metrics, 'registry', None)
            
            # Create or get the metrics instance
            metrics_aggregator.nq_metrics = get_or_create_nq_metrics(registry=registry)
            
            # Set config info if available
            if nq_config and metrics_aggregator.nq_metrics:
                config_data = {
                    'enabled': getattr(nq_config, 'enabled', False),
                    'test_duration': getattr(nq_config.client, 'test_duration', None) if hasattr(nq_config, 'client') else None,
                    'max_connections': getattr(nq_config.client, 'max_loaded_connections', None) if hasattr(nq_config, 'client') else None,
                    'server_type': getattr(nq_config.server, 'type', None) if hasattr(nq_config, 'server') else None,
                    'binary_path': getattr(nq_config.client, 'binary_path', None) if hasattr(nq_config, 'client') else None
                }
                metrics_aggregator.nq_metrics.set_config_info(config_data)
            
            logger.info("NetworkQuality metrics integrated with MetricsAggregator")
        except Exception as e:
            logger.error(f"Failed to integrate NetworkQuality metrics: {e}")
    
    return getattr(metrics_aggregator, 'nq_metrics', None)

# Extension method for MetricsAggregator
def add_networkquality_metrics_method(metrics_aggregator):
    """Add NetworkQuality metrics method to existing MetricsAggregator"""
    
    def add_networkquality_metrics(self, nq_metrics_data):
        """Add NetworkQuality metrics to Prometheus export"""
        if hasattr(self, 'nq_metrics') and self.nq_metrics:
            try:
                if hasattr(nq_metrics_data, 'to_dict'):
                    data = nq_metrics_data.to_dict()
                else:
                    data = nq_metrics_data
                
                self.nq_metrics.update_metrics(data)
                logger.debug(f"Updated NetworkQuality metrics for {data.get('target_host', 'unknown')}")
                
            except Exception as e:
                logger.error(f"Error adding NetworkQuality metrics to aggregator: {e}")
        else:
            # Try to create on demand
            try:
                self.nq_metrics = get_or_create_nq_metrics(registry=None)
                if self.nq_metrics:
                    data = nq_metrics_data.to_dict() if hasattr(nq_metrics_data, 'to_dict') else nq_metrics_data
                    self.nq_metrics.update_metrics(data)
            except Exception as e:
                logger.error(f"Failed to create NetworkQuality metrics on demand: {e}")
    
    # Bind the method to the metrics_aggregator instance
    import types
    metrics_aggregator.add_networkquality_metrics = types.MethodType(add_networkquality_metrics, metrics_aggregator)

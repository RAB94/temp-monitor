#!/usr/bin/env python3
# src/networkquality/prometheus_metrics.py
"""
Prometheus metrics export for NetworkQuality-RS measurements
"""

import time
import logging
from typing import Dict, Any, Optional
from prometheus_client import Gauge, Counter, Histogram, Info

logger = logging.getLogger(__name__)

class NetworkQualityPrometheusMetrics:
    """Prometheus metrics collector for NetworkQuality-RS data"""
    
    def __init__(self, registry=None):
        """Initialize NetworkQuality Prometheus metrics"""
        
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
            'NetworkQuality bufferbloat severity (0=none, 1=mild, 2=moderate, 3=severe)',
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
            'NetworkQuality rating (0=error, 1=poor, 2=fair, 3=good, 4=excellent)',
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
        
        logger.info("NetworkQuality Prometheus metrics initialized")
    
    def update_metrics(self, metrics_data: Dict[str, Any]):
        """Update Prometheus metrics from NetworkQuality ResponsivenessMetrics"""
        
        target_host = metrics_data.get('target_host', 'unknown')
        
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
                for sev_name, sev_val in severity_map.items():
                    if sev_name != 'unknown':
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
            rating_map = {'error': 0, 'poor': 1, 'fair': 2, 'good': 3, 'excellent': 4}
            rating = metrics_data.get('quality_rating', 'unknown')
            if rating in rating_map:
                # Reset all rating labels
                for rating_name, rating_val in rating_map.items():
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
            
            logger.debug(f"Updated NetworkQuality Prometheus metrics for {target_host}")
            
        except Exception as e:
            logger.error(f"Error updating NetworkQuality Prometheus metrics: {e}")
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

# Integration function for the main MetricsAggregator
def integrate_networkquality_metrics(metrics_aggregator, nq_config=None):
    """Integrate NetworkQuality metrics with existing MetricsAggregator"""
    
    if not hasattr(metrics_aggregator, 'nq_metrics'):
        metrics_aggregator.nq_metrics = NetworkQualityPrometheusMetrics(
            registry=getattr(metrics_aggregator, 'registry', None)
        )
        
        # Set config info if available
        if nq_config:
            config_data = {
                'enabled': getattr(nq_config, 'enabled', False),
                'test_duration': getattr(nq_config.client, 'test_duration', None) if hasattr(nq_config, 'client') else None,
                'max_connections': getattr(nq_config.client, 'max_loaded_connections', None) if hasattr(nq_config, 'client') else None,
                'server_type': getattr(nq_config.server, 'type', None) if hasattr(nq_config, 'server') else None,
                'binary_path': getattr(nq_config.client, 'binary_path', None) if hasattr(nq_config, 'client') else None
            }
            metrics_aggregator.nq_metrics.set_config_info(config_data)
        
        logger.info("NetworkQuality metrics integrated with MetricsAggregator")
    
    return metrics_aggregator.nq_metrics

# Extension method for MetricsAggregator
def add_networkquality_metrics_method(metrics_aggregator):
    """Add NetworkQuality metrics method to existing MetricsAggregator"""
    
    def add_networkquality_metrics(self, nq_metrics_data):
        """Add NetworkQuality metrics to Prometheus export"""
        if hasattr(self, 'nq_metrics'):
            try:
                if hasattr(nq_metrics_data, 'to_dict'):
                    data = nq_metrics_data.to_dict()
                else:
                    data = nq_metrics_data
                
                self.nq_metrics.update_metrics(data)
                
            except Exception as e:
                logger.error(f"Error adding NetworkQuality metrics to aggregator: {e}")
    
    # Bind the method to the metrics_aggregator instance
    import types
    metrics_aggregator.add_networkquality_metrics = types.MethodType(add_networkquality_metrics, metrics_aggregator)

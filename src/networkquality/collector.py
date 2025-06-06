#!/usr/bin/env python3
# src/networkquality/collector.py
"""
Network quality collector using the networkquality binary (Cloudflare responsiveness tool).
"""

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import statistics
import json

from .bridge import NetworkQualityBinaryBridge, NetworkQualityMeasurement
from ..utils.database import Database

logger = logging.getLogger(__name__)

@dataclass
class ResponsivenessMetrics:
    """
    Comprehensive responsiveness and network quality metrics derived from
    the networkquality tool (Cloudflare responsiveness measurements).
    """
    timestamp: float
    target_host: str  # Will be "cloudflare" for this tool

    # Raw metrics from NetworkQualityMeasurement
    rpm_download: Optional[float] = None
    rpm_upload: Optional[float] = None
    base_rtt_ms: Optional[float] = None
    loaded_rtt_download_ms: Optional[float] = None
    loaded_rtt_upload_ms: Optional[float] = None
    download_throughput_mbps: Optional[float] = None
    upload_throughput_mbps: Optional[float] = None
    download_responsiveness_score: Optional[float] = None
    upload_responsiveness_score: Optional[float] = None

    # Derived metrics
    rpm_average: Optional[float] = None
    download_bufferbloat_ms: Optional[float] = None
    upload_bufferbloat_ms: Optional[float] = None
    max_bufferbloat_ms: Optional[float] = None
    bufferbloat_severity: str = "unknown"

    overall_quality_score: Optional[float] = None
    quality_rating: str = "unknown"

    congestion_detected: Optional[bool] = None
    measurement_duration_ms: Optional[float] = None
    error: Optional[str] = None
    recommendations: List[str] = None

    def __post_init__(self):
        if self.recommendations is None:
            self.recommendations = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class NetworkQualityCollector:
    """
    Collector for network quality metrics using NetworkQualityBinaryBridge.
    This version works with the Cloudflare responsiveness tool.
    """

    def __init__(self, nq_config: Any, database: Optional[Database] = None):
        """
        Initializes the collector.
        Args:
            nq_config: An instance of NetworkQualityRSConfig from src.config.py
            database: Optional database instance for storing results.
        """
        self.nq_config = nq_config
        self.database = database
        self.logger = logger

        # Initialize bridge with the client sub-config
        client_config_dict = {
            'binary_path': getattr(nq_config.client, 'binary_path', '/usr/local/bin/networkquality'),
            'test_duration': getattr(nq_config.client, 'test_duration', 12000),
            'max_loaded_connections': getattr(nq_config.client, 'max_loaded_connections', 8)
        }
        self.bridge = NetworkQualityBinaryBridge(client_config_dict)

        # Since this tool doesn't use custom servers, set target to "cloudflare"
        self.server_url = "cloudflare"

        # Test parameters from client config
        self.test_duration_ms = getattr(nq_config.client, 'test_duration', 12000)
        self.max_connections = getattr(nq_config.client, 'max_loaded_connections', 8)

        # Classification thresholds from config
        self.thresholds_config = nq_config.thresholds if hasattr(nq_config, 'thresholds') else {}
        self.default_thresholds = {
            'bufferbloat_ms': {'mild': 30, 'moderate': 60, 'severe': 100},
            'rpm': {'poor': 100, 'fair': 300, 'good': 600, 'excellent': 800},
            'quality_score': {'poor': 200, 'fair': 500, 'good': 750, 'excellent': 900}
        }

        # Adaptive testing
        testing_conf = nq_config.testing if hasattr(nq_config, 'testing') else {}
        self.adaptive_intervals = testing_conf.get('adaptive_intervals', {
            'excellent': 3600, 'good': 1800, 'fair': 600, 'poor': 300, 'error': 300
        })
        self.default_interval = testing_conf.get('default_interval_seconds', 300)
        self.target_next_test_time = {}

    async def collect_network_quality(self, target_host: Optional[str] = None, force: bool = False) -> ResponsivenessMetrics:
        """
        Collects network quality metrics using the Cloudflare responsiveness tool.
        target_host is ignored since this tool uses predefined endpoints.
        """
        measurement_target = "cloudflare"  # This tool always measures against Cloudflare
        current_time = time.time()

        # Adaptive testing logic
        testing_strategy = getattr(self.nq_config.testing, 'strategy', 'fixed')
        if not force and testing_strategy == 'adaptive':
            next_test_time = self.target_next_test_time.get(measurement_target, 0)
            if current_time < next_test_time:
                self.logger.debug(f"Skipping NetworkQuality test for {measurement_target}, next test at {time.ctime(next_test_time)}")
                return self._create_error_metrics(measurement_target, "Skipped due to adaptive interval")

        self.logger.info(f"Collecting NetworkQuality metrics using Cloudflare endpoints...")
        test_start_time = time.monotonic()

        try:
            raw_measurement = await self.bridge.measure(
                duration_ms=self.test_duration_ms,
                max_connections=self.max_connections
            )
            measurement_duration_ms = (time.monotonic() - test_start_time) * 1000

            if raw_measurement.error:
                self.logger.warning(f"NQRS measurement error: {raw_measurement.error}")
                metrics = self._create_error_metrics(measurement_target, raw_measurement.error, measurement_duration_ms)
            else:
                metrics = self._process_raw_measurement(raw_measurement, measurement_duration_ms)

        except Exception as e:
            measurement_duration_ms = (time.monotonic() - test_start_time) * 1000
            self.logger.exception(f"Unexpected error during NetworkQuality collection: {e}")
            metrics = self._create_error_metrics(measurement_target, str(e), measurement_duration_ms)

        # Update adaptive testing interval
        if testing_strategy == 'adaptive':
            next_interval = self.adaptive_intervals.get(metrics.quality_rating, self.default_interval)
            self.target_next_test_time[measurement_target] = current_time + next_interval

        if self.database and metrics.error is None:
            await self._store_metrics(metrics)

        return metrics

    def _get_threshold(self, category: str, level: str) -> float:
        """Safely get a threshold value."""
        # Log what we're looking for
        logger.debug(f"Getting threshold for {category}.{level}")
        logger.debug(f"Config thresholds: {self.thresholds_config}")
        logger.debug(f"Default thresholds: {self.default_thresholds}")
        
        value = None
        source = "not found"
        
        # First try config thresholds
        if category in self.thresholds_config:
            logger.debug(f"Found category {category} in config: {self.thresholds_config[category]}")
            if level in self.thresholds_config[category]:
                value = self.thresholds_config[category][level]
                source = "config"
                logger.debug(f"Found {category}.{level} = {value} in config")
        
        # Fall back to defaults if not found
        if value is None and category in self.default_thresholds:
            logger.debug(f"Checking defaults for {category}.{level}")
            if level in self.default_thresholds[category]:
                value = self.default_thresholds[category][level]
                source = "defaults"
                logger.debug(f"Found {category}.{level} = {value} in defaults")
        
        # Convert to float
        if value is not None:
            try:
                result = float(value)
                logger.debug(f"Threshold {category}.{level} = {result} (from {source})")
                return result
            except (ValueError, TypeError) as e:
                logger.error(f"Error converting threshold {category}.{level} = {value} to float: {e}")
                return 0.0
        else:
            logger.warning(f"Threshold not found for {category}.{level}, returning 0")
            return 0.0

    def _process_raw_measurement(self, raw: NetworkQualityMeasurement, duration_ms: float) -> ResponsivenessMetrics:
        """Process raw measurement and calculate derived metrics"""
        
        dl_rpm = raw.rpm_download
        ul_rpm = raw.rpm_upload
        base_rtt = raw.base_rtt_ms
        loaded_dl_rtt = raw.loaded_rtt_download_ms
        loaded_ul_rtt = raw.loaded_rtt_upload_ms

        rpm_average = None
        if dl_rpm is not None and ul_rpm is not None:
            rpm_average = (dl_rpm + ul_rpm) / 2

        dl_bufferbloat = None
        if loaded_dl_rtt is not None and base_rtt is not None:
            dl_bufferbloat = max(0, loaded_dl_rtt - base_rtt)

        ul_bufferbloat = None
        if loaded_ul_rtt is not None and base_rtt is not None:
            ul_bufferbloat = max(0, loaded_ul_rtt - base_rtt)

        max_bufferbloat = None
        if dl_bufferbloat is not None and ul_bufferbloat is not None:
            max_bufferbloat = max(dl_bufferbloat, ul_bufferbloat)
        elif dl_bufferbloat is not None:
            max_bufferbloat = dl_bufferbloat
        elif ul_bufferbloat is not None:
            max_bufferbloat = ul_bufferbloat

        bufferbloat_severity = "unknown"
        if max_bufferbloat is not None:
            severe_threshold = float(self._get_threshold('bufferbloat_ms', 'severe'))
            moderate_threshold = float(self._get_threshold('bufferbloat_ms', 'moderate'))
            mild_threshold = float(self._get_threshold('bufferbloat_ms', 'mild'))
            
            if max_bufferbloat >= severe_threshold:
                bufferbloat_severity = "severe"
            elif max_bufferbloat >= moderate_threshold:
                bufferbloat_severity = "moderate"
            elif max_bufferbloat >= mild_threshold:
                bufferbloat_severity = "mild"
            else:
                bufferbloat_severity = "none"

        # Calculate quality score
        quality_score = 0.0
        if rpm_average is not None:
            quality_score += min(rpm_average * 0.4, 400)
        if max_bufferbloat is not None:
            severe_threshold = float(self._get_threshold('bufferbloat_ms', 'severe'))
            moderate_threshold = float(self._get_threshold('bufferbloat_ms', 'moderate'))
            mild_threshold = float(self._get_threshold('bufferbloat_ms', 'mild'))
            
            if max_bufferbloat > severe_threshold:
                quality_score -= 300
            elif max_bufferbloat > moderate_threshold:
                quality_score -= 150
            elif max_bufferbloat > mild_threshold:
                quality_score -= 75
        if raw.download_throughput_mbps is not None and raw.upload_throughput_mbps is not None:
            quality_score += min((raw.download_throughput_mbps + raw.upload_throughput_mbps) * 2, 300)

        quality_score = max(0.0, min(1000.0, quality_score))

        # FIX: Correct quality rating based on RPM thresholds with proper numeric comparison
        quality_rating = "unknown"
        if rpm_average is not None:
            # Get thresholds and ensure they are floats
            excellent_threshold = float(self._get_threshold('rpm', 'excellent'))
            good_threshold = float(self._get_threshold('rpm', 'good'))
            fair_threshold = float(self._get_threshold('rpm', 'fair'))
            poor_threshold = float(self._get_threshold('rpm', 'poor'))
            
            # Log for debugging
            logger.debug(f"RPM average: {rpm_average}, thresholds: excellent={excellent_threshold}, "
                         f"good={good_threshold}, fair={fair_threshold}, poor={poor_threshold}")
            
            # Determine rating (check from highest to lowest)
            if rpm_average >= excellent_threshold:
                quality_rating = "excellent"
            elif rpm_average >= good_threshold:
                quality_rating = "good"
            elif rpm_average >= fair_threshold:
                quality_rating = "fair"
            elif rpm_average >= poor_threshold:
                quality_rating = "poor"
            else:
                quality_rating = "poor"  # Below all thresholds
            
            logger.debug(f"Quality rating for RPM {rpm_average}: {quality_rating}")
            
            # Downgrade rating if severe bufferbloat
            if bufferbloat_severity == "severe" and quality_rating in ["excellent", "good"]:
                logger.debug(f"Downgrading quality rating from {quality_rating} to fair due to severe bufferbloat")
                quality_rating = "fair"
        else:
            # Fallback to quality score if no RPM
            excellent_score = float(self._get_threshold('quality_score', 'excellent'))
            good_score = float(self._get_threshold('quality_score', 'good'))
            fair_score = float(self._get_threshold('quality_score', 'fair'))
            poor_score = float(self._get_threshold('quality_score', 'poor'))
            
            if quality_score >= excellent_score:
                quality_rating = "excellent"
            elif quality_score >= good_score:
                quality_rating = "good"
            elif quality_score >= fair_score:
                quality_rating = "fair"
            else:
                quality_rating = "poor"

        congestion_detected = bufferbloat_severity in ["moderate", "severe"] or \
                              (rpm_average is not None and rpm_average < float(self._get_threshold('rpm', 'fair')))

        metrics = ResponsivenessMetrics(
            timestamp=raw.timestamp,
            target_host=raw.target_server,
            rpm_download=dl_rpm,
            rpm_upload=ul_rpm,
            base_rtt_ms=base_rtt,
            loaded_rtt_download_ms=loaded_dl_rtt,
            loaded_rtt_upload_ms=loaded_ul_rtt,
            download_throughput_mbps=raw.download_throughput_mbps,
            upload_throughput_mbps=raw.upload_throughput_mbps,
            download_responsiveness_score=raw.download_responsiveness_score,
            upload_responsiveness_score=raw.upload_responsiveness_score,
            rpm_average=rpm_average,
            download_bufferbloat_ms=dl_bufferbloat,
            upload_bufferbloat_ms=ul_bufferbloat,
            max_bufferbloat_ms=max_bufferbloat,
            bufferbloat_severity=bufferbloat_severity,
            overall_quality_score=quality_score,
            quality_rating=quality_rating,
            congestion_detected=congestion_detected,
            measurement_duration_ms=duration_ms,
            error=raw.error
        )
        
        # Log final calculation
        rpm_str = f"{rpm_average:.1f}" if rpm_average is not None else "0"
        bb_str = f"{max_bufferbloat:.1f}" if max_bufferbloat is not None else "0"
        logger.info(f"Processed NQ metrics: RPM avg={rpm_str}, "
                    f"bufferbloat={bb_str}ms ({bufferbloat_severity}), "
                    f"quality_score={quality_score:.1f}, rating={quality_rating}")       

        metrics.recommendations = self._generate_recommendations(metrics)
        return metrics

    def _create_error_metrics(self, target_url: str, error_msg: str, duration_ms: Optional[float] = None) -> ResponsivenessMetrics:
        return ResponsivenessMetrics(
            timestamp=time.time(),
            target_host=target_url,
            error=error_msg,
            quality_rating="error",
            bufferbloat_severity="unknown",
            measurement_duration_ms=duration_ms
        )

    def _generate_recommendations(self, metrics: ResponsivenessMetrics) -> List[str]:
        recs = []
        if metrics.error:
            recs.append(f"Test failed: {metrics.error}. Check binary configuration and network connectivity.")
            return recs

        if metrics.bufferbloat_severity == "severe":
            recs.append("Severe bufferbloat detected. Consider enabling SQM/QoS on your router, "
                        "reducing concurrent network usage, or checking for faulty network equipment.")
        elif metrics.bufferbloat_severity == "moderate":
            recs.append("Moderate bufferbloat. Monitor during peak hours. "
                        "If issues persist, investigate network usage or consider QoS.")

        if metrics.rpm_average is not None:
            if metrics.rpm_average < self._get_threshold('rpm', 'poor'):
                recs.append(f"Very low responsiveness (RPM: {metrics.rpm_average:.0f}). "
                            "Real-time applications will suffer. Investigate network congestion or ISP issues.")
            elif metrics.rpm_average < self._get_threshold('rpm', 'fair'):
                recs.append(f"Low responsiveness (RPM: {metrics.rpm_average:.0f}). "
                            "May impact gaming or video conferencing.")

        if not recs and metrics.quality_rating in ["excellent", "good"]:
            recs.append("Network quality appears good.")
        elif not recs:
            recs.append("Review individual metrics for potential issues.")
        return recs

    async def _store_metrics(self, metrics: ResponsivenessMetrics):
        if not self.database or not self.database.db:
            return
        
        query = """
            INSERT INTO network_quality_rs_metrics (
                timestamp, target_host, rpm_download, rpm_upload, rpm_average,
                base_rtt_ms, loaded_rtt_download_ms, loaded_rtt_upload_ms,
                download_bufferbloat_ms, upload_bufferbloat_ms, bufferbloat_severity,
                download_throughput_mbps, upload_throughput_mbps, overall_quality_score, quality_rating,
                download_responsiveness_score, upload_responsiveness_score,
                congestion_detected, measurement_duration_ms, recommendations, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        recommendations_json = json.dumps(metrics.recommendations) if metrics.recommendations else None
        values = (
            metrics.timestamp, metrics.target_host, metrics.rpm_download, metrics.rpm_upload, metrics.rpm_average,
            metrics.base_rtt_ms, metrics.loaded_rtt_download_ms, metrics.loaded_rtt_upload_ms,
            metrics.download_bufferbloat_ms, metrics.upload_bufferbloat_ms, metrics.bufferbloat_severity,
            metrics.download_throughput_mbps, metrics.upload_throughput_mbps, metrics.overall_quality_score, metrics.quality_rating,
            metrics.download_responsiveness_score, metrics.upload_responsiveness_score,
            metrics.congestion_detected, metrics.measurement_duration_ms, recommendations_json, metrics.error
        )
        try:
            await self.database.db.execute(query, values)
            await self.database.db.commit()
            self.logger.debug(f"Stored NetworkQuality metrics for {metrics.target_host} to database.")
        except Exception as e:
            self.logger.error(f"Failed to store NetworkQuality metrics for {metrics.target_host}: {e}")

async def main_collector_test():
    """Test the collector with the actual networkquality binary"""
    logging.basicConfig(level=logging.DEBUG)
    
    # Mock config object that matches NetworkQualityRSConfig structure
    test_nq_config_obj = type('NetworkQualityRSConfigMock', (), {
        'enabled': True,
        'client': type('ClientMock', (), {
            'binary_path': "/usr/local/bin/networkquality",
            'test_duration': 12000,  # 12 seconds in milliseconds
            'max_loaded_connections': 8
        })(),
        'server': type('ServerMock', (), {
            'type': 'external',
            'url': None,
            'auto_start': False
        })(),
        'thresholds': {
            'bufferbloat_ms': {'mild': 25, 'moderate': 50, 'severe': 75},
            'rpm': {'poor': 150, 'fair': 350, 'good': 650, 'excellent': 850},
            'quality_score': {'poor': 250, 'fair': 550, 'good': 750, 'excellent': 950}
        },
        'testing': {
            'strategy': 'fixed',
            'default_interval_seconds': 10
        }
    })()

    collector = NetworkQualityCollector(test_nq_config_obj)

    logger.info("Testing NetworkQualityCollector with Cloudflare endpoints...")
    metrics = await collector.collect_network_quality()
    logger.info(f"Collected Metrics: {metrics.to_dict() if metrics else 'None'}")

    if metrics and metrics.error:
        logger.error(f"Collector returned an error: {metrics.error}")
    elif metrics:
        logger.info(f"Quality Rating: {metrics.quality_rating}")
        logger.info(f"Bufferbloat: {metrics.bufferbloat_severity} ({metrics.max_bufferbloat_ms if metrics.max_bufferbloat_ms is not None else 'N/A'} ms)")
        logger.info(f"RPM Avg: {metrics.rpm_average if metrics.rpm_average is not None else 'N/A'} RPM")
        logger.info(f"Recommendations: {metrics.recommendations}")

if __name__ == "__main__":
    print("NetworkQualityCollector defined. To test, uncomment asyncio.run(main_collector_test()) "
          "and ensure the networkquality binary is available.")
    # asyncio.run(main_collector_test())

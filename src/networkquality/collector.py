#!/usr/bin/env python3
# src/networkquality/collector.py
"""
Network quality collector using the networkquality-rs binary via NetworkQualityBinaryBridge.
"""

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import statistics
import numpy as np # For potential statistical calculations if needed later
import json # For storing recommendations

# Assuming bridge.py is in the same directory or accessible in PYTHONPATH
from .bridge import NetworkQualityBinaryBridge, NetworkQualityMeasurement
# Adjusted for typical project structure, assuming utils is a sibling to networkquality
from ..utils.database import Database

logger = logging.getLogger(__name__)

@dataclass
class ResponsivenessMetrics:
    """
    Comprehensive responsiveness and network quality metrics derived from
    the networkquality-rs tool.
    """
    timestamp: float
    target_host: str # This will be the measurement server URL

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
    bufferbloat_severity: str = "unknown"  # none, mild, moderate, severe

    overall_quality_score: Optional[float] = None # Example: 0-1000
    quality_rating: str = "unknown"  # Example: excellent, good, fair, poor, error

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
    """

    def __init__(self, nq_config: Any, database: Optional[Database] = None): # nq_config is NetworkQualityRSConfig
        """
        Initializes the collector.
        Args:
            nq_config: An instance of NetworkQualityRSConfig from src.config.py
            database: Optional database instance for storing results.
        """
        self.nq_config = nq_config # Store the NetworkQualityRSConfig object directly
        self.database = database
        self.logger = logger

        # Initialize bridge, passing the client sub-config (which is a dict in the original plan)
        # or directly if NetworkQualityBinaryBridge expects NetworkQualityRSClientConfig
        # For now, assuming NetworkQualityBinaryBridge expects a dict for its 'config' param.
        # If NetworkQualityBinaryBridge was updated to take NetworkQualityRSClientConfig, this would be:
        # self.bridge = NetworkQualityBinaryBridge(nq_config.client)
        client_config_dict = nq_config.client.__dict__ if hasattr(nq_config, 'client') else {}
        self.bridge = NetworkQualityBinaryBridge({'client': client_config_dict})


        # Server URL to test against - this is crucial
        self.server_url = getattr(nq_config.server, 'url', None)
        if not self.server_url and nq_config.server.type == 'self_hosted':
            # Construct for self_hosted if not explicitly set, and bind_address is known
            bind_addr = getattr(nq_config.server, 'bind_address', '127.0.0.1')
            port = getattr(nq_config.server, 'port', 9090)
            connect_address = '127.0.0.1' if bind_addr == '0.0.0.0' else bind_addr
            self.server_url = f"http://{connect_address}:{port}"


        if not self.server_url and nq_config.enabled:
            self.logger.error(
                "NetworkQuality server URL ('networkquality.server.url' or derived from self-hosted) "
                "is not configured. Measurements will not be performed."
            )

        # Test parameters from client config
        self.test_duration = getattr(nq_config.client, 'test_duration', 10)
        self.parallel_streams = getattr(nq_config.client, 'parallel_streams', 8)

        # Classification thresholds from config
        self.thresholds_config = nq_config.thresholds if hasattr(nq_config, 'thresholds') else {}
        self.default_thresholds = { # Default thresholds if not in config
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
        Collects network quality metrics for the configured server.
        The 'target_host' argument is mostly for consistency but the actual server tested against
        is self.server_url derived from networkquality.server.url or self-hosted settings.
        """
        measurement_server_url = self.server_url # Primarily use the configured server URL
        current_time = time.time()

        if not measurement_server_url:
            self.logger.warning("No NetworkQuality server URL specified for collector. Skipping measurement.")
            return self._create_error_metrics(target_host or "unknown_target", "Collector's server_url not configured")

        # Adaptive testing logic
        testing_strategy = getattr(self.nq_config.testing, 'strategy', 'fixed')
        if not force and testing_strategy == 'adaptive':
            next_test_time = self.target_next_test_time.get(measurement_server_url, 0)
            if current_time < next_test_time:
                self.logger.debug(f"Skipping NetworkQuality test for {measurement_server_url}, next test at {time.ctime(next_test_time)}")
                return self._create_error_metrics(measurement_server_url, "Skipped due to adaptive interval")

        self.logger.info(f"Collecting NetworkQuality metrics for server: {measurement_server_url}")
        test_start_time = time.monotonic()

        try:
            raw_measurement = await self.bridge.measure(
                server_url=measurement_server_url,
                duration=self.test_duration,
                parallel_streams=self.parallel_streams
            )
            measurement_duration_ms = (time.monotonic() - test_start_time) * 1000

            if raw_measurement.error:
                self.logger.warning(f"NetworkQuality measurement failed for {measurement_server_url}: {raw_measurement.error}")
                metrics = self._create_error_metrics(measurement_server_url, raw_measurement.error, measurement_duration_ms)
            else:
                metrics = self._process_raw_measurement(raw_measurement, measurement_duration_ms)

        except Exception as e:
            measurement_duration_ms = (time.monotonic() - test_start_time) * 1000
            self.logger.exception(f"Unexpected error during NetworkQuality collection for {measurement_server_url}: {e}")
            metrics = self._create_error_metrics(measurement_server_url, str(e), measurement_duration_ms)

        # Update adaptive testing interval
        if testing_strategy == 'adaptive':
            next_interval = self.adaptive_intervals.get(metrics.quality_rating, self.default_interval)
            self.target_next_test_time[measurement_server_url] = current_time + next_interval

        if self.database and metrics.error is None:
            await self._store_metrics(metrics)

        return metrics

    def _get_threshold(self, category: str, level: str) -> float:
        """Safely get a threshold value."""
        return self.thresholds_config.get(category, self.default_thresholds.get(category, {})).get(level, 0)


    def _process_raw_measurement(self, raw: NetworkQualityMeasurement, duration_ms: float) -> ResponsivenessMetrics:
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
            if max_bufferbloat >= self._get_threshold('bufferbloat_ms', 'severe'):
                bufferbloat_severity = "severe"
            elif max_bufferbloat >= self._get_threshold('bufferbloat_ms', 'moderate'):
                bufferbloat_severity = "moderate"
            elif max_bufferbloat >= self._get_threshold('bufferbloat_ms', 'mild'):
                bufferbloat_severity = "mild"
            else:
                bufferbloat_severity = "none"

        quality_score = 0.0
        if rpm_average is not None:
            quality_score += min(rpm_average * 0.4, 400) # Max 400 points for RPM (scaled)
        if max_bufferbloat is not None:
            # Higher penalty for higher bufferbloat
            if max_bufferbloat > self._get_threshold('bufferbloat_ms', 'severe'): quality_score -= 300
            elif max_bufferbloat > self._get_threshold('bufferbloat_ms', 'moderate'): quality_score -= 150
            elif max_bufferbloat > self._get_threshold('bufferbloat_ms', 'mild'): quality_score -= 75
        if raw.download_throughput_mbps is not None and raw.upload_throughput_mbps is not None:
            quality_score += min((raw.download_throughput_mbps + raw.upload_throughput_mbps) * 2, 300) # Max 300 for throughput

        quality_score = max(0.0, min(1000.0, quality_score))

        quality_rating = "unknown"
        if quality_score >= self._get_threshold('quality_score', 'excellent'): quality_rating = "excellent"
        elif quality_score >= self._get_threshold('quality_score', 'good'): quality_rating = "good"
        elif quality_score >= self._get_threshold('quality_score', 'fair'): quality_rating = "fair"
        else: quality_rating = "poor"

        congestion_detected = bufferbloat_severity in ["moderate", "severe"] or \
                              (rpm_average is not None and rpm_average < self._get_threshold('rpm', 'fair'))

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
            recs.append(f"Test failed: {metrics.error}. Check server and binary configuration.")
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
        if not self.database or not self.database.db: # Ensure db object is available
            return
        query = """
            INSERT INTO network_quality_rs_metrics (
                timestamp, target_host, rpm_download, rpm_upload, rpm_average,
                base_rtt_ms, loaded_rtt_download_ms, loaded_rtt_upload_ms,
                download_bufferbloat_ms, upload_bufferbloat_ms, bufferbloat_severity,
                download_mbps, upload_mbps, overall_quality_score, quality_rating,
                download_responsiveness_score, upload_responsiveness_score,
                congestion_detected, measurement_duration_ms, recommendations, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        # Ensure recommendations is a JSON string or None
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
    logging.basicConfig(level=logging.DEBUG)
    mock_db_path = "test_nq_collector.db"
    db = Database(mock_db_path)
    await db.initialize()

    try:
        await db.db.execute("""
            CREATE TABLE IF NOT EXISTS network_quality_rs_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp REAL, target_host TEXT,
                rpm_download REAL, rpm_upload REAL, rpm_average REAL, base_rtt_ms REAL,
                loaded_rtt_download_ms REAL, loaded_rtt_upload_ms REAL,
                download_bufferbloat_ms REAL, upload_bufferbloat_ms REAL, bufferbloat_severity TEXT,
                download_mbps REAL, upload_mbps REAL, overall_quality_score REAL, quality_rating TEXT,
                download_responsiveness_score REAL, upload_responsiveness_score REAL,
                congestion_detected BOOLEAN, measurement_duration_ms REAL, recommendations TEXT, error TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        await db.db.commit()
    except Exception as e:
        logger.error(f"Could not create test table: {e}")

    # This config now matches the structure of NetworkQualityRSConfig dataclass
    test_nq_config_obj = type('NetworkQualityRSConfigMock', (), {
        'enabled': True,
        'client': type('ClientMock', (), {
            'binary_path': "/usr/local/bin/networkquality", # ADJUST
            'test_duration': 7,
            'parallel_streams': 4
        })(),
        'server': type('ServerMock', (), {
            'type': 'self_hosted', # or 'external'
            'url': "http://localhost:9090", # ADJUST if external or self-hosted with different URL
            'auto_start': False, # For testing, assume server is already running or external
            'port': 9090,
            'bind_address':'127.0.0.1'
        })(),
        'thresholds': {
            'bufferbloat_ms': {'mild': 25, 'moderate': 50, 'severe': 75},
            'rpm': {'poor': 150, 'fair': 350, 'good': 650, 'excellent': 850},
            'quality_score': {'poor': 250, 'fair': 550, 'good': 750, 'excellent': 950}
        },
        'testing': {
            'strategy': 'fixed',
            'default_interval_seconds': 10 # Short for test
        }
    })()

    collector = NetworkQualityCollector(test_nq_config_obj, db)
    target_server = collector.server_url # Use the URL resolved by the collector

    logger.info(f"Testing NetworkQualityCollector against {target_server}...")
    metrics = await collector.collect_network_quality()
    logger.info(f"Collected Metrics: {metrics.to_dict() if metrics else 'None'}")

    if metrics and metrics.error:
        logger.error(f"Collector returned an error: {metrics.error}")
    elif metrics:
        logger.info(f"Quality Rating: {metrics.quality_rating}")
        logger.info(f"Bufferbloat: {metrics.bufferbloat_severity} ({metrics.max_bufferbloat_ms if metrics.max_bufferbloat_ms is not None else 'N/A'} ms)")
        logger.info(f"RPM Avg: {metrics.rpm_average if metrics.rpm_average is not None else 'N/A'} RPM")
        logger.info(f"Recommendations: {metrics.recommendations}")

    await db.close()
    Path(mock_db_path).unlink(missing_ok=True)

if __name__ == "__main__":
    # asyncio.run(main_collector_test())
    print("NetworkQualityCollector defined. To test, uncomment asyncio.run(main_collector_test()) "
          "and ensure the networkquality binary and a server are available, "
          "and paths/URLs in main_collector_test are correct.")

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

# Assuming bridge.py is in the same directory or accessible in PYTHONPATH
from .bridge import NetworkQualityBinaryBridge, NetworkQualityMeasurement
from ..utils.database import Database # Adjusted for typical project structure

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

    def __init__(self, config: Dict[str, Any], database: Optional[Database] = None):
        self.config = config.get('networkquality', {}) # Expects a 'networkquality' sub-config
        self.database = database # Optional: for storing results
        self.logger = logger

        # Initialize bridge
        self.bridge = NetworkQualityBinaryBridge(self.config)

        # Server URL to test against - this is crucial
        self.server_url = self.config.get('server', {}).get('url')
        if not self.server_url:
            self.logger.error(
                "NetworkQuality server URL ('networkquality.server.url') is not configured. "
                "Measurements will not be performed."
            )

        # Test parameters
        self.test_duration = self.config.get('client',{}).get('test_duration', 10)
        self.parallel_streams = self.config.get('client',{}).get('parallel_streams', 8)

        # Classification thresholds from config
        self.thresholds = self.config.get('thresholds', {
            'bufferbloat_ms': {'mild': 30, 'moderate': 60, 'severe': 100}, # in ms
            'rpm': {'poor': 100, 'fair': 300, 'good': 600, 'excellent': 800},
            # Overall quality score can be a composite, e.g. 0-1000
            'quality_score': {'poor': 200, 'fair': 500, 'good': 750, 'excellent': 900}
        })

        # Adaptive testing (optional, can be implemented if needed)
        self.adaptive_intervals = self.config.get('testing', {}).get('adaptive_intervals', {
            'excellent': 3600, 'good': 1800, 'fair': 600, 'poor': 300, 'error': 300
        })
        self.target_next_test_time = {}


    async def collect_network_quality(self, target_host: Optional[str] = None, force: bool = False) -> ResponsivenessMetrics:
        """
        Collects network quality metrics for the configured server or a specific target (if server_url can be dynamic).
        For networkquality-rs, target_host is typically the measurement server itself.
        """
        measurement_server_url = target_host or self.server_url
        current_time = time.time()

        if not measurement_server_url:
            self.logger.warning("No NetworkQuality server URL specified. Skipping measurement.")
            return self._create_error_metrics(measurement_server_url or "unknown", "Server URL not configured")

        if not force:
            next_test_time = self.target_next_test_time.get(measurement_server_url, 0)
            if current_time < next_test_time:
                self.logger.debug(f"Skipping NetworkQuality test for {measurement_server_url}, next test at {time.ctime(next_test_time)}")
                # Optionally return last known good result or specific "skipped" status
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
        next_interval = self.adaptive_intervals.get(metrics.quality_rating, self.adaptive_intervals['fair'])
        self.target_next_test_time[measurement_server_url] = current_time + next_interval

        if self.database and metrics.error is None: # Only store successful/processed metrics
            await self._store_metrics(metrics)

        return metrics

    def _process_raw_measurement(self, raw: NetworkQualityMeasurement, duration_ms: float) -> ResponsivenessMetrics:
        """Processes raw measurement data to compute derived metrics and classifications."""
        dl_rpm = raw.rpm_download
        ul_rpm = raw.rpm_upload
        base_rtt = raw.base_rtt_ms
        loaded_dl_rtt = raw.loaded_rtt_download_ms
        loaded_ul_rtt = raw.loaded_rtt_upload_ms

        # --- Derived Metrics ---
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


        # --- Classifications & Scores ---
        bufferbloat_severity = "unknown"
        if max_bufferbloat is not None:
            if max_bufferbloat >= self.thresholds['bufferbloat_ms']['severe']:
                bufferbloat_severity = "severe"
            elif max_bufferbloat >= self.thresholds['bufferbloat_ms']['moderate']:
                bufferbloat_severity = "moderate"
            elif max_bufferbloat >= self.thresholds['bufferbloat_ms']['mild']:
                bufferbloat_severity = "mild"
            else:
                bufferbloat_severity = "none"

        # Overall Quality Score (example heuristic, can be refined)
        # This needs to be carefully designed based on how RPM, RTT, and throughput interplay.
        quality_score = 0
        if rpm_average is not None:
            quality_score += min(rpm_average / 10, 400) # Max 400 points for RPM (e.g. 1000 RPM = 100 pts)
        if max_bufferbloat is not None:
            quality_score -= min(max_bufferbloat / 2, 300) # Penalty for bufferbloat
        if raw.download_throughput_mbps is not None and raw.upload_throughput_mbps is not None:
             # Max 300 for throughput (e.g. 100Mbps combined = 300 pts)
            quality_score += min((raw.download_throughput_mbps + raw.upload_throughput_mbps), 300)

        quality_score = max(0, min(1000, quality_score)) # Normalize to 0-1000

        quality_rating = "unknown"
        if quality_score >= self.thresholds['quality_score']['excellent']:
            quality_rating = "excellent"
        elif quality_score >= self.thresholds['quality_score']['good']:
            quality_rating = "good"
        elif quality_score >= self.thresholds['quality_score']['fair']:
            quality_rating = "fair"
        else:
            quality_rating = "poor"

        congestion_detected = bufferbloat_severity in ["moderate", "severe"] or \
                              (rpm_average is not None and rpm_average < self.thresholds['rpm']['fair'])


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
        """Creates a ResponsivenessMetrics object representing a failed test."""
        return ResponsivenessMetrics(
            timestamp=time.time(),
            target_host=target_url,
            error=error_msg,
            quality_rating="error",
            bufferbloat_severity="unknown",
            measurement_duration_ms=duration_ms
        )

    def _generate_recommendations(self, metrics: ResponsivenessMetrics) -> List[str]:
        """Generate actionable recommendations based on metrics."""
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
            if metrics.rpm_average < self.thresholds['rpm']['poor']:
                recs.append(f"Very low responsiveness (RPM: {metrics.rpm_average:.0f}). "
                            "Real-time applications will suffer. Investigate network congestion or ISP issues.")
            elif metrics.rpm_average < self.thresholds['rpm']['fair']:
                recs.append(f"Low responsiveness (RPM: {metrics.rpm_average:.0f}). "
                            "May impact gaming or video conferencing.")

        if (metrics.download_throughput_mbps is not None and metrics.download_throughput_mbps < 5) or \
           (metrics.upload_throughput_mbps is not None and metrics.upload_throughput_mbps < 1):
            recs.append("Low throughput detected. Check your internet plan or look for bandwidth-heavy devices.")

        if not recs and metrics.quality_rating in ["excellent", "good"]:
            recs.append("Network quality appears good.")
        elif not recs:
            recs.append("Review individual metrics for potential issues.")

        return recs

    async def _store_metrics(self, metrics: ResponsivenessMetrics):
        """Stores responsiveness metrics in the database."""
        if not self.database:
            return

        # Adapt this to your actual database schema for network_quality_metrics
        # This is a placeholder for the fields defined in the previous SQL schema suggestion
        query = """
            INSERT INTO network_quality_metrics (
                timestamp, target_host, rpm_download, rpm_upload, rpm_average,
                base_rtt_ms, loaded_rtt_download_ms, loaded_rtt_upload_ms,
                download_bufferbloat_ms, upload_bufferbloat_ms, bufferbloat_severity,
                download_mbps, upload_mbps, overall_quality_score, quality_rating,
                download_responsiveness, upload_responsiveness, -- Assuming these are scores
                congestion_detected, measurement_duration, recommendations, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        values = (
            metrics.timestamp, metrics.target_host, metrics.rpm_download, metrics.rpm_upload, metrics.rpm_average,
            metrics.base_rtt_ms, metrics.loaded_rtt_download_ms, metrics.loaded_rtt_upload_ms,
            metrics.download_bufferbloat_ms, metrics.upload_bufferbloat_ms, metrics.bufferbloat_severity,
            metrics.download_throughput_mbps, metrics.upload_throughput_mbps, metrics.overall_quality_score, metrics.quality_rating,
            metrics.download_responsiveness_score, metrics.upload_responsiveness_score, # Use the scores
            metrics.congestion_detected, metrics.measurement_duration_ms, json.dumps(metrics.recommendations), metrics.error
        )
        try:
            await self.database.db.execute(query, values)
            await self.database.db.commit()
            self.logger.debug(f"Stored NetworkQuality metrics for {metrics.target_host} to database.")
        except Exception as e:
            self.logger.error(f"Failed to store NetworkQuality metrics for {metrics.target_host}: {e}")

async def main_collector_test():
    # Example usage for NetworkQualityCollector
    logging.basicConfig(level=logging.DEBUG)
    mock_db_path = "test_nq_collector.db" # Use a temporary DB for testing
    db = Database(mock_db_path)
    await db.initialize() # Ensure tables are created if your DB class does this

    # Create a dummy network_quality_metrics table for testing if it doesn't exist
    try:
        await db.db.execute("""
            CREATE TABLE IF NOT EXISTS network_quality_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp REAL, target_host TEXT,
                rpm_download REAL, rpm_upload REAL, rpm_average REAL, base_rtt_ms REAL,
                loaded_rtt_download_ms REAL, loaded_rtt_upload_ms REAL,
                download_bufferbloat_ms REAL, upload_bufferbloat_ms REAL, bufferbloat_severity TEXT,
                download_mbps REAL, upload_mbps REAL, overall_quality_score REAL, quality_rating TEXT,
                download_responsiveness REAL, upload_responsiveness REAL,
                congestion_detected BOOLEAN, measurement_duration REAL, recommendations TEXT, error TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        await db.db.commit()
    except Exception as e:
        logger.error(f"Could not create test table: {e}")


    config = {
        "networkquality": {
             "client": {
                "binary_path": "/usr/local/bin/networkquality", # ADJUST THIS PATH
                "test_duration": 7,
                "parallel_streams": 4
            },
            "server": {
                "url": "http://localhost:9090" # Replace with your actual server
            },
            "thresholds": { # Example thresholds
                "bufferbloat_ms": {'mild': 25, 'moderate': 50, 'severe': 75},
                "rpm": {'poor': 150, 'fair': 350, 'good': 650, 'excellent': 850},
                "quality_score": {'poor': 250, 'fair': 550, 'good': 750, 'excellent': 950}
            }
        }
    }
    collector = NetworkQualityCollector(config, db)
    target_server = config["networkquality"]["server"]["url"]

    logger.info(f"Testing NetworkQualityCollector against {target_server}...")
    metrics = await collector.collect_network_quality()
    logger.info(f"Collected Metrics: {metrics.to_dict() if metrics else 'None'}")

    if metrics and metrics.error:
        logger.error(f"Collector returned an error: {metrics.error}")
    elif metrics:
        logger.info(f"Quality Rating: {metrics.quality_rating}")
        logger.info(f"Bufferbloat: {metrics.bufferbloat_severity} ({metrics.max_bufferbloat_ms:.2f} ms)")
        logger.info(f"RPM Avg: {metrics.rpm_average:.2f} RPM")
        logger.info(f"Recommendations: {metrics.recommendations}")

    await db.close()
    Path(mock_db_path).unlink(missing_ok=True) # Clean up test DB

if __name__ == "__main__":
    # This part is for direct testing of the collector.
    # Ensure networkquality binary is installed and a server is running.
    # asyncio.run(main_collector_test())
    print("NetworkQualityCollector defined. To test, uncomment asyncio.run(main_collector_test()) "
          "and ensure the networkquality binary and a server are available, "
          "and paths/URLs in main_collector_test are correct.")

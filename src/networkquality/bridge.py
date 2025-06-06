#!/usr/bin/env python3
# src/networkquality/bridge.py
"""
Python bridge to the networkquality binary (Cloudflare's responsiveness tool).
Parses JSON output from the rpm subcommand.
"""

import asyncio
import json
import logging
import re
import subprocess
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class NetworkQualityMeasurement:
    """
    Represents the structured result from a networkquality rpm measurement.
    This tool measures against predefined endpoints (like Cloudflare).
    """
    timestamp: float
    target_server: str
    rpm_download: Optional[float] = None
    rpm_upload: Optional[float] = None
    base_rtt_ms: Optional[float] = None
    loaded_rtt_download_ms: Optional[float] = None
    loaded_rtt_upload_ms: Optional[float] = None
    download_throughput_mbps: Optional[float] = None
    upload_throughput_mbps: Optional[float] = None
    download_responsiveness_score: Optional[float] = None
    upload_responsiveness_score: Optional[float] = None
    error: Optional[str] = None
    rpm_average: Optional[float] = None
    download_bufferbloat_ms: Optional[float] = None
    upload_bufferbloat_ms: Optional[float] = None
    bufferbloat_severity: Optional[str] = None
    overall_quality_score: Optional[float] = None
    quality_rating: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class NetworkQualityBinaryBridge:
    """
    Bridge to interact with the networkquality binary (Cloudflare responsiveness tool).
    """

    def __init__(self, client_config_dict: Dict[str, Any]):
        self.binary_path = Path(client_config_dict.get('binary_path', '/usr/local/bin/networkquality'))
        self.default_duration_ms = client_config_dict.get('test_duration', 12000)
        self.default_max_connections = client_config_dict.get('max_loaded_connections', 8)
        self.logger = logger

        if not self.binary_path.exists():
            common_paths = [
                Path("/usr/local/bin/networkquality"),
                Path("/usr/bin/networkquality"),
                Path("./networkquality")
            ]
            for p in common_paths:
                if p.exists():
                    self.binary_path = p
                    self.logger.info(f"Resolved networkquality binary to: {self.binary_path}")
                    break
            else:
                self.logger.warning(f"NetworkQuality binary not found at configured path or common locations.")

    async def measure(self, duration_ms: Optional[int] = None, max_connections: Optional[int] = None) -> NetworkQualityMeasurement:
        """
        Runs the 'networkquality rpm' command and parses its JSON output.
        """
        target_server = "cloudflare"
        if not self.binary_path.exists():
            error_msg = f"NetworkQuality binary not found at {self.binary_path}"
            self.logger.error(error_msg)
            return NetworkQualityMeasurement(timestamp=time.time(), target_server=target_server, error=error_msg)

        cmd = [
            str(self.binary_path), "rpm",
            "--test-duration", str(duration_ms or self.default_duration_ms),
            "--max-load", str(max_connections or self.default_max_connections),
        ]

        self.logger.debug(f"Executing NetworkQuality command: {' '.join(cmd)}")
        timestamp = time.time()

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                error_message = stderr.decode().strip() or f"Process exited with code {proc.returncode}"
                self.logger.error(f"NetworkQuality measurement failed: {error_message}")
                return NetworkQualityMeasurement(timestamp=timestamp, target_server=target_server, error=error_message)

            raw_result_str = stdout.decode()
            if not raw_result_str.strip():
                error_message = stderr.decode().strip() if stderr else "Empty output from binary"
                self.logger.error(f"NetworkQuality measurement produced no output. Stderr: {error_message}")
                return NetworkQualityMeasurement(
                    timestamp=timestamp, 
                    target_server="cloudflare", 
                    error=f"Empty output. Stderr: {error_message}"
                )

# Try to parse as JSON first
            try:
                raw_result_dict = json.loads(raw_result_str)  # Changed variable name to raw_result_dict
                self.logger.debug(f"Raw NetworkQuality JSON result: {raw_result_dict}")
                return self._parse_json_output(raw_result_dict, timestamp)  # Use the new variable name
            except json.JSONDecodeError:
                # If not JSON, parse text output
                self.logger.debug(f"Raw NetworkQuality text result: {raw_result_str}")
                return self._parse_text_output(raw_result_str, timestamp)

        except FileNotFoundError:
            return NetworkQualityMeasurement(timestamp=time.time(), target_server=target_server, error=f"Binary not found at {self.binary_path}")
        except Exception as e:
            self.logger.exception("An unexpected error occurred during NetworkQuality measurement")
            return NetworkQualityMeasurement(timestamp=time.time(), target_server=target_server, error=str(e))

    def _parse_json_output(self, raw_result: Dict[str, Any], timestamp: float) -> NetworkQualityMeasurement:
            """Parse JSON output from the tool"""
            
            self.logger.debug(f"Parsing JSON output: {raw_result}")
            
            # Parse the actual networkquality JSON structure
            unloaded_latency_ms = raw_result.get("unloaded_latency_ms")
            jitter_ms = raw_result.get("jitter_ms")
            
            # Parse download metrics
            download_data = raw_result.get("download", {})
            download_throughput_bps = download_data.get("throughput")
            download_loaded_latency_ms = download_data.get("loaded_latency_ms")
            download_rpm = download_data.get("rpm")
            
            # Parse upload metrics
            upload_data = raw_result.get("upload", {})
            upload_throughput_bps = upload_data.get("throughput")
            upload_loaded_latency_ms = upload_data.get("loaded_latency_ms")
            upload_rpm = upload_data.get("rpm")
            
            # Convert throughput from bytes/sec to Mbps
            dl_mbps = None
            if download_throughput_bps is not None:
                dl_mbps = download_throughput_bps * 8 / 1_000_000  # bytes/sec to Mbps
            
            ul_mbps = None
            if upload_throughput_bps is not None:
                ul_mbps = upload_throughput_bps * 8 / 1_000_000  # bytes/sec to Mbps
            
            # Format values for logging
            dl_mbps_str = f"{dl_mbps:.2f}" if dl_mbps is not None else "0.00"
            ul_mbps_str = f"{ul_mbps:.2f}" if ul_mbps is not None else "0.00"
            dl_rpm_str = str(download_rpm) if download_rpm is not None else "N/A"
            ul_rpm_str = str(upload_rpm) if upload_rpm is not None else "N/A"
            
            self.logger.info(f"Parsed metrics - Download: {dl_rpm_str} RPM, {dl_mbps_str} Mbps | Upload: {ul_rpm_str} RPM, {ul_mbps_str} Mbps")

            return NetworkQualityMeasurement(
                timestamp=timestamp,
                target_server="cloudflare",
                rpm_download=download_rpm,
                rpm_upload=upload_rpm,
                base_rtt_ms=unloaded_latency_ms,
                loaded_rtt_download_ms=download_loaded_latency_ms,
                loaded_rtt_upload_ms=upload_loaded_latency_ms,
                download_throughput_mbps=dl_mbps,
                upload_throughput_mbps=ul_mbps,
                download_responsiveness_score=None,  # Not provided in this output
                upload_responsiveness_score=None,    # Not provided in this output
                error=raw_result.get("error")
            )

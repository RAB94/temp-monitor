#!/usr/bin/env python3
# src/networkquality/bridge.py
"""
Python bridge to the networkquality binary (Cloudflare's responsiveness tool).
Parses JSON output from the rpm subcommand.
"""

import asyncio
import json
import logging
import subprocess
import time
from typing import Dict, Any, Optional, List, Tuple
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
    target_server: str  # Will be set to the endpoint used (e.g., "cloudflare")
    
    # RPM measurements
    rpm_download: Optional[float] = None
    rpm_upload: Optional[float] = None
    
    # RTT measurements
    base_rtt_ms: Optional[float] = None
    loaded_rtt_download_ms: Optional[float] = None
    loaded_rtt_upload_ms: Optional[float] = None
    
    # Throughput measurements
    download_throughput_mbps: Optional[float] = None
    upload_throughput_mbps: Optional[float] = None
    
    # Responsiveness scores (if available)
    download_responsiveness_score: Optional[float] = None
    upload_responsiveness_score: Optional[float] = None
    
    error: Optional[str] = None

    # Derived metrics (calculated in collector)
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
    This tool measures against predefined endpoints, not custom servers.
    """

    def __init__(self, client_config_dict: Dict[str, Any]):
        """
        Initializes the bridge.
        Args:
            client_config_dict: A dictionary containing client-specific configurations.
        """
        self.binary_path = Path(client_config_dict.get('binary_path', '/usr/local/bin/networkquality'))
        self.default_duration_ms = client_config_dict.get('test_duration', 12000)  # milliseconds
        self.default_max_connections = client_config_dict.get('max_loaded_connections', 8)
        self.logger = logger

        if not self.binary_path.exists():
            # Attempt to resolve common paths
            if not self.binary_path.is_absolute():
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
                    self.logger.warning(
                        f"NetworkQuality binary not found at '{client_config_dict.get('binary_path')}' or common locations. "
                        "Measurements will fail. Please install it or update the 'binary_path' in config."
                    )
            else:
                self.logger.warning(
                    f"NetworkQuality binary not found at absolute path '{self.binary_path}'. Measurements will fail."
                )

    async def measure(self, server_url: str = None,
                      duration_ms: Optional[int] = None,
                      max_connections: Optional[int] = None) -> NetworkQualityMeasurement:
        """
        Runs the 'networkquality rpm' command to perform a measurement.
        Note: server_url is ignored as this tool uses predefined endpoints.

        Args:
            server_url: Ignored - tool uses predefined endpoints
            duration_ms: Duration of the test in milliseconds
            max_connections: Maximum number of loaded connections

        Returns:
            A NetworkQualityMeasurement object.
        """
        if not self.binary_path.exists():
            error_msg = f"NetworkQuality binary not found at {self.binary_path}"
            self.logger.error(error_msg)
            return NetworkQualityMeasurement(
                timestamp=time.time(), 
                target_server="cloudflare", 
                error=error_msg
            )

        test_duration_ms = duration_ms if duration_ms is not None else self.default_duration_ms
        max_load = max_connections if max_connections is not None else self.default_max_connections

        # Build command for networkquality rpm
        cmd = [
            str(self.binary_path),
            "rpm",
            "--test-duration", str(test_duration_ms),
            "--max-load", str(max_load),
            # Add JSON output if supported (check with --help first)
            # "--json"  # Uncomment if the tool supports JSON output
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
                error_message = stderr.decode().strip() if stderr else "Unknown error from binary"
                self.logger.error(f"NetworkQuality measurement failed (RC: {proc.returncode}): {error_message}")
                return NetworkQualityMeasurement(
                    timestamp=timestamp, 
                    target_server="cloudflare", 
                    error=error_message
                )

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
                raw_result = json.loads(raw_result_str)
                self.logger.debug(f"Raw NetworkQuality JSON result: {raw_result}")
                return self._parse_json_output(raw_result, timestamp)
            except json.JSONDecodeError:
                # If not JSON, parse text output
                self.logger.debug(f"Raw NetworkQuality text result: {raw_result_str}")
                return self._parse_text_output(raw_result_str, timestamp)

        except FileNotFoundError:
            error_msg = f"NetworkQuality binary not found at {self.binary_path}"
            self.logger.error(error_msg)
            return NetworkQualityMeasurement(
                timestamp=time.time(), 
                target_server="cloudflare", 
                error=error_msg
            )
        except Exception as e:
            error_msg = f"An unexpected error occurred during NetworkQuality measurement: {e}"
            self.logger.exception(error_msg)
            return NetworkQualityMeasurement(
                timestamp=time.time(), 
                target_server="cloudflare", 
                error=error_msg
            )

    def _parse_json_output(self, raw_result: Dict[str, Any], timestamp: float) -> NetworkQualityMeasurement:
        """Parse JSON output from the tool"""
        
        # Convert throughput from bytes/sec to Mbps if needed
        dl_mbps = None
        ul_mbps = None
        
        if "download_throughput_bps" in raw_result:
            dl_mbps = raw_result["download_throughput_bps"] / 1_000_000
        elif "download_throughput_mbps" in raw_result:
            dl_mbps = raw_result["download_throughput_mbps"]
        
        if "upload_throughput_bps" in raw_result:
            ul_mbps = raw_result["upload_throughput_bps"] / 1_000_000
        elif "upload_throughput_mbps" in raw_result:
            ul_mbps = raw_result["upload_throughput_mbps"]

        return NetworkQualityMeasurement(
            timestamp=timestamp,
            target_server="cloudflare",
            rpm_download=raw_result.get("download_rpm"),
            rpm_upload=raw_result.get("upload_rpm"),
            base_rtt_ms=raw_result.get("base_rtt_ms"),
            loaded_rtt_download_ms=raw_result.get("download_loaded_rtt_ms"),
            loaded_rtt_upload_ms=raw_result.get("upload_loaded_rtt_ms"),
            download_throughput_mbps=dl_mbps,
            upload_throughput_mbps=ul_mbps,
            download_responsiveness_score=raw_result.get("download_responsiveness_score"),
            upload_responsiveness_score=raw_result.get("upload_responsiveness_score"),
            error=raw_result.get("error")
        )

    def _parse_text_output(self, output: str, timestamp: float) -> NetworkQualityMeasurement:
        """Parse text output from the tool"""
        
        # This is a fallback parser for text output
        # You'll need to adjust this based on the actual text format
        lines = output.strip().split('\n')
        
        measurement = NetworkQualityMeasurement(
            timestamp=timestamp,
            target_server="cloudflare"
        )
        
        # Look for specific patterns in the output
        for line in lines:
            line = line.strip().lower()
            
            # Look for RPM values
            if "download rpm" in line or "dl rpm" in line:
                try:
                    rpm_value = float([word for word in line.split() if word.replace('.', '').isdigit()][0])
                    measurement.rpm_download = rpm_value
                except (IndexError, ValueError):
                    pass
            
            elif "upload rpm" in line or "ul rpm" in line:
                try:
                    rpm_value = float([word for word in line.split() if word.replace('.', '').isdigit()][0])
                    measurement.rpm_upload = rpm_value
                except (IndexError, ValueError):
                    pass
            
            # Look for throughput values
            elif "download" in line and ("mbps" in line or "mb/s" in line):
                try:
                    mbps_value = float([word for word in line.split() if word.replace('.', '').isdigit()][0])
                    measurement.download_throughput_mbps = mbps_value
                except (IndexError, ValueError):
                    pass
            
            elif "upload" in line and ("mbps" in line or "mb/s" in line):
                try:
                    mbps_value = float([word for word in line.split() if word.replace('.', '').isdigit()][0])
                    measurement.upload_throughput_mbps = mbps_value
                except (IndexError, ValueError):
                    pass
        
        return measurement

async def main():
    logging.basicConfig(level=logging.DEBUG)
    
    client_config_dict = {
        "binary_path": "/usr/local/bin/networkquality",
        "test_duration": 12000,  # 12 seconds in milliseconds
        "max_loaded_connections": 8
    }
    bridge = NetworkQualityBinaryBridge(client_config_dict)

    logger.info("Attempting to measure responsiveness using networkquality rpm...")
    try:
        result = await bridge.measure()
        logger.info(f"Measurement Result: {result.to_dict()}")
        if result.error:
            logger.error(f"Measurement error: {result.error}")
    except Exception as e:
        logger.error(f"Test execution failed: {e}")

if __name__ == "__main__":
    print("NetworkQualityBinaryBridge defined. To test, uncomment asyncio.run(main()) and ensure "
          "the networkquality binary is available at the configured path.")
    # asyncio.run(main())

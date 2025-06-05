#!/usr/bin/env python3
# src/networkquality/bridge.py
"""
Python bridge to the networkquality-rs binary.
Parses JSON output from the command-line tool.
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
    Represents the structured result from a networkquality-rs measurement.
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
    download_responsiveness_score: Optional[float] = None # Raw responsiveness score from tool
    upload_responsiveness_score: Optional[float] = None   # Raw responsiveness score from tool
    error: Optional[str] = None

    # Derived metrics (can be calculated in the collector)
    rpm_average: Optional[float] = None
    download_bufferbloat_ms: Optional[float] = None
    upload_bufferbloat_ms: Optional[float] = None
    bufferbloat_severity: Optional[str] = None # e.g., "none", "mild", "moderate", "severe"
    overall_quality_score: Optional[float] = None # e.g., 0-1000
    quality_rating: Optional[str] = None # e.g., "excellent", "good", "fair", "poor"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class NetworkQualityBinaryBridge:
    """
    Bridge to interact with the networkquality-rs command-line binary.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config.get('client', {})
        self.binary_path = Path(self.config.get('binary_path', '/usr/local/bin/networkquality'))
        self.default_duration = self.config.get('test_duration', 10) # Shorter default for CLI
        self.default_parallel_streams = self.config.get('parallel_streams', 8) # Fewer default for CLI
        self.logger = logger

        if not self.binary_path.exists():
            self.logger.warning(
                f"NetworkQuality binary not found at {self.binary_path}. "
                "Measurements will fail. Please install it or update the 'binary_path' in config."
            )

    async def measure(self, server_url: str,
                      duration: Optional[int] = None,
                      parallel_streams: Optional[int] = None) -> NetworkQualityMeasurement:
        """
        Runs the networkquality-rs binary to perform a measurement.

        Args:
            server_url: The URL of the networkquality-rs measurement server.
            duration: Duration of the test in seconds.
            parallel_streams: Number of parallel streams to use.

        Returns:
            A NetworkQualityMeasurement object.
        """
        if not self.binary_path.exists():
            error_msg = f"NetworkQuality binary not found at {self.binary_path}"
            self.logger.error(error_msg)
            return NetworkQualityMeasurement(timestamp=time.time(), target_server=server_url, error=error_msg)

        test_duration = duration if duration is not None else self.default_duration
        num_streams = parallel_streams if parallel_streams is not None else self.default_parallel_streams

        cmd = [
            str(self.binary_path),
            "--server", server_url,
            "--duration", str(test_duration),
            "--parallel-streams", str(num_streams),
            "--json"  # Crucial for parsing output
        ]

        self.logger.debug(f"Executing NetworkQuality command: {' '.join(cmd)}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            timestamp = time.time()

            if proc.returncode != 0:
                error_message = stderr.decode().strip()
                self.logger.error(f"NetworkQuality measurement failed for {server_url}: {error_message}")
                return NetworkQualityMeasurement(timestamp=timestamp, target_server=server_url, error=error_message)

            # Parse JSON output
            raw_result = json.loads(stdout.decode())
            self.logger.debug(f"Raw NetworkQuality result for {server_url}: {raw_result}")

            # Map to NetworkQualityMeasurement fields
            # Note: Field names from networkquality-rs JSON output might differ.
            # Adjust these based on the actual JSON structure from the binary.
            # Example mapping (likely needs adjustment):
            # {
            #   "dl_rpm": 580.0,
            #   "ul_rpm": 620.0,
            #   "base_rtt_ms": 15.0,
            #   "dl_loaded_rtt_ms": 45.0,
            #   "ul_loaded_rtt_ms": 55.0,
            #   "dl_mbps": 95.5,
            #   "ul_mbps": 88.0,
            #   "dl_responsiveness": 0.85, (this is a score, not RPM directly)
            #   "ul_responsiveness": 0.90  (this is a score, not RPM directly)
            # }
            # The tool might output separate responsiveness scores and RPM.
            # The CLI version of networkquality-rs might have slightly different output keys than the library.
            # It's crucial to inspect the actual JSON output of `networkquality --json`.

            # Assuming the JSON output keys are similar to the library's Measurement struct for simplicity:
            return NetworkQualityMeasurement(
                timestamp=timestamp,
                target_server=server_url,
                rpm_download=raw_result.get("dl_rpm"), # Adjust key if needed
                rpm_upload=raw_result.get("ul_rpm"),   # Adjust key if needed
                base_rtt_ms=raw_result.get("base_rtt_ms"), # Adjust key if needed
                loaded_rtt_download_ms=raw_result.get("dl_loaded_rtt_ms"), # Adjust key if needed
                loaded_rtt_upload_ms=raw_result.get("ul_loaded_rtt_ms"),   # Adjust key if needed
                download_throughput_mbps=raw_result.get("dl_mbps"), # Adjust key if needed
                upload_throughput_mbps=raw_result.get("ul_mbps"),   # Adjust key if needed
                # The binary might output `dl_responsiveness_score` and `ul_responsiveness_score`
                # Or it might directly give RPMs. This needs to be checked from binary's JSON output.
                download_responsiveness_score=raw_result.get("dl_responsiveness"), # Adjust key if needed
                upload_responsiveness_score=raw_result.get("ul_responsiveness")    # Adjust key if needed
            )

        except FileNotFoundError:
            error_msg = f"NetworkQuality binary not found at {self.binary_path}"
            self.logger.error(error_msg)
            return NetworkQualityMeasurement(timestamp=time.time(), target_server=server_url, error=error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse JSON output from NetworkQuality binary: {e}. Output: {stdout.decode()}"
            self.logger.error(error_msg)
            return NetworkQualityMeasurement(timestamp=time.time(), target_server=server_url, error=error_msg)
        except Exception as e:
            error_msg = f"An unexpected error occurred during NetworkQuality measurement: {e}"
            self.logger.exception(error_msg) # Log with stack trace
            return NetworkQualityMeasurement(timestamp=time.time(), target_server=server_url, error=error_msg)

async def main():
    # Example usage (for testing the bridge directly)
    logging.basicConfig(level=logging.DEBUG)
    config = {
        "client": {
            "binary_path": "/usr/local/bin/networkquality", # Ensure this path is correct
            "test_duration": 5, # Short duration for testing
        }
    }
    bridge = NetworkQualityBinaryBridge(config)

    # Replace with your actual self-hosted server URL or a public one if the binary supports it.
    # The `networkquality-rs` client binary typically expects a server running the `networkquality-server` component.
    # For testing without a self-hosted server, you might need to check if cloudflare provides test servers
    # or if the binary has a default test mode.
    # Assuming you have a local server running for testing:
    server_url = "http://localhost:9090" # Replace with your server
    # server_url = "http://your-networkquality-server.example.com"


    logger.info(f"Attempting to measure against {server_url}...")
    try:
        result = await bridge.measure(server_url)
        logger.info(f"Measurement Result: {result.to_dict()}")
        if result.error:
            logger.error(f"Measurement error: {result.error}")
    except Exception as e:
        logger.error(f"Direct test execution failed: {e}")

if __name__ == "__main__":
    # This part is for direct testing of the bridge.
    # You'll need to have the `networkquality` binary installed and potentially a server running.
    # asyncio.run(main())
    print("NetworkQualityBinaryBridge defined. To test, uncomment asyncio.run(main()) and ensure "
          "the networkquality binary and a server are available.")

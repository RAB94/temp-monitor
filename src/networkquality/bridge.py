#!/usr/bin/env python3
# src/networkquality/bridge.py
"""
Python bridge to the networkquality-rs binary.
Parses JSON output from the command-line tool.
Uses the 'rpm' subcommand as per cloudflare/networkquality-rs.
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
    Fields should align with the JSON output of the 'networkquality rpm --json' command.
    """
    timestamp: float
    target_server: str # The server URL that was tested against
    # Based on typical output from such tools, these are expected.
    # Verify against actual JSON output of `networkquality rpm <server_url> --json`
    rpm_download: Optional[float] = None # Often `dl_rpm` or `download_rpm` in JSON
    rpm_upload: Optional[float] = None   # Often `ul_rpm` or `upload_rpm` in JSON
    base_rtt_ms: Optional[float] = None  # Often `base_rtt_ms` or `rtt_ms`
    loaded_rtt_download_ms: Optional[float] = None # Often `dl_loaded_rtt_ms`
    loaded_rtt_upload_ms: Optional[float] = None   # Often `ul_loaded_rtt_ms`
    download_throughput_mbps: Optional[float] = None # Often `dl_mbps` or `download_mbps`
    upload_throughput_mbps: Optional[float] = None   # Often `ul_mbps` or `upload_mbps`
    download_responsiveness_score: Optional[float] = None # Tool might provide a specific score
    upload_responsiveness_score: Optional[float] = None   # Tool might provide a specific score
    error: Optional[str] = None

    # Derived metrics (can be calculated in the collector)
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
    Bridge to interact with the networkquality-rs command-line binary
    using the 'rpm' subcommand.
    """

    def __init__(self, client_config_dict: Dict[str, Any]): # Expects the 'client' part of networkquality config
        """
        Initializes the bridge.
        Args:
            client_config_dict: A dictionary containing client-specific configurations like
                                'binary_path', 'test_duration', 'parallel_streams'.
        """
        self.binary_path = Path(client_config_dict.get('binary_path', '/usr/local/bin/networkquality'))
        self.default_duration = client_config_dict.get('test_duration', 10)
        self.default_parallel_streams = client_config_dict.get('parallel_streams', 8)
        self.logger = logger

        if not self.binary_path.exists():
            # Attempt to resolve common paths if the configured path doesn't exist and is not absolute
            if not self.binary_path.is_absolute():
                common_paths = [
                    Path("/usr/local/bin/networkquality"),
                    Path("/usr/bin/networkquality"),
                    Path("./networkquality") # Check local directory if running from project root during dev
                ]
                for p in common_paths:
                    if p.exists():
                        self.binary_path = p
                        self.logger.info(f"Resolved networkquality client binary to: {self.binary_path}")
                        break
                else: # If still not found
                    self.logger.warning(
                        f"NetworkQuality client binary not found at '{client_config_dict.get('binary_path')}' or common locations. "
                        "Measurements will fail. Please install it or update the 'binary_path' in config."
                    )
            else: # If absolute path was given and it doesn't exist
                 self.logger.warning(
                    f"NetworkQuality client binary not found at absolute path '{self.binary_path}'. Measurements will fail."
                )


    async def measure(self, server_url: str,
                      duration: Optional[int] = None,
                      parallel_streams: Optional[int] = None) -> NetworkQualityMeasurement:
        """
        Runs the 'networkquality rpm' command to perform a measurement.

        Args:
            server_url: The URL of the networkquality-rs measurement server (positional argument).
            duration: Duration of the test in seconds.
            parallel_streams: Number of parallel streams to use.

        Returns:
            A NetworkQualityMeasurement object.
        """
        if not self.binary_path.exists():
            error_msg = f"NetworkQuality client binary not found at {self.binary_path}"
            self.logger.error(error_msg)
            return NetworkQualityMeasurement(timestamp=time.time(), target_server=server_url, error=error_msg)

        test_duration = duration if duration is not None else self.default_duration
        num_streams = parallel_streams if parallel_streams is not None else self.default_parallel_streams

        # Corrected command structure for 'networkquality rpm <server_url> [OPTIONS]'
        cmd = [
            str(self.binary_path),
            "rpm",                 # The subcommand
            server_url,            # Server URL as a positional argument
            "--duration", str(test_duration),
            "--parallel-streams", str(num_streams),
            "--json"               # Global option for JSON output
        ]
        # Optional: Add verbosity flags like -v or -q if needed, from config
        # Example: if client_config_dict.get('verbose'): cmd.append('-v')

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
                self.logger.error(f"NetworkQuality measurement failed for {server_url} (RC: {proc.returncode}): {error_message}")
                return NetworkQualityMeasurement(timestamp=timestamp, target_server=server_url, error=error_message)

            raw_result_str = stdout.decode()
            if not raw_result_str.strip():
                error_message = stderr.decode().strip() if stderr else "Empty output from binary"
                self.logger.error(f"NetworkQuality measurement for {server_url} produced no output. Stderr: {error_message}")
                return NetworkQualityMeasurement(timestamp=timestamp, target_server=server_url, error=f"Empty output. Stderr: {error_message}")

            raw_result = json.loads(raw_result_str)
            self.logger.debug(f"Raw NetworkQuality 'rpm' result for {server_url}: {raw_result}")

            # CRITICAL: Field names here MUST match the JSON output of `networkquality rpm ... --json`
            # Common keys from networkquality-rs output for 'rpm' might be:
            #   "up_bytes_per_sec", "down_bytes_per_sec" (convert to mbps)
            #   "up_rpm", "down_rpm"
            #   "rtt_ms" (base RTT)
            #   "up_loaded_rtt_ms", "down_loaded_rtt_ms"
            #   "interface_name" (useful if the tool reports it)
            #   "error" (if the tool itself reports a specific error in JSON)
            #   Refer to the `Measurement` struct in networkquality-rs `src/measurement.rs` if possible
            #   or directly inspect the JSON output.

            # Example mapping:
            dl_mbps = (raw_result.get("down_bytes_per_sec", 0) * 8) / 1_000_000 if raw_result.get("down_bytes_per_sec") is not None else None
            ul_mbps = (raw_result.get("up_bytes_per_sec", 0) * 8) / 1_000_000 if raw_result.get("up_bytes_per_sec") is not None else None

            return NetworkQualityMeasurement(
                timestamp=timestamp,
                target_server=server_url, # server_url is the target tested
                rpm_download=raw_result.get("down_rpm"),
                rpm_upload=raw_result.get("up_rpm"),
                base_rtt_ms=raw_result.get("rtt_ms"), # Check if this is the base RTT
                loaded_rtt_download_ms=raw_result.get("down_loaded_rtt_ms"),
                loaded_rtt_upload_ms=raw_result.get("up_loaded_rtt_ms"),
                download_throughput_mbps=dl_mbps,
                upload_throughput_mbps=ul_mbps,
                # The 'rpm' command should directly give RPMs. Scores might be part of a different subcommand or not present.
                # If the JSON also contains specific responsiveness scores, map them here.
                # download_responsiveness_score=raw_result.get("some_dl_score_key"),
                # upload_responsiveness_score=raw_result.get("some_ul_score_key"),
                error=raw_result.get("error") # If the JSON itself can contain an error field
            )

        except FileNotFoundError:
            error_msg = f"NetworkQuality client binary not found at {self.binary_path}"
            self.logger.error(error_msg)
            return NetworkQualityMeasurement(timestamp=time.time(), target_server=server_url, error=error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse JSON output from NetworkQuality binary: {e}. Output: {stdout.decode() if 'stdout' in locals() else 'N/A'}"
            self.logger.error(error_msg)
            return NetworkQualityMeasurement(timestamp=time.time(), target_server=server_url, error=error_msg)
        except Exception as e:
            error_msg = f"An unexpected error occurred during NetworkQuality measurement: {e}"
            self.logger.exception(error_msg)
            return NetworkQualityMeasurement(timestamp=time.time(), target_server=server_url, error=error_msg)

async def main():
    logging.basicConfig(level=logging.DEBUG)
    # This config should come from the main Config object's networkquality.client section
    client_config_dict = {
        "binary_path": "/usr/local/bin/networkquality", # ADJUST THIS PATH
        "test_duration": 5,
        "parallel_streams": 4
    }
    bridge = NetworkQualityBinaryBridge(client_config_dict)

    # Replace with your actual self-hosted server URL
    server_url = "http://localhost:9090" # Ensure your networkquality-server is running here

    logger.info(f"Attempting to measure against {server_url} using 'rpm' subcommand...")
    try:
        result = await bridge.measure(server_url)
        logger.info(f"Measurement Result: {result.to_dict()}")
        if result.error:
            logger.error(f"Measurement error: {result.error}")
    except Exception as e:
        logger.error(f"Direct test execution failed: {e}")

if __name__ == "__main__":
    # asyncio.run(main())
    print("NetworkQualityBinaryBridge defined. To test, uncomment asyncio.run(main()) and ensure "
          "the networkquality binary (client) and a networkquality-server are available, "
          "and paths/URLs in main() are correct.")


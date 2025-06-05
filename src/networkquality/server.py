#!/usr/bin/env python3
# src/networkquality/server.py
"""
Manages a self-hosted networkquality-rs server process.
"""

import asyncio
import logging
import subprocess # Using subprocess for consistency with the binary bridge approach
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class NetworkQualityServerManager:
    """
    Manages the lifecycle of a self-hosted networkquality-rs server binary.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the server manager.

        Args:
            config: A dictionary containing the 'networkquality.server' configuration.
                    Expected keys:
                    - 'type': "self_hosted" or "external". This manager only acts if "self_hosted".
                    - 'auto_start': boolean, if true, this manager will try to start/stop the server.
                    - 'binary_path': Path to the 'networkquality-server' executable.
                    - 'port': Port for the server to listen on.
                    - 'bind_address': Address for the server to bind to.
                    - 'log_level': Log level for the server (e.g., "info", "debug").
                    - 'additional_args': Optional list of additional command-line arguments for the server.
        """
        self.server_config = config.get('server', {})
        self.client_config = config.get('client', {}) # For getting server URL if needed
        self.logger = logger
        self.server_process: Optional[asyncio.subprocess.Process] = None
        self.running_tasks: List[asyncio.Task] = []

        self.server_type = self.server_config.get('type', 'external')
        self.auto_start = self.server_config.get('auto_start', False)
        self.server_binary = Path(self.server_config.get('binary_path', '/usr/local/bin/networkquality-server'))
        self.port = self.server_config.get('port', 9090)
        self.bind_address = self.server_config.get('bind_address', '0.0.0.0')
        self.server_log_level = self.server_config.get('log_level', 'info')
        self.additional_args = self.server_config.get('additional_args', [])

    async def start(self) -> bool:
        """
        Starts the self-hosted networkquality-server if configured to do so.

        Returns:
            True if the server was started or is already running, False otherwise.
        """
        if self.server_type != 'self_hosted' or not self.auto_start:
            self.logger.info(
                f"NetworkQualityServerManager: Server type is '{self.server_type}' or auto_start is '{self.auto_start}'. "
                "Not managing server process."
            )
            return True # Not an error, just not managing

        if self.is_running():
            self.logger.info(f"NetworkQuality server process is already running (PID: {self.server_process.pid}).")
            return True

        if not self.server_binary.exists():
            self.logger.error(
                f"NetworkQuality server binary not found at '{self.server_binary}'. "
                "Cannot start self-hosted server. Please install or update path in config."
            )
            return False

        cmd = [
            str(self.server_binary),
            "--bind", f'{self.bind_address}:{self.port}',
            "--log-level", self.server_log_level,
        ]
        if isinstance(self.additional_args, list):
            cmd.extend(self.additional_args)

        self.logger.info(f"Starting NetworkQuality server: {' '.join(cmd)}")

        try:
            self.server_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            self.logger.info(
                f"NetworkQuality server process started successfully (PID: {self.server_process.pid}) "
                f"on {self.bind_address}:{self.port}."
            )

            # Start monitoring tasks for stdout and stderr
            stdout_task = asyncio.create_task(self._log_stream(self.server_process.stdout, "stdout"))
            stderr_task = asyncio.create_task(self._log_stream(self.server_process.stderr, "stderr"))
            monitor_task = asyncio.create_task(self._monitor_process())
            self.running_tasks.extend([stdout_task, stderr_task, monitor_task])

            return True
        except Exception as e:
            self.logger.error(f"Failed to start NetworkQuality server process: {e}")
            self.server_process = None
            return False

    async def _log_stream(self, stream: Optional[asyncio.StreamReader], stream_name: str):
        """Logs output from the server process's stdout or stderr."""
        if not stream:
            return
        try:
            while not stream.at_eof():
                line = await stream.readline()
                if line:
                    self.logger.info(f"[networkquality-server-{stream_name}]: {line.decode().strip()}")
                else:
                    # Stream closed
                    break
        except asyncio.CancelledError:
            self.logger.debug(f"Stream logging ({stream_name}) cancelled.")
        except Exception as e:
            self.logger.error(f"Error reading server {stream_name}: {e}")

    async def _monitor_process(self):
        """Monitors the server process and logs if it exits."""
        if not self.server_process:
            return

        try:
            return_code = await self.server_process.wait()
            self.logger.warning(
                f"NetworkQuality server process (PID: {self.server_process.pid}) exited with code {return_code}."
            )
            # Optionally, add restart logic here if desired
            self.server_process = None # Mark as not running
        except asyncio.CancelledError:
            self.logger.debug("Server process monitoring cancelled.")
        except Exception as e:
            self.logger.error(f"Error monitoring server process: {e}")


    async def stop(self):
        """Stops the self-hosted networkquality-server if it's running."""
        if not self.server_process or not self.is_running():
            self.logger.info("NetworkQuality server process is not running or not managed.")
            return

        self.logger.info(f"Stopping NetworkQuality server process (PID: {self.server_process.pid})...")
        try:
            self.server_process.terminate()
            await asyncio.wait_for(self.server_process.wait(), timeout=10.0)
            self.logger.info("NetworkQuality server process terminated.")
        except asyncio.TimeoutError:
            self.logger.warning("NetworkQuality server process did not terminate gracefully, killing.")
            self.server_process.kill()
            await self.server_process.wait()
            self.logger.info("NetworkQuality server process killed.")
        except Exception as e:
            self.logger.error(f"Error stopping NetworkQuality server process: {e}")
        finally:
            for task in self.running_tasks:
                if not task.done():
                    task.cancel()
            if self.running_tasks:
                await asyncio.gather(*self.running_tasks, return_exceptions=True)
            self.running_tasks.clear()
            self.server_process = None


    def is_running(self) -> bool:
        """Checks if the server process is currently running."""
        return self.server_process is not None and self.server_process.returncode is None

    def get_server_url(self) -> Optional[str]:
        """
        Returns the URL of the self-hosted server if it's configured and supposed to be running.
        This is used by the collector to know where to send measurements.
        """
        if self.server_type == 'self_hosted':
            return f"http://{self.bind_address}:{self.port}"
        elif self.server_type == 'external':
            # For external, the URL is directly specified in the config.
            return self.server_config.get('url')
        return None


async def main_server_manager_test():
    # Example usage for NetworkQualityServerManager
    logging.basicConfig(level=logging.DEBUG)

    # Configuration for a self-hosted server that auto-starts
    config_self_hosted = {
        "networkquality": {
            "server": {
                "type": "self_hosted",
                "auto_start": True,
                "binary_path": "/usr/local/bin/networkquality-server", # ADJUST THIS PATH
                "port": 9091, # Using a different port for testing
                "bind_address": "127.0.0.1",
                "log_level": "debug"
            }
        }
    }

    manager = NetworkQualityServerManager(config_self_hosted.get("networkquality", {}))

    logger.info("Attempting to start self-hosted server...")
    started = await manager.start()

    if started and manager.is_running():
        logger.info(f"Server started. URL: {manager.get_server_url()}")
        logger.info("Server will run for 15 seconds for testing...")
        await asyncio.sleep(15)
        logger.info("Stopping server...")
        await manager.stop()
        logger.info("Server stopped.")
    elif started and not manager.is_running():
        logger.error("Manager reported start, but server is not running. Check logs.")
    else:
        logger.error("Server did not start. Check binary path and permissions.")

    # Configuration for an external server (manager should not start anything)
    config_external = {
         "networkquality": {
            "server": {
                "type": "external",
                "url": "http://some-external-rpm-server.com:9090"
            }
        }
    }
    external_manager = NetworkQualityServerManager(config_external.get("networkquality", {}))
    logger.info("Testing external server configuration (should not start a local server):")
    await external_manager.start() # Should do nothing but log
    logger.info(f"External server URL from config: {external_manager.get_server_url()}")
    await external_manager.stop() # Should do nothing


if __name__ == "__main__":
    # This part is for direct testing of the server manager.
    # Ensure networkquality-server binary is installed and path is correct in main_server_manager_test.
    # asyncio.run(main_server_manager_test())
    print("NetworkQualityServerManager defined. To test, uncomment asyncio.run(main_server_manager_test()) "
          "and ensure the networkquality-server binary is available, and paths in the test are correct.")


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

# Import the dataclass definitions from config.py to understand the structure
# This is for type hinting and clarity; direct import might cause circular dependency issues
# if server.py were imported by config.py. For now, this is illustrative.
# from src.config import NetworkQualityRSConfig # Illustrative

logger = logging.getLogger(__name__)

class NetworkQualityServerManager:
    """
    Manages the lifecycle of a self-hosted networkquality-rs server binary.
    """

    def __init__(self, nq_config: Any): # nq_config is expected to be NetworkQualityRSConfig instance
        """
        Initializes the server manager.

        Args:
            nq_config: An instance of NetworkQualityRSConfig (from src.config.py).
        """
        self.logger = logger
        self.server_process: Optional[asyncio.subprocess.Process] = None
        self.running_tasks: List[asyncio.Task] = []

        # Access attributes directly from the nq_config (NetworkQualityRSConfig) object
        # and its nested server and client config objects.
        # Fallback to defaults if attributes are missing (though dataclasses should have them)

        # self.server_config = nq_config.server if hasattr(nq_config, 'server') else {} # This would be NetworkQualityRSServerConfig
        # self.client_config = nq_config.client if hasattr(nq_config, 'client') else {} # This would be NetworkQualityRSClientConfig

        # More robust access using getattr with defaults for nested objects
        _server_details = getattr(nq_config, 'server', None)
        _client_details = getattr(nq_config, 'client', None)


        self.server_type = getattr(_server_details, 'type', 'external')
        self.auto_start = getattr(_server_details, 'auto_start', False)
        self.server_binary = Path(getattr(_server_details, 'binary_path', '/usr/local/bin/networkquality-server'))
        self.port = getattr(_server_details, 'port', 9090)
        self.bind_address = getattr(_server_details, 'bind_address', '0.0.0.0')
        self.server_log_level = getattr(_server_details, 'log_level', 'info')
        self.additional_args = getattr(_server_details, 'additional_args', [])

        # We might not need client_config here unless the server manager needs client details.
        # For now, keeping it minimal.

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
            # Attempt to resolve common paths if the configured path doesn't exist and is not absolute
            if not self.server_binary.is_absolute():
                common_paths = [
                    Path("/usr/local/bin/networkquality-server"),
                    Path("/usr/bin/networkquality-server"),
                    Path("./networkquality-server") # Check local directory
                ]
                for p in common_paths:
                    if p.exists():
                        self.server_binary = p
                        self.logger.info(f"Resolved networkquality-server binary to: {self.server_binary}")
                        break
                else: # If still not found
                    self.logger.error(
                        f"NetworkQuality server binary not found at '{self.server_config.binary_path}' or common locations. "
                        "Cannot start self-hosted server. Please install or update path in config."
                    )
                    return False
            else: # If absolute path was given and it doesn't exist
                 self.logger.error(
                    f"NetworkQuality server binary not found at absolute path '{self.server_binary}'. "
                    "Cannot start self-hosted server."
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
            while self.server_process and not stream.at_eof(): # Check if server_process still exists
                line = await stream.readline()
                if line:
                    self.logger.info(f"[networkquality-server-{stream_name}]: {line.decode().strip()}")
                else:
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
            pid = self.server_process.pid # Store pid before await
            return_code = await self.server_process.wait()
            self.logger.warning(
                f"NetworkQuality server process (PID: {pid}) exited with code {return_code}."
            )
            self.server_process = None
        except asyncio.CancelledError:
            self.logger.debug("Server process monitoring cancelled.")
        except Exception as e:
            self.logger.error(f"Error monitoring server process: {e}")


    async def stop(self):
        """Stops the self-hosted networkquality-server if it's running."""
        if not self.server_process or self.server_process.returncode is not None: # Check returncode to see if already exited
            self.logger.info("NetworkQuality server process is not running or not managed.")
            # Ensure tasks are cleaned up if process died unexpectedly
            for task in self.running_tasks:
                if not task.done():
                    task.cancel()
            if self.running_tasks:
                 await asyncio.gather(*self.running_tasks, return_exceptions=True)
            self.running_tasks.clear()
            self.server_process = None
            return

        pid = self.server_process.pid
        self.logger.info(f"Stopping NetworkQuality server process (PID: {pid})...")
        try:
            self.server_process.terminate()
            await asyncio.wait_for(self.server_process.wait(), timeout=10.0)
            self.logger.info(f"NetworkQuality server process (PID: {pid}) terminated.")
        except asyncio.TimeoutError:
            self.logger.warning(f"NetworkQuality server process (PID: {pid}) did not terminate gracefully, killing.")
            if self.server_process and self.server_process.returncode is None: # Check again before kill
                self.server_process.kill()
                await self.server_process.wait()
            self.logger.info(f"NetworkQuality server process (PID: {pid}) killed.")
        except Exception as e:
            self.logger.error(f"Error stopping NetworkQuality server process (PID: {pid}): {e}")
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
        """
        if self.server_type == 'self_hosted':
            # For self_hosted, construct from bind_address and port
            # If bind_address is 0.0.0.0, client might need to use localhost or actual IP
            connect_address = '127.0.0.1' if self.bind_address == '0.0.0.0' else self.bind_address
            return f"http://{connect_address}:{self.port}"
        elif self.server_type == 'external':
            # For external, the URL is directly specified in nq_config.server.url
            # This should be accessed by the collector directly from its config.
            # This method is more for confirming the self-hosted URL.
            # The NetworkQualityRSServerConfig dataclass has a 'url' field.
            # We can access it via the original nq_config if it was stored,
            # or the collector can look it up.
            # For clarity, this manager primarily provides the self-hosted URL.
            # The collector should rely on its own config for external URLs.
            return None # Or raise an error if called for external type by this manager
        return None


async def main_server_manager_test():
    logging.basicConfig(level=logging.DEBUG)
    from src.config import Config # Import for test

    # Create a dummy config file for testing
    test_config_content = """
networkquality:
  enabled: true
  server:
    type: "self_hosted"
    auto_start: true
    binary_path: "/usr/local/bin/networkquality-server" # ADJUST IF NEEDED
    port: 9092 # Use a different port for testing
    bind_address: "127.0.0.1"
    log_level: "debug"
  client:
    binary_path: "/usr/local/bin/networkquality"
"""
    with open("test_nq_config.yaml", "w") as f:
        f.write(test_config_content)

    config_instance = Config("test_nq_config.yaml")
    nq_config_obj = config_instance.networkquality # This is the NetworkQualityRSConfig object

    manager = NetworkQualityServerManager(nq_config_obj)

    logger.info("Attempting to start self-hosted server...")
    started = await manager.start()

    if started and manager.is_running():
        logger.info(f"Server started. URL for client to connect: {manager.get_server_url()}")
        logger.info("Server will run for 15 seconds for testing...")
        await asyncio.sleep(15)
        logger.info("Stopping server...")
        await manager.stop()
        logger.info("Server stopped.")
    elif started and not manager.is_running():
        logger.error("Manager reported start, but server is not running. Check logs for networkquality-server output.")
    else:
        logger.error("Server did not start. Check binary path and permissions for networkquality-server.")

    Path("test_nq_config.yaml").unlink(missing_ok=True)


if __name__ == "__main__":
    # asyncio.run(main_server_manager_test())
    print("NetworkQualityServerManager defined. To test, uncomment asyncio.run(main_server_manager_test()) "
          "and ensure the networkquality-server binary is available, and paths in the test are correct.")



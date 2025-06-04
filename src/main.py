#!/usr/bin/env python3
"""
Enhanced Network Intelligence Monitor - Main Application
======================================================

Updated main application that integrates all enhanced components:
- Enhanced LSTM anomaly detection
- Mimir/Prometheus integration
- Advanced network metrics collection
- Prometheus metrics export for Alloy
- Edge device optimization
- Intelligent alerting
"""

import asyncio
import logging
import signal
import sys
import os
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import Config
from src.utils.logger import setup_logging
from enhanced_integration import EnhancedNetworkIntelligenceMonitor, create_example_config, create_deployment_scripts

logger = logging.getLogger(__name__)

class EnhancedMonitorManager:
    """Manager for the enhanced monitoring system"""
    
    def __init__(self):
        self.monitor = None
        self.shutdown_event = asyncio.Event()
        
    async def initialize(self, config_path: str = "config.yaml"):
        """Initialize the enhanced monitor"""
        
        logger.info("Initializing Enhanced Network Intelligence Monitor...")
        
        # Check if config exists, create example if not
        if not Path(config_path).exists():
            logger.warning(f"Configuration file {config_path} not found")
            create_example_config()
            logger.info("Created example configuration: config-enhanced.yaml")
            logger.info("Please review and customize the configuration before running again")
            return False
        
        try:
            # Create enhanced monitor
            self.monitor = EnhancedNetworkIntelligenceMonitor(config_path)
            await self.monitor.initialize()
            
            logger.info("Enhanced Network Intelligence Monitor initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize enhanced monitor: {e}")
            return False
    
    async def run(self):
        """Run the enhanced monitoring system"""
        
        if not self.monitor:
            logger.error("Monitor not initialized")
            return
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        try:
            logger.info("Starting Enhanced Network Intelligence Monitor...")
            
            # Start monitor in background
            monitor_task = asyncio.create_task(self._run_monitor())
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
            logger.info("Shutdown signal received, stopping monitor...")
            
            # Cancel monitor task
            monitor_task.cancel()
            
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
            
            # Stop monitor
            self.monitor.stop()
            
        except Exception as e:
            logger.error(f"Error running enhanced monitor: {e}")
            raise
    
    async def _run_monitor(self):
        """Run monitor in async context"""
        
        def start_monitor():
            self.monitor.start()
        
        # Run monitor start in thread executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, start_monitor)
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self._shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, signal_handler)
    
    async def _shutdown(self):
        """Initiate shutdown"""
        self.shutdown_event.set()

def validate_environment():
    """Validate environment and dependencies"""
    
    logger.info("Validating environment...")
    
    issues = []
    
    # Check Python version
    if sys.version_info < (3, 8):
        issues.append("Python 3.8 or higher is required")
    
    # Check required directories
    required_dirs = ['data', 'data/logs', 'data/models', 'data/database']
    for directory in required_dirs:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    # Check for required environment variables for production
    env = os.getenv('ENVIRONMENT', 'development')
    if env == 'production':
        required_env_vars = ['MIMIR_ENDPOINT', 'MIMIR_TOKEN']
        for var in required_env_vars:
            if not os.getenv(var):
                issues.append(f"Environment variable {var} is required for production deployment")
    
    # Check disk space
    try:
        import shutil
        total, used, free = shutil.disk_usage('.')
        free_gb = free // (1024**3)
        if free_gb < 1:
            issues.append(f"Low disk space: {free_gb}GB available (recommend at least 1GB)")
    except Exception:
        pass
    
    # Check memory
    try:
        import psutil
        memory = psutil.virtual_memory()
        if memory.available < 512 * 1024 * 1024:  # 512MB
            issues.append(f"Low memory: {memory.available // (1024**2)}MB available (recommend at least 512MB)")
    except ImportError:
        logger.warning("psutil not available for memory check")
    
    if issues:
        logger.warning("Environment validation issues found:")
        for issue in issues:
            logger.warning(f"  - {issue}")
        return False
    
    logger.info("Environment validation passed")
    return True

def setup_edge_optimizations():
    """Setup optimizations for edge devices"""
    
    deployment_type = os.getenv('DEPLOYMENT_TYPE', 'standard')
    
    if deployment_type == 'edge':
        logger.info("Applying edge device optimizations...")
        
        # PyTorch optimizations
        os.environ['PYTORCH_JIT'] = '0'  # Disable JIT for memory savings
        os.environ['OMP_NUM_THREADS'] = '2'  # Limit threads on edge devices
        
        # Set CPU-only mode if no GPU
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
        
        logger.info("Edge optimizations applied")

def print_startup_banner():
    """Print startup banner with system information"""
    
    banner = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                 Enhanced Network Intelligence Monitor                        ║
║                              Version 1.0.0                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Features:                                                                   ║
║    • Advanced LSTM Anomaly Detection                                        ║
║    • Mimir/Prometheus Historical Baselines                                  ║
║    • Enhanced Network Metrics Collection                                    ║
║    • Prometheus Metrics Export for Alloy                                    ║
║    • Edge Device Optimization                                               ║
║    • Real-time Quality Assessment (MOS Score)                               ║
║    • Intelligent Dynamic Thresholds                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    
    print(banner)
    
    # System information
    import platform
    import psutil
    
    system_info = f"""
System Information:
  Platform: {platform.platform()}
  Python: {platform.python_version()}
  CPU Cores: {psutil.cpu_count()}
  Memory: {psutil.virtual_memory().total // (1024**3)}GB
  Deployment: {os.getenv('DEPLOYMENT_TYPE', 'standard')}
  Environment: {os.getenv('ENVIRONMENT', 'development')}
"""
    
    print(system_info)

async def run_health_check():
    """Run initial health check"""
    
    logger.info("Running initial health check...")
    
    health_checks = []
    
    try:
        # Test network connectivity
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('8.8.8.8', 53))
        sock.close()
        
        if result == 0:
            health_checks.append(("Network connectivity", "✓ PASS"))
        else:
            health_checks.append(("Network connectivity", "✗ FAIL - No internet access"))
    
    except Exception as e:
        health_checks.append(("Network connectivity", f"✗ ERROR - {e}"))
    
    # Test DNS resolution
    try:
        import socket
        socket.gethostbyname('google.com')
        health_checks.append(("DNS resolution", "✓ PASS"))
    except Exception as e:
        health_checks.append(("DNS resolution", f"✗ FAIL - {e}"))
    
    # Test PyTorch
    try:
        import torch
        tensor = torch.tensor([1.0, 2.0, 3.0])
        assert tensor.sum().item() == 6.0
        health_checks.append(("PyTorch", f"✓ PASS - {torch.__version__}"))
    except Exception as e:
        health_checks.append(("PyTorch", f"✗ FAIL - {e}"))
    
    # Test database creation
    try:
        from src.utils.database import Database
        test_db = Database(':memory:')
        await test_db.initialize()
        health_checks.append(("Database", "✓ PASS"))
    except Exception as e:
        health_checks.append(("Database", f"✗ FAIL - {e}"))
    
    # Print results
    logger.info("Health check results:")
    for check_name, result in health_checks:
        logger.info(f"  {check_name}: {result}")
    
    # Return overall health
    failed_checks = [check for check in health_checks if "FAIL" in check[1] or "ERROR" in check[1]]
    return len(failed_checks) == 0

def create_startup_scripts():
    """Create startup scripts for different environments"""
    
    # SystemD service file
    systemd_service = """[Unit]
Description=Enhanced Network Intelligence Monitor
After=network.target
Wants=network.target

[Service]
Type=simple
User=networkmon
Group=networkmon
WorkingDirectory=/opt/network-intelligence-monitor
ExecStart=/usr/bin/python3 -m src.main
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
TimeoutStopSec=30

# Environment
Environment=PYTHONPATH=/opt/network-intelligence-monitor
Environment=DEPLOYMENT_TYPE=edge
Environment=ENVIRONMENT=production

# Security
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/network-intelligence-monitor/data
PrivateTmp=yes

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=network-monitor

[Install]
WantedBy=multi-user.target
"""
    
    # Supervisor configuration
    supervisor_conf = """[program:network-monitor]
command=/usr/bin/python3 -m src.main
directory=/opt/network-intelligence-monitor
user=networkmon
group=networkmon
autostart=true
autorestart=true
startsecs=10
startretries=3
exitcodes=0,2
stopsignal=TERM
stopwaitsecs=30
redirect_stderr=true
stdout_logfile=/var/log/network-monitor/supervisor.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=3
environment=PYTHONPATH="/opt/network-intelligence-monitor",DEPLOYMENT_TYPE="edge",ENVIRONMENT="production"
"""
    
    # Docker healthcheck script
    healthcheck_script = """#!/bin/bash
# Docker healthcheck script for Enhanced Network Intelligence Monitor

set -e

# Check if API is responding
if curl -f -s http://localhost:5000/health > /dev/null; then
    echo "API health check: PASS"
else
    echo "API health check: FAIL"
    exit 1
fi

# Check if metrics endpoint is responding
if curl -f -s http://localhost:8000/metrics > /dev/null; then
    echo "Metrics health check: PASS"
else
    echo "Metrics health check: FAIL"
    exit 1
fi

# Check if monitor is collecting metrics
if curl -f -s http://localhost:5000/api/enhanced/health | grep -q '"overall_status": "healthy"'; then
    echo "System health check: PASS"
else
    echo "System health check: FAIL"
    exit 1
fi

echo "All health checks passed"
exit 0
"""
    
    # Create scripts directory
    scripts_dir = Path("scripts")
    scripts_dir.mkdir(exist_ok=True)
    
    # Write service files
    with open(scripts_dir / "network-monitor.service", "w") as f:
        f.write(systemd_service)
    
    with open(scripts_dir / "network-monitor.conf", "w") as f:
        f.write(supervisor_conf)
    
    with open(scripts_dir / "healthcheck.sh", "w") as f:
        f.write(healthcheck_script)
    
    # Make healthcheck executable
    import stat
    healthcheck_path = scripts_dir / "healthcheck.sh"
    healthcheck_path.chmod(healthcheck_path.stat().st_mode | stat.S_IEXEC)
    
    logger.info("Startup scripts created in scripts/ directory")

async def main():
    """Enhanced main function"""
    
    # Print startup banner
    print_startup_banner()
    
    # Setup logging first
    setup_logging()
    
    # Setup edge optimizations if needed
    setup_edge_optimizations()
    
    # Validate environment
    if not validate_environment():
        logger.error("Environment validation failed")
        sys.exit(1)
    
    # Run health check
    if not await run_health_check():
        logger.warning("Some health checks failed, but continuing...")
    
    # Create startup scripts
    create_startup_scripts()
    
    # Create deployment scripts
    create_deployment_scripts()
    
    # Create monitor manager
    manager = EnhancedMonitorManager()
    
    try:
        # Initialize monitor
        config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
        
        if not await manager.initialize(config_path):
            logger.error("Failed to initialize monitor")
            sys.exit(1)
        
        # Log startup completion
        logger.info("=== Enhanced Network Intelligence Monitor Started ===")
        logger.info("API Server: http://localhost:5000")
        logger.info("Metrics Endpoint: http://localhost:8000/metrics")
        logger.info("Health Check: http://localhost:5000/api/enhanced/health")
        logger.info("Grafana Alloy Config: config.alloy")
        logger.info("=========================================================")
        
        # Run monitor
        await manager.run()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        logger.info("Enhanced Network Intelligence Monitor stopped")

if __name__ == "__main__":
    # Set process title if available
    try:
        import setproctitle
        setproctitle.setproctitle("network-intelligence-monitor")
    except ImportError:
        pass
    
    # Run main function
    asyncio.run(main())

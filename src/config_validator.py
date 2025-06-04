#!/usr/bin/env python3
"""
Deployment Utilities
===================

Comprehensive deployment utilities for different environments:
- Environment detection and optimization
- Service file generation
- Backup and recovery
- Performance monitoring
- Health checks
"""

import os
import sys
import subprocess
import logging
import time
import shutil
import tarfile
import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import platform
import psutil

logger = logging.getLogger(__name__)

@dataclass
class DeploymentEnvironment:
    """Deployment environment information"""
    environment_type: str  # 'development', 'production', 'edge'
    platform: str         # 'linux', 'windows', 'macos'
    architecture: str      # 'x86_64', 'arm64', 'armv7l'
    is_container: bool
    is_systemd: bool
    is_supervisor: bool
    python_version: str
    available_memory_gb: float
    available_disk_gb: float
    network_interfaces: List[str]
    recommended_config: Dict[str, Any]

class DeploymentManager:
    """Manages deployment across different environments"""
    
    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path.cwd()
        self.deployment_env = None
        
    async def analyze_environment(self) -> DeploymentEnvironment:
        """Analyze deployment environment"""
        
        logger.info("Analyzing deployment environment...")
        
        # Detect platform and architecture
        platform_info = platform.platform()
        arch = platform.machine()
        
        # Detect container environment
        is_container = (
            os.path.exists('/.dockerenv') or
            os.path.exists('/proc/1/cgroup') and 'docker' in open('/proc/1/cgroup').read()
        )
        
        # Detect service managers
        is_systemd = self._is_systemd_available()
        is_supervisor = self._is_supervisor_available()
        
        # Determine environment type
        env_type = os.getenv('ENVIRONMENT', 'development')
        if not env_type:
            if is_container:
                env_type = 'production'
            elif psutil.virtual_memory().total < 2 * 1024**3:
                env_type = 'edge'
            else:
                env_type = 'development'
        
        # Get system resources
        memory_gb = psutil.virtual_memory().total / (1024**3)
        disk_gb = psutil.disk_usage('/').free / (1024**3)
        
        # Get network interfaces
        interfaces = []
        for interface in psutil.net_if_addrs():
            if not interface.startswith(('lo', 'docker', 'br-')):
                interfaces.append(interface)
        
        # Generate recommended configuration
        recommended_config = self._generate_recommended_config(
            env_type, memory_gb, arch, is_container
        )
        
        self.deployment_env = DeploymentEnvironment(
            environment_type=env_type,
            platform=platform.system().lower(),
            architecture=arch,
            is_container=is_container,
            is_systemd=is_systemd,
            is_supervisor=is_supervisor,
            python_version=platform.python_version(),
            available_memory_gb=memory_gb,
            available_disk_gb=disk_gb,
            network_interfaces=interfaces,
            recommended_config=recommended_config
        )
        
        logger.info(f"Environment detected: {env_type} on {platform_info}")
        logger.info(f"Resources: {memory_gb:.1f}GB RAM, {disk_gb:.1f}GB disk")
        
        return self.deployment_env
    
    def _is_systemd_available(self) -> bool:
        """Check if systemd is available"""
        try:
            result = subprocess.run(['systemctl', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _is_supervisor_available(self) -> bool:
        """Check if supervisor is available"""
        try:
            result = subprocess.run(['supervisorctl', 'version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _generate_recommended_config(self, env_type: str, memory_gb: float, 
                                   arch: str, is_container: bool) -> Dict[str, Any]:
        """Generate recommended configuration"""
        
        config = {
            'monitoring': {
                'interval': 30,
                'timeout': 10,
                'targets': ['8.8.8.8', '1.1.1.1']
            },
            'ai': {
                'train_interval': 3600,
                'initial_epochs': 100,
                'enable_quantization': False
            },
            'deployment': {
                'edge_optimization': False,
                'quantize_models': False,
                'max_memory_mb': 512
            }
        }
        
        # Environment-specific adjustments
        if env_type == 'edge' or memory_gb < 2:
            config.update({
                'monitoring': {
                    'interval': 60,
                    'timeout': 15,
                    'targets': ['8.8.8.8']
                },
                'ai': {
                    'train_interval': 7200,
                    'initial_epochs': 50,
                    'enable_quantization': True
                },
                'deployment': {
                    'edge_optimization': True,
                    'quantize_models': True,
                    'max_memory_mb': min(256, int(memory_gb * 1024 * 0.6))
                }
            })
        
        # ARM-specific optimizations
        if 'arm' in arch.lower():
            config['ai']['enable_quantization'] = True
            config['deployment']['quantize_models'] = True
        
        # Container-specific adjustments
        if is_container:
            config['api'] = {'host': '0.0.0.0', 'port': 5000}
            config['metrics'] = {'host': '0.0.0.0', 'port': 8000}
        
        return config
    
    async def create_deployment_package(self, output_path: str = None) -> str:
        """Create deployment package"""
        
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"network-monitor-deployment-{timestamp}.tar.gz"
        
        logger.info(f"Creating deployment package: {output_path}")
        
        # Create temporary directory for package contents
        temp_dir = Path(f"/tmp/network-monitor-deploy-{int(time.time())}")
        temp_dir.mkdir(exist_ok=True)
        
        try:
            # Copy source code
            src_dir = temp_dir / "src"
            shutil.copytree(self.project_root / "src", src_dir)
            
            # Copy configuration files
            config_files = ['requirements.txt', 'requirements-edge.txt']
            for config_file in config_files:
                src_file = self.project_root / config_file
                if src_file.exists():
                    shutil.copy2(src_file, temp_dir)
            
            # Create deployment scripts
            await self._create_deployment_scripts(temp_dir)
            
            # Create configuration templates
            await self._create_config_templates(temp_dir)
            
            # Create documentation
            await self._create_deployment_docs(temp_dir)
            
            # Create tarball
            with tarfile.open(output_path, 'w:gz') as tar:
                tar.add(temp_dir, arcname='network-intelligence-monitor')
            
            logger.info(f"Deployment package created: {output_path}")
            
        finally:
            # Clean up temporary directory
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        return output_path
    
    async def _create_deployment_scripts(self, temp_dir: Path):
        """Create deployment scripts"""
        
        scripts_dir = temp_dir / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        
        # Main installation script
        install_script = '''#!/bin/bash
# Network Intelligence Monitor - Installation Script

set -e

INSTALL_DIR="/opt/network-intelligence-monitor"
SERVICE_USER="networkmon"
PYTHON_CMD="python3"

echo "Installing Network Intelligence Monitor..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# Detect platform
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "Cannot detect OS"
    exit 1
fi

# Install system dependencies
echo "Installing system dependencies..."
case $OS in
    ubuntu|debian)
        apt-get update
        apt-get install -y python3 python3-pip python3-venv build-essential
        ;;
    centos|rhel|fedora)
        if command -v dnf &> /dev/null; then
            dnf install -y python3 python3-pip python3-devel gcc
        else
            yum install -y python3 python3-pip python3-devel gcc
        fi
        ;;
    *)
        echo "Unsupported OS: $OS"
        exit 1
        ;;
esac

# Create service user
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "Creating service user: $SERVICE_USER"
    useradd --system --shell /bin/false --home-dir $INSTALL_DIR $SERVICE_USER
fi

# Create installation directory
mkdir -p $INSTALL_DIR
cp -r * $INSTALL_DIR/
chown -R $SERVICE_USER:$SERVICE_USER $INSTALL_DIR

# Create virtual environment
echo "Creating Python virtual environment..."
cd $INSTALL_DIR
sudo -u $SERVICE_USER $PYTHON_CMD -m venv venv
sudo -u $SERVICE_USER $INSTALL_DIR/venv/bin/pip install --upgrade pip

# Install Python dependencies
echo "Installing Python dependencies..."
if [ -f requirements-edge.txt ] && [ $(free -m | awk 'NR==2{print $2}') -lt 2048 ]; then
    echo "Installing edge-optimized requirements..."
    sudo -u $SERVICE_USER $INSTALL_DIR/venv/bin/pip install -r requirements-edge.txt
else
    sudo -u $SERVICE_USER $INSTALL_DIR/venv/bin/pip install -r requirements.txt
fi

# Create data directories
echo "Creating data directories..."
sudo -u $SERVICE_USER mkdir -p $INSTALL_DIR/data/{logs,models,database,exports}

# Install service file
if systemctl --version >/dev/null 2>&1; then
    echo "Installing systemd service..."
    cp scripts/network-monitor.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable network-monitor.service
    echo "Service installed. Start with: systemctl start network-monitor"
else
    echo "Systemd not available. Manual startup required."
fi

# Create configuration
if [ ! -f $INSTALL_DIR/config.yaml ]; then
    echo "Creating default configuration..."
    cp config-templates/config-production.yaml $INSTALL_DIR/config.yaml
    chown $SERVICE_USER:$SERVICE_USER $INSTALL_DIR/config.yaml
fi

echo "Installation completed successfully!"
echo ""
echo "Next steps:"
echo "1. Edit configuration: $INSTALL_DIR/config.yaml"
echo "2. Start service: systemctl start network-monitor"
echo "3. Check status: systemctl status network-monitor"
echo "4. View logs: journalctl -u network-monitor -f"
'''
        
        # Edge device script
        edge_script = '''#!/bin/bash
# Network Intelligence Monitor - Edge Device Setup

set -e

echo "Setting up Network Intelligence Monitor for edge devices..."

# Detect if Raspberry Pi
if grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "Raspberry Pi detected"
    
    # Install Pi-specific optimizations
    echo "Installing Raspberry Pi optimizations..."
    
    # Optimize GPU memory split
    if command -v raspi-config &> /dev/null; then
        raspi-config nonint do_memory_split 16
    fi
    
    # Install optimized PyTorch
    pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cpu
    
    # Set CPU governor to performance
    echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
fi

# Set environment variables for edge deployment
cat >> /etc/environment << EOF
DEPLOYMENT_TYPE=edge
PYTORCH_JIT=0
OMP_NUM_THREADS=4
EOF

# Create edge-optimized configuration
cat > config.yaml << EOF
logging:
  level: INFO
  file: data/logs/network_intelligence.log
  max_size_mb: 5
  backup_count: 2

monitoring:
  targets: ['8.8.8.8', '1.1.1.1']
  interval: 60
  timeout: 15
  enhanced_features: true

ai:
  train_interval: 7200
  initial_epochs: 50
  enable_quantization: true

deployment:
  edge_optimization: true
  quantize_models: true
  max_memory_mb: 256
EOF

echo "Edge setup completed!"
'''
        
        # Write scripts
        with open(scripts_dir / "install.sh", "w") as f:
            f.write(install_script)
        
        with open(scripts_dir / "setup-edge.sh", "w") as f:
            f.write(edge_script)
        
        # Make scripts executable
        for script in scripts_dir.glob("*.sh"):
            script.chmod(0o755)
    
    async def _create_config_templates(self, temp_dir: Path):
        """Create configuration templates"""
        
        templates_dir = temp_dir / "config-templates"
        templates_dir.mkdir(exist_ok=True)
        
        # Production configuration
        prod_config = {
            'logging': {
                'level': 'INFO',
                'file': 'data/logs/network_intelligence.log',
                'max_size_mb': 10,
                'backup_count': 5
            },
            'monitoring': {
                'targets': ['8.8.8.8', '1.1.1.1', 'google.com'],
                'interval': 30,
                'timeout': 10,
                'enhanced_features': True
            },
            'ai': {
                'model_dir': 'data/models',
                'train_interval': 3600,
                'initial_epochs': 100,
                'auto_train': True
            },
            'api': {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False
            },
            'metrics': {
                'port': 8000,
                'host': '0.0.0.0'
            },
            'database': {
                'path': 'data/database/network_intelligence.db',
                'cleanup_days': 30,
                'backup_enabled': True
            },
            'mimir': {
                'enabled': False,
                'prometheus_url': None,
                'mimir_url': None,
                'tenant_id': 'network-monitoring'
            },
            'alerts': {
                'enabled': True,
                'webhook_url': None
            },
            'deployment': {
                'edge_optimization': False,
                'quantize_models': False,
                'max_memory_mb': 512
            }
        }
        
        # Edge configuration
        edge_config = prod_config.copy()
        edge_config.update({
            'monitoring': {
                'targets': ['8.8.8.8', '1.1.1.1'],
                'interval': 60,
                'timeout': 15,
                'enhanced_features': True
            },
            'ai': {
                'model_dir': 'data/models',
                'train_interval': 7200,
                'initial_epochs': 50,
                'auto_train': True,
                'enable_quantization': True
            },
            'database': {
                'path': 'data/database/network_intelligence.db',
                'cleanup_days': 7,
                'backup_enabled': False
            },
            'deployment': {
                'edge_optimization': True,
                'quantize_models': True,
                'max_memory_mb': 256
            }
        })
        
        # Write templates
        with open(templates_dir / "config-production.yaml", "w") as f:
            yaml.dump(prod_config, f, default_flow_style=False, indent=2)
        
        with open(templates_dir / "config-edge.yaml", "w") as f:
            yaml.dump(edge_config, f, default_flow_style=False, indent=2)
    
    async def _create_deployment_docs(self, temp_dir: Path):
        """Create deployment documentation"""
        
        docs_dir = temp_dir / "docs"
        docs_dir.mkdir(exist_ok=True)
        
        deployment_guide = '''# Network Intelligence Monitor - Deployment Guide

## Quick Start

### Standard Deployment

1. Extract the deployment package:
   ```bash
   tar -xzf network-monitor-deployment-*.tar.gz
   cd network-intelligence-monitor
   ```

2. Run the installation script:
   ```bash
   sudo ./scripts/install.sh
   ```

3. Configure the system:
   ```bash
   sudo nano /opt/network-intelligence-monitor/config.yaml
   ```

4. Start the service:
   ```bash
   sudo systemctl start network-monitor
   ```

### Edge Device Deployment (Raspberry Pi)

1. Extract and install:
   ```bash
   tar -xzf network-monitor-deployment-*.tar.gz
   cd network-intelligence-monitor
   sudo ./scripts/install.sh
   ```

2. Run edge optimizations:
   ```bash
   sudo ./scripts/setup-edge.sh
   ```

3. Start the service:
   ```bash
   sudo systemctl start network-monitor
   ```

## Configuration

### Environment Variables

- `ENVIRONMENT`: deployment environment (development/production/edge)
- `MIMIR_ENDPOINT`: Mimir API endpoint
- `MIMIR_TOKEN`: Mimir authentication token
- `WEBHOOK_URL`: Alert webhook URL

### Network Requirements

The monitor needs outbound access to:
- Monitoring targets (configurable, default: 8.8.8.8, 1.1.1.1)
- Mimir/Prometheus endpoints (if configured)
- Package repositories for updates

### Resource Requirements

#### Minimum Requirements
- Python 3.8+
- 512MB RAM
- 1GB disk space
- Network connectivity

#### Recommended Requirements
- Python 3.9+
- 2GB RAM
- 5GB disk space
- Multiple network interfaces

#### Edge Device Requirements
- 256MB RAM
- 500MB disk space
- Single network interface

## Monitoring

### Health Checks

- API Health: `curl http://localhost:5000/health`
- Metrics: `curl http://localhost:8000/metrics`
- Service Status: `systemctl status network-monitor`

### Logs

- Application logs: `/opt/network-intelligence-monitor/data/logs/`
- System logs: `journalctl -u network-monitor -f`

### Performance Monitoring

Monitor these metrics:
- CPU usage: Should be < 80%
- Memory usage: Should be < 80% of allocated
- Disk usage: Should be < 80%
- Network connectivity to targets

## Troubleshooting

### Common Issues

1. **Service won't start**
   - Check configuration file syntax
   - Verify Python dependencies
   - Check file permissions

2. **High memory usage**
   - Enable edge optimization
   - Reduce monitoring targets
   - Increase cleanup frequency

3. **Network connectivity issues**
   - Verify target accessibility
   - Check firewall rules
   - Validate DNS resolution

### Log Analysis

Key log messages to monitor:
- `ERROR` level messages indicate problems
- `WARNING` messages suggest optimization opportunities
- High frequency of connection errors may indicate network issues

## Updates

### Manual Updates

1. Stop the service:
   ```bash
   sudo systemctl stop network-monitor
   ```

2. Backup current installation:
   ```bash
   sudo cp -r /opt/network-intelligence-monitor /opt/network-intelligence-monitor.backup
   ```

3. Extract new version and run update script

4. Start the service:
   ```bash
   sudo systemctl start network-monitor
   ```

### Configuration Migration

The system automatically migrates configuration files between versions.
Always backup your configuration before updates.

## Integration

### Grafana Alloy

Configure Alloy to scrape metrics:
```yaml
prometheus.scrape "network_intelligence" {
  targets = [
    {"__address__" = "localhost:8000"},
  ]
  forward_to = [prometheus.remote_write.mimir.receiver]
  job_name = "network-intelligence-monitor"
  scrape_interval = "30s"
  metrics_path = "/metrics"
}
```

### Mimir Integration

Configure Mimir endpoints in config.yaml:
```yaml
mimir:
  enabled: true
  mimir_url: "https://your-mimir-endpoint.com"
  tenant_id: "network-monitoring"
```

### Alerting

Configure webhook alerts:
```yaml
alerts:
  enabled: true
  webhook_url: "https://your-webhook-endpoint.com/alerts"
```

## Security

### Network Security
- Limit outbound connections to required targets
- Use firewall rules to restrict API access
- Consider VPN for remote monitoring

### Data Security
- Database files contain network performance data
- Log files may contain target information
- Use appropriate file permissions

### Authentication
- API endpoints are unauthenticated by default
- Consider reverse proxy with authentication for production
- Use HTTPS for external communications

## Support

For support and updates:
- Check logs for error messages
- Verify configuration with validation tool
- Monitor system resources
- Review documentation for troubleshooting steps
'''
        
        with open(docs_dir / "DEPLOYMENT.md", "w") as f:
            f.write(deployment_guide)
    
    async def create_service_files(self) -> Dict[str, str]:
        """Create service files for different service managers"""
        
        if not self.deployment_env:
            await self.analyze_environment()
        
        service_files = {}
        
        # SystemD service file
        if self.deployment_env.is_systemd:
            systemd_service = self._create_systemd_service()
            service_files['systemd'] = systemd_service
        
        # Supervisor configuration
        if self.deployment_env.is_supervisor:
            supervisor_config = self._create_supervisor_config()
            service_files['supervisor'] = supervisor_config
        
        # Docker Compose
        docker_compose = self._create_docker_compose()
        service_files['docker_compose'] = docker_compose
        
        return service_files
    
    def _create_systemd_service(self) -> str:
        """Create SystemD service file"""
        
        return f'''[Unit]
Description=Network Intelligence Monitor
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=networkmon
Group=networkmon
WorkingDirectory=/opt/network-intelligence-monitor
ExecStart=/opt/network-intelligence-monitor/venv/bin/python -m src.main
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
TimeoutStopSec=30

# Environment
Environment=PYTHONPATH=/opt/network-intelligence-monitor
Environment=DEPLOYMENT_TYPE={self.deployment_env.environment_type}
Environment=PYTHONUNBUFFERED=1

# Security
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/network-intelligence-monitor/data
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=network-monitor

# Resource limits
MemoryMax={int(self.deployment_env.recommended_config['deployment']['max_memory_mb'])}M
CPUQuota=80%

[Install]
WantedBy=multi-user.target
'''
    
    def _create_supervisor_config(self) -> str:
        """Create Supervisor configuration"""
        
        return f'''[program:network-monitor]
command=/opt/network-intelligence-monitor/venv/bin/python -m src.main
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
environment=PYTHONPATH="/opt/network-intelligence-monitor",DEPLOYMENT_TYPE="{self.deployment_env.environment_type}",PYTHONUNBUFFERED="1"
'''
    
    def _create_docker_compose(self) -> str:
        """Create Docker Compose configuration"""
        
        return '''version: '3.8'

services:
  network-monitor:
    build: .
    container_name: network-intelligence-monitor
    restart: unless-stopped
    ports:
      - "5000:5000"   # API
      - "8000:8000"   # Metrics
    volumes:
      - ./data:/app/data
      - ./config.yaml:/app/config.yaml
    environment:
      - ENVIRONMENT=production
      - DEPLOYMENT_TYPE=container
      - PYTHONUNBUFFERED=1
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - monitoring

  # Optional: Grafana for visualization
  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    volumes:
      - grafana-storage:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    networks:
      - monitoring

volumes:
  grafana-storage:

networks:
  monitoring:
    driver: bridge
'''

class BackupManager:
    """Manages backups and recovery"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.backup_dir = project_root / "backups"
        self.backup_dir.mkdir(exist_ok=True)
    
    async def create_backup(self, include_models: bool = True) -> str:
        """Create system backup"""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"network-monitor-backup-{timestamp}.tar.gz"
        backup_path = self.backup_dir / backup_name
        
        logger.info(f"Creating backup: {backup_name}")
        
        with tarfile.open(backup_path, 'w:gz') as tar:
            # Backup configuration
            if (self.project_root / "config.yaml").exists():
                tar.add(self.project_root / "config.yaml", arcname="config.yaml")
            
            # Backup database
            db_dir = self.project_root / "data" / "database"
            if db_dir.exists():
                tar.add(db_dir, arcname="data/database")
            
            # Backup models (optional)
            if include_models:
                models_dir = self.project_root / "data" / "models"
                if models_dir.exists():
                    tar.add(models_dir, arcname="data/models")
            
            # Backup logs (recent only)
            logs_dir = self.project_root / "data" / "logs"
            if logs_dir.exists():
                for log_file in logs_dir.glob("*.log"):
                    # Only backup logs from last 7 days
                    if time.time() - log_file.stat().st_mtime < 7 * 24 * 3600:
                        tar.add(log_file, arcname=f"data/logs/{log_file.name}")
        
        logger.info(f"Backup created: {backup_path}")
        return str(backup_path)
    
    async def restore_backup(self, backup_path: str, stop_service: bool = True) -> bool:
        """Restore from backup"""
        
        logger.info(f"Restoring from backup: {backup_path}")
        
        # Stop service if requested
        if stop_service:
            await self._stop_service()
        
        try:
            with tarfile.open(backup_path, 'r:gz') as tar:
                tar.extractall(self.project_root)
            
            logger.info("Backup restored successfully")
            return True
            
        except Exception as e:
            logger.error(f"Backup restore failed: {e}")
            return False
        finally:
            if stop_service:
                await self._start_service()
    
    async def _stop_service(self):
        """Stop the service"""
        try:
            subprocess.run(['systemctl', 'stop', 'network-monitor'], check=True)
        except subprocess.CalledProcessError:
            logger.warning("Failed to stop service via systemctl")
    
    async def _start_service(self):
        """Start the service"""
        try:
            subprocess.run(['systemctl', 'start', 'network-monitor'], check=True)
        except subprocess.CalledProcessError:
            logger.warning("Failed to start service via systemctl")
    
    def cleanup_old_backups(self, keep_days: int = 30):
        """Clean up old backups"""
        
        cutoff_time = time.time() - (keep_days * 24 * 3600)
        
        for backup_file in self.backup_dir.glob("network-monitor-backup-*.tar.gz"):
            if backup_file.stat().st_mtime < cutoff_time:
                backup_file.unlink()
                logger.info(f"Removed old backup: {backup_file.name}")

# Utility functions

async def detect_and_optimize_environment() -> DeploymentEnvironment:
    """Detect environment and create optimized configuration"""
    
    manager = DeploymentManager()
    env = await manager.analyze_environment()
    
    # Create optimized config file
    config_path = Path("config-optimized.yaml")
    with open(config_path, 'w') as f:
        yaml.dump(env.recommended_config, f, default_flow_style=False, indent=2)
    
    logger.info(f"Optimized configuration created: {config_path}")
    
    return env

async def create_production_deployment():
    """Create production deployment package"""
    
    manager = DeploymentManager()
    await manager.analyze_environment()
    
    # Create deployment package
    package_path = await manager.create_deployment_package()
    
    # Create service files
    service_files = await manager.create_service_files()
    
    # Save service files
    scripts_dir = Path("scripts")
    scripts_dir.mkdir(exist_ok=True)
    
    for service_type, content in service_files.items():
        file_path = scripts_dir / f"network-monitor.{service_type}"
        with open(file_path, 'w') as f:
            f.write(content)
        
        logger.info(f"Created {service_type} service file: {file_path}")
    
    return package_path

def create_health_check_script() -> str:
    """Create health check script"""
    
    script = '''#!/bin/bash
# Network Intelligence Monitor Health Check

set -e

API_URL="http://localhost:5000"
METRICS_URL="http://localhost:8000"
ERROR_COUNT=0

echo "Network Intelligence Monitor Health Check"
echo "========================================"

# Check API health
echo -n "API Health Check... "
if curl -sf "$API_URL/health" > /dev/null; then
    echo "✓ PASS"
else
    echo "✗ FAIL"
    ERROR_COUNT=$((ERROR_COUNT + 1))
fi

# Check metrics endpoint
echo -n "Metrics Endpoint... "
if curl -sf "$METRICS_URL/metrics" > /dev/null; then
    echo "✓ PASS"
else
    echo "✗ FAIL"
    ERROR_COUNT=$((ERROR_COUNT + 1))
fi

# Check service status
echo -n "Service Status... "
if systemctl is-active --quiet network-monitor; then
    echo "✓ PASS"
else
    echo "✗ FAIL"
    ERROR_COUNT=$((ERROR_COUNT + 1))
fi

# Check disk space
echo -n "Disk Space... "
DISK_USAGE=$(df /opt/network-intelligence-monitor | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    echo "✓ PASS ($DISK_USAGE% used)"
else
    echo "⚠ WARNING ($DISK_USAGE% used)"
fi

# Check memory usage
echo -n "Memory Usage... "
MEMORY_USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
if [ "$MEMORY_USAGE" -lt 80 ]; then
    echo "✓ PASS ($MEMORY_USAGE% used)"
else
    echo "⚠ WARNING ($MEMORY_USAGE% used)"
fi

echo ""
if [ $ERROR_COUNT -eq 0 ]; then
    echo "✓ All health checks passed"
    exit 0
else
    echo "✗ $ERROR_COUNT health check(s) failed"
    exit 1
fi
'''
    
    return script

if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Create deployment package
        package_path = await create_production_deployment()
        print(f"Deployment package created: {package_path}")
        
        # Create health check script
        health_script = create_health_check_script()
        with open("scripts/health_check.sh", "w") as f:
            f.write(health_script)
        os.chmod("scripts/health_check.sh", 0o755)
        print("Health check script created: scripts/health_check.sh")
    
    asyncio.run(main())

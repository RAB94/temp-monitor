#!/usr/bin/env python3
# src/config.py
"""
Configuration Management
=======================

Centralized configuration management for the Network Intelligence Monitor.
Supports YAML files, environment variables, and runtime overrides.
Includes configuration for networkquality-rs.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class MonitoringConfig:
    """Monitoring configuration"""
    targets: list = field(default_factory=lambda: ['8.8.8.8', '1.1.1.1', 'google.com'])
    interval: int = 30
    timeout: int = 10
    enabled: bool = True
    enhanced_features: bool = True

@dataclass
class AIConfig:
    """AI/ML configuration"""
    model_dir: str = 'data/models'
    train_interval: int = 3600
    initial_epochs: int = 100
    baseline_window: int = 1000
    training_hours: int = 24
    auto_train: bool = True
    enable_quantization: bool = True 
    sequence_length: int = 20
    input_size: int = 14
    hidden_size: int = 64
    num_layers: int = 2

@dataclass
class APIConfig:
    """API server configuration"""
    host: str = '0.0.0.0'
    port: int = 5000
    debug: bool = False
    cors_enabled: bool = True
    websocket_enabled: bool = True  # New: Default to True
    websocket_port: int = 8001      # New: Default port

@dataclass
class DatabaseConfig:
    """Database configuration"""
    path: str = 'data/database/network_intelligence.db'
    cleanup_days: int = 30
    backup_enabled: bool = True
    backup_interval_hours: int = 24

@dataclass
class MimirConfig:
    """Mimir/Prometheus configuration"""
    prometheus_url: Optional[str] = None
    mimir_url: Optional[str] = None
    tenant_id: str = 'network-monitoring'
    enabled: bool = False

@dataclass
class MetricsConfig:
    """Metrics export configuration"""
    port: int = 8000
    host: str = '0.0.0.0'
    batch_size: int = 10
    enable_aggregation: bool = True

@dataclass
class AlertsConfig:
    """Alerts configuration"""
    enabled: bool = True
    webhook_url: Optional[str] = None
    email_enabled: bool = False
    smtp_server: Optional[str] = None
    smtp_port: int = 587
    email_recipients: list = field(default_factory=list)

@dataclass
class DeploymentConfig:
    """Deployment configuration"""
    edge_optimization: bool = False
    quantize_models: bool = False
    reduce_memory_usage: bool = False
    max_memory_mb: int = 512

@dataclass
class NetworkQualityRSClientConfig:
    """networkquality-rs client configuration"""
    binary_path: str = '/usr/local/bin/networkquality' 
    test_duration: int = 10 
    parallel_streams: int = 8 

@dataclass
class NetworkQualityRSServerConfig:
    """networkquality-rs server configuration (for self-hosting)"""
    type: str = 'external' 
    url: Optional[str] = None 
    auto_start: bool = False 
    binary_path: str = '/usr/local/bin/networkquality-server' 
    port: int = 9090
    bind_address: str = '0.0.0.0'
    log_level: str = 'info'
    additional_args: List[str] = field(default_factory=list)

@dataclass
class NetworkQualityRSConfig:
    """Overall configuration for networkquality-rs integration"""
    enabled: bool = False
    client: NetworkQualityRSClientConfig = field(default_factory=NetworkQualityRSClientConfig)
    server: NetworkQualityRSServerConfig = field(default_factory=NetworkQualityRSServerConfig)
    thresholds: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        'bufferbloat_ms': {'mild': 30, 'moderate': 60, 'severe': 100},
        'rpm': {'poor': 100, 'fair': 300, 'good': 600, 'excellent': 800},
        'quality_score': {'poor': 200, 'fair': 500, 'good': 750, 'excellent': 900}
    })
    testing: Dict[str, Any] = field(default_factory=lambda: { 
        'strategy': 'fixed', 
        'adaptive_intervals': {
            'excellent': 3600, 'good': 1800, 'fair': 600, 'poor': 300, 'error': 300
        },
        'default_interval_seconds': 300
    })

class Config:
    """Main configuration class"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self._config_data = {}

        self.monitoring = MonitoringConfig()
        self.ai = AIConfig()
        self.api = APIConfig()
        self.database = DatabaseConfig()
        self.mimir = MimirConfig()
        self.metrics = MetricsConfig()
        self.alerts = AlertsConfig()
        self.deployment = DeploymentConfig()
        self.networkquality = NetworkQualityRSConfig() 

        self.load_config()

    def load_config(self):
        """Load configuration from file and environment variables"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    self._config_data = yaml.safe_load(f) or {}
                logger.info(f"Loaded configuration from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to load config file {self.config_path}: {e}")
                self._config_data = {}
        else:
            logger.warning(f"Config file {self.config_path} not found, using defaults")
            self._config_data = {}

        self._update_config_objects()
        self._load_environment_overrides()
        self._validate_config()


    def _update_config_objects(self):
        """Update configuration objects from loaded data"""
        config_sections = {
            'monitoring': self.monitoring,
            'ai': self.ai,
            'api': self.api,
            'database': self.database,
            'mimir': self.mimir,
            'metrics': self.metrics,
            'alerts': self.alerts,
            'deployment': self.deployment,
            'networkquality': self.networkquality 
        }

        for section_name, section_obj in config_sections.items():
            section_data = self._config_data.get(section_name, {})
            if isinstance(section_obj, NetworkQualityRSConfig): 
                # Handle enabled flag first
                if 'enabled' in section_data:
                    section_obj.enabled = section_data['enabled']
                    
                # Handle client configuration
                if 'client' in section_data:
                    client_data = section_data['client']
                    for key, value in client_data.items():
                         if hasattr(section_obj.client, key):
                            setattr(section_obj.client, key, value)
                            
                # Handle server configuration        
                if 'server' in section_data:
                    server_data = section_data['server']
                    for key, value in server_data.items():
                         if hasattr(section_obj.server, key):
                            setattr(section_obj.server, key, value)
                            
                # Handle thresholds
                if 'thresholds' in section_data: 
                    section_obj.thresholds.update(section_data['thresholds'])
                    
                # Handle testing configuration
                if 'testing' in section_data: 
                    section_obj.testing.update(section_data['testing'])
            else:
                # Handle other configuration objects normally
                for key, value in section_data.items():
                    if hasattr(section_obj, key):
                        setattr(section_obj, key, value)

        for section_name, section_obj in config_sections.items():
            section_data = self._config_data.get(section_name, {})
            if isinstance(section_obj, NetworkQualityRSConfig): 
                if 'client' in section_data:
                    for key, value in section_data['client'].items():
                         if hasattr(section_obj.client, key):
                            setattr(section_obj.client, key, value)
                if 'server' in section_data:
                    for key, value in section_data['server'].items():
                         if hasattr(section_obj.server, key):
                            setattr(section_obj.server, key, value)
                if 'thresholds' in section_data: 
                    section_obj.thresholds = section_data['thresholds']
                if 'testing' in section_data: 
                    section_obj.testing = section_data['testing']
                if 'enabled' in section_data:
                    section_obj.enabled = section_data['enabled']
            else:
                for key, value in section_data.items():
                    if hasattr(section_obj, key):
                        setattr(section_obj, key, value)


    def _load_environment_overrides(self):
        """Load configuration overrides from environment variables"""
        env_mappings = {
            'MONITORING_INTERVAL': (self.monitoring, 'interval', int),
            'MONITORING_TIMEOUT': (self.monitoring, 'timeout', int),
            'MONITORING_TARGETS': (self.monitoring, 'targets', lambda x: x.split(',')),
            'API_HOST': (self.api, 'host', str),
            'API_PORT': (self.api, 'port', int),
            'API_WEBSOCKET_ENABLED': (self.api, 'websocket_enabled', lambda x: x.lower() == 'true'), # New Env Var
            'API_WEBSOCKET_PORT': (self.api, 'websocket_port', int), # New Env Var
            'DATABASE_PATH': (self.database, 'path', str),
            'MIMIR_ENDPOINT': (self.mimir, 'mimir_url', str), 
            'PROMETHEUS_ENDPOINT': (self.mimir, 'prometheus_url', str), 
            'MIMIR_TENANT_ID': (self.mimir, 'tenant_id', str),
            'MIMIR_ENABLED':(self.mimir, 'enabled', lambda x: x.lower() == 'true'),
            'METRICS_PORT': (self.metrics, 'port', int),
            'ALERTS_WEBHOOK_URL':(self.alerts, 'webhook_url', str),
            'ALERTS_ENABLED':(self.alerts, 'enabled', lambda x: x.lower() == 'true'),
            'DEPLOYMENT_EDGE_OPTIMIZATION': (self.deployment, 'edge_optimization', lambda x: x.lower() == 'true'),
            'NQ_ENABLED': (self.networkquality, 'enabled', lambda x: x.lower() == 'true'),
            'NQ_SERVER_URL': (self.networkquality.server, 'url', str),
            'NQ_CLIENT_BINARY_PATH': (self.networkquality.client, 'binary_path', str),
            'NQ_SERVER_BINARY_PATH': (self.networkquality.server, 'binary_path', str),
            'NQ_SERVER_TYPE': (self.networkquality.server, 'type', str),
            'NQ_SERVER_AUTO_START': (self.networkquality.server, 'auto_start', lambda x: x.lower() == 'true'),
        }

        for env_var, (config_obj, key, converter) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    converted_value = converter(value)
                    setattr(config_obj, key, converted_value)
                    logger.debug(f"Override {config_obj.__class__.__name__}.{key} = {converted_value} from {env_var}")
                except Exception as e:
                    logger.warning(f"Failed to parse environment variable {env_var}={value}: {e}")

    def _validate_config(self):
        """Validate configuration values"""
        if not self.monitoring.targets:
            self.monitoring.targets = ['8.8.8.8']
            logger.warning("No monitoring targets specified, using default ['8.8.8.8']")

        if self.networkquality.enabled:
            nq_client_bin = Path(self.networkquality.client.binary_path)
            if not nq_client_bin.is_absolute() and not nq_client_bin.exists():
                common_paths = [Path("/usr/local/bin/networkquality"), Path("/usr/bin/networkquality"), Path("./networkquality")]
                for p in common_paths:
                    if p.exists():
                        self.networkquality.client.binary_path = str(p.resolve())
                        logger.info(f"Resolved networkquality client binary to: {self.networkquality.client.binary_path}")
                        break
                else: 
                     if not Path(self.networkquality.client.binary_path).exists(): 
                        logger.warning(f"networkquality client binary not found at {self.networkquality.client.binary_path}")
            
            # REMOVED FAULTY VALIDATION LOGIC. The networkquality tool does not need a server URL
            # as it defaults to Cloudflare. This fixes the startup error.
            
        logger.info("Configuration validation completed.")


    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation"""
        parts = key.split('.')
        obj = self
        try:
            for part in parts:
                if isinstance(obj, dict): 
                    obj = obj.get(part)
                else: 
                    obj = getattr(obj, part)
                if obj is None and default is not None : return default 
            return obj if obj is not None else default
        except (AttributeError, TypeError):
            return default

    def set(self, key: str, value: Any):
        """Set configuration value using dot notation"""
        parts = key.split('.')
        obj = self
        try:
            for part in parts[:-1]:
                obj = getattr(obj, part)
            setattr(obj, parts[-1], value)
            logger.info(f"Configuration updated: {key} = {value}")
        except AttributeError:
            logger.error(f"Failed to set configuration key: {key}")


    def save_config(self, path: Optional[str] = None):
        """Save current configuration to file"""
        save_path = Path(path) if path else self.config_path
        try:
            self._config_data = self.to_dict()
            with open(save_path, 'w') as f:
                yaml.dump(self._config_data, f, default_flow_style=False, indent=2)
            logger.info(f"Configuration saved to {save_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration to {save_path}: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            'monitoring': self.monitoring.__dict__,
            'ai': self.ai.__dict__,
            'api': self.api.__dict__,
            'database': self.database.__dict__,
            'mimir': self.mimir.__dict__,
            'metrics': self.metrics.__dict__,
            'alerts': self.alerts.__dict__,
            'deployment': self.deployment.__dict__,
            'networkquality': { 
                'enabled': self.networkquality.enabled,
                'client': self.networkquality.client.__dict__,
                'server': self.networkquality.server.__dict__,
                'thresholds': self.networkquality.thresholds,
                'testing': self.networkquality.testing
            }
        }

    @property
    def database_path(self) -> str:
        """Get database path"""
        return self.database.path

    def is_edge_deployment(self) -> bool:
        """Check if this is an edge deployment"""
        return self.deployment.edge_optimization or os.getenv('DEPLOYMENT_TYPE') == 'edge'

    def get_network_interfaces(self) -> list:
        """Get network interfaces for monitoring"""
        try:
            import psutil
            interfaces = []
            for interface_name, addresses in psutil.net_if_addrs().items():
                if interface_name.startswith(('lo', 'docker', 'br-', 'veth')):
                    continue
                stats = psutil.net_if_stats().get(interface_name)
                if stats and stats.isup:
                    interfaces.append({
                        'name': interface_name,
                        'addresses': [addr.address for addr in addresses],
                        'family': [addr.family.name for addr in addresses] # type: ignore
                    })
            return interfaces
        except ImportError:
            logger.warning("psutil not available, cannot detect network interfaces")
            return []
        except Exception as e:
            logger.error(f"Error detecting network interfaces: {e}")
            return []

def create_default_config_dict() -> Dict[str, Any]:
    """Create default configuration dictionary for initial save"""
    default_cfg = Config()
    default_dict = default_cfg.to_dict()

    if isinstance(default_dict['ai']['model_dir'], Path):
        default_dict['ai']['model_dir'] = str(default_dict['ai']['model_dir'])
    if isinstance(default_dict['database']['path'], Path):
        default_dict['database']['path'] = str(default_dict['database']['path'])

    return default_dict

def create_config_file_if_not_exists(config_path_str: str = "config.yaml"):
    """Creates a default config.yaml if it doesn't exist."""
    config_path = Path(config_path_str)
    if not config_path.exists():
        logger.info(f"Configuration file '{config_path_str}' not found. Creating with default values.")
        default_config_data = create_default_config_dict()
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w') as f:
                yaml.dump(default_config_data, f, default_flow_style=False, indent=2)
            logger.info(f"Default configuration file created at '{config_path_str}'.")
        except Exception as e:
            logger.error(f"Could not create default configuration file: {e}")

if __name__ == '__main__':
    create_config_file_if_not_exists("example_config.yaml")

    cfg = Config("example_config.yaml")
    print(f"Monitoring Interval: {cfg.monitoring.interval}")
    print(f"NetworkQuality Enabled: {cfg.networkquality.enabled}")
    print(f"NetworkQuality Client Binary: {cfg.networkquality.client.binary_path}")
    print(f"NetworkQuality Server URL (if external or self-hosted): {cfg.networkquality.server.url}")
    print(f"NetworkQuality Server Type: {cfg.networkquality.server.type}")
    print(f"API WebSocket Enabled: {cfg.api.websocket_enabled}")
    print(f"API WebSocket Port: {cfg.api.websocket_port}")

    cfg.api.websocket_enabled = False
    cfg.api.websocket_port = 11560
    # cfg.save_config("example_config_updated.yaml")

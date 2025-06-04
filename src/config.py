#!/usr/bin/env python3
"""
Configuration Management
=======================

Centralized configuration management for the Network Intelligence Monitor.
Supports YAML files, environment variables, and runtime overrides.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
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

@dataclass
class APIConfig:
    """API server configuration"""
    host: str = '0.0.0.0'
    port: int = 5000
    debug: bool = False
    cors_enabled: bool = True

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

class Config:
    """Main configuration class"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self._config_data = {}
        
        # Initialize configuration sections
        self.monitoring = MonitoringConfig()
        self.ai = AIConfig()
        self.api = APIConfig()
        self.database = DatabaseConfig()
        self.mimir = MimirConfig()
        self.metrics = MetricsConfig()
        self.alerts = AlertsConfig()
        self.deployment = DeploymentConfig()
        
        self.load_config()
    
    def load_config(self):
        """Load configuration from file and environment variables"""
        
        # Load from YAML file if it exists
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
        
        # Update configuration objects
        self._update_config_objects()
        
        # Override with environment variables
        self._load_environment_overrides()
        
        # Validate configuration
        self._validate_config()
    
    def _update_config_objects(self):
        """Update configuration objects from loaded data"""
        
        # Update monitoring config
        monitoring_data = self._config_data.get('monitoring', {})
        for key, value in monitoring_data.items():
            if hasattr(self.monitoring, key):
                setattr(self.monitoring, key, value)
        
        # Update AI config
        ai_data = self._config_data.get('ai', {})
        for key, value in ai_data.items():
            if hasattr(self.ai, key):
                setattr(self.ai, key, value)
        
        # Update API config
        api_data = self._config_data.get('api', {})
        for key, value in api_data.items():
            if hasattr(self.api, key):
                setattr(self.api, key, value)
        
        # Update database config
        database_data = self._config_data.get('database', {})
        for key, value in database_data.items():
            if hasattr(self.database, key):
                setattr(self.database, key, value)
        
        # Update Mimir config
        mimir_data = self._config_data.get('mimir', {})
        for key, value in mimir_data.items():
            if hasattr(self.mimir, key):
                setattr(self.mimir, key, value)
        
        # Update metrics config
        metrics_data = self._config_data.get('metrics', {})
        for key, value in metrics_data.items():
            if hasattr(self.metrics, key):
                setattr(self.metrics, key, value)
        
        # Update alerts config
        alerts_data = self._config_data.get('alerts', {})
        for key, value in alerts_data.items():
            if hasattr(self.alerts, key):
                setattr(self.alerts, key, value)
        
        # Update deployment config
        deployment_data = self._config_data.get('deployment', {})
        for key, value in deployment_data.items():
            if hasattr(self.deployment, key):
                setattr(self.deployment, key, value)
    
    def _load_environment_overrides(self):
        """Load configuration overrides from environment variables"""
        
        env_mappings = {
            # Monitoring
            'MONITORING_INTERVAL': ('monitoring', 'interval', int),
            'MONITORING_TIMEOUT': ('monitoring', 'timeout', int),
            'MONITORING_TARGETS': ('monitoring', 'targets', lambda x: x.split(',')),
            
            # API
            'API_HOST': ('api', 'host', str),
            'API_PORT': ('api', 'port', int),
            'API_DEBUG': ('api', 'debug', lambda x: x.lower() == 'true'),
            
            # Database
            'DATABASE_PATH': ('database', 'path', str),
            'DATABASE_CLEANUP_DAYS': ('database', 'cleanup_days', int),
            
            # Mimir
            'MIMIR_ENDPOINT': ('mimir', 'mimir_url', str),
            'PROMETHEUS_ENDPOINT': ('mimir', 'prometheus_url', str),
            'MIMIR_TENANT_ID': ('mimir', 'tenant_id', str),
            
            # Metrics
            'METRICS_PORT': ('metrics', 'port', int),
            'METRICS_HOST': ('metrics', 'host', str),
            
            # Deployment
            'DEPLOYMENT_TYPE': ('deployment', 'edge_optimization', lambda x: x == 'edge'),
            'MAX_MEMORY_MB': ('deployment', 'max_memory_mb', int),
        }
        
        for env_var, (section, key, converter) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    converted_value = converter(value)
                    config_obj = getattr(self, section)
                    setattr(config_obj, key, converted_value)
                    logger.debug(f"Override {section}.{key} = {converted_value} from {env_var}")
                except Exception as e:
                    logger.warning(f"Failed to parse environment variable {env_var}={value}: {e}")
    
    def _validate_config(self):
        """Validate configuration values"""
        
        # Validate monitoring targets
        if not self.monitoring.targets:
            self.monitoring.targets = ['8.8.8.8']
            logger.warning("No monitoring targets specified, using default")
        
        # Validate intervals
        if self.monitoring.interval < 5:
            self.monitoring.interval = 5
            logger.warning("Monitoring interval too low, set to 5 seconds")
        
        if self.monitoring.timeout >= self.monitoring.interval:
            self.monitoring.timeout = max(5, self.monitoring.interval - 5)
            logger.warning(f"Timeout adjusted to {self.monitoring.timeout} seconds")
        
        # Validate paths
        for path_attr in ['model_dir']:
            path_value = getattr(self.ai, path_attr)
            Path(path_value).mkdir(parents=True, exist_ok=True)
        
        Path(self.database.path).parent.mkdir(parents=True, exist_ok=True)
        
        # Validate ports
        if not (1024 <= self.api.port <= 65535):
            self.api.port = 5000
            logger.warning("Invalid API port, using default 5000")
        
        if not (1024 <= self.metrics.port <= 65535):
            self.metrics.port = 8000
            logger.warning("Invalid metrics port, using default 8000")
        
        # Enable Mimir if URLs are provided
        if self.mimir.prometheus_url or self.mimir.mimir_url:
            self.mimir.enabled = True
        
        logger.info("Configuration validation completed")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation"""
        
        keys = key.split('.')
        value = self._config_data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Set configuration value using dot notation"""
        
        keys = key.split('.')
        config_dict = self._config_data
        
        for k in keys[:-1]:
            if k not in config_dict:
                config_dict[k] = {}
            config_dict = config_dict[k]
        
        config_dict[keys[-1]] = value
        
        # Re-update configuration objects
        self._update_config_objects()
    
    def save_config(self, path: Optional[str] = None):
        """Save current configuration to file"""
        
        save_path = Path(path) if path else self.config_path
        
        try:
            with open(save_path, 'w') as f:
                yaml.dump(self._config_data, f, default_flow_style=False, indent=2)
            logger.info(f"Configuration saved to {save_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration to {save_path}: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        
        return {
            'monitoring': {
                'targets': self.monitoring.targets,
                'interval': self.monitoring.interval,
                'timeout': self.monitoring.timeout,
                'enabled': self.monitoring.enabled,
                'enhanced_features': self.monitoring.enhanced_features
            },
            'ai': {
                'model_dir': self.ai.model_dir,
                'train_interval': self.ai.train_interval,
                'initial_epochs': self.ai.initial_epochs,
                'baseline_window': self.ai.baseline_window,
                'training_hours': self.ai.training_hours,
                'auto_train': self.ai.auto_train,
                'enable_quantization': self.ai.enable_quantization
            },
            'api': {
                'host': self.api.host,
                'port': self.api.port,
                'debug': self.api.debug,
                'cors_enabled': self.api.cors_enabled
            },
            'database': {
                'path': self.database.path,
                'cleanup_days': self.database.cleanup_days,
                'backup_enabled': self.database.backup_enabled,
                'backup_interval_hours': self.database.backup_interval_hours
            },
            'mimir': {
                'prometheus_url': self.mimir.prometheus_url,
                'mimir_url': self.mimir.mimir_url,
                'tenant_id': self.mimir.tenant_id,
                'enabled': self.mimir.enabled
            },
            'metrics': {
                'port': self.metrics.port,
                'host': self.metrics.host,
                'batch_size': self.metrics.batch_size,
                'enable_aggregation': self.metrics.enable_aggregation
            },
            'alerts': {
                'enabled': self.alerts.enabled,
                'webhook_url': self.alerts.webhook_url,
                'email_enabled': self.alerts.email_enabled,
                'smtp_server': self.alerts.smtp_server,
                'smtp_port': self.alerts.smtp_port,
                'email_recipients': self.alerts.email_recipients
            },
            'deployment': {
                'edge_optimization': self.deployment.edge_optimization,
                'quantize_models': self.deployment.quantize_models,
                'reduce_memory_usage': self.deployment.reduce_memory_usage,
                'max_memory_mb': self.deployment.max_memory_mb
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
                # Skip loopback and virtual interfaces
                if interface_name.startswith(('lo', 'docker', 'br-', 'veth')):
                    continue
                
                # Check if interface is up
                stats = psutil.net_if_stats().get(interface_name)
                if stats and stats.isup:
                    interfaces.append({
                        'name': interface_name,
                        'addresses': [addr.address for addr in addresses],
                        'family': [addr.family.name for addr in addresses]
                    })
            
            return interfaces
            
        except ImportError:
            logger.warning("psutil not available, cannot detect network interfaces")
            return []
        except Exception as e:
            logger.error(f"Error detecting network interfaces: {e}")
            return []

def create_default_config() -> Dict[str, Any]:
    """Create default configuration"""
    
    return {
        'logging': {
            'level': 'INFO',
            'file': 'data/logs/network_intelligence.log',
            'max_size_mb': 10,
            'backup_count': 5
        },
        'database': {
            'path': 'data/database/network_intelligence.db',
            'cleanup_days': 30,
            'backup_enabled': True,
            'backup_interval_hours': 24
        },
        'monitoring': {
            'targets': ['8.8.8.8', '1.1.1.1', 'google.com', 'github.com'],
            'interval': 30,
            'timeout': 10,
            'enabled': True,
            'enhanced_features': True
        },
        'ai': {
            'model_dir': 'data/models',
            'train_interval': 3600,
            'initial_epochs': 100,
            'baseline_window': 1000,
            'training_hours': 24,
            'auto_train': True,
            'enable_quantization': True
        },
        'api': {
            'host': '0.0.0.0',
            'port': 5000,
            'debug': False,
            'cors_enabled': True
        },
        'metrics': {
            'port': 8000,
            'host': '0.0.0.0',
            'batch_size': 10,
            'enable_aggregation': True
        },
        'mimir': {
            'prometheus_url': None,
            'mimir_url': None,
            'tenant_id': 'network-monitoring',
            'enabled': False
        },
        'alerts': {
            'enabled': True,
            'webhook_url': None,
            'email_enabled': False,
            'smtp_server': None,
            'smtp_port': 587,
            'email_recipients': []
        },
        'deployment': {
            'edge_optimization': False,
            'quantize_models': False,
            'reduce_memory_usage': False,
            'max_memory_mb': 512
        }
    }

def create_edge_config() -> Dict[str, Any]:
    """Create edge-optimized configuration"""
    
    config = create_default_config()
    
    # Edge optimizations
    config['deployment'].update({
        'edge_optimization': True,
        'quantize_models': True,
        'reduce_memory_usage': True,
        'max_memory_mb': 256
    })
    
    config['ai'].update({
        'train_interval': 7200,  # Less frequent training
        'initial_epochs': 50,    # Fewer epochs
        'baseline_window': 500   # Smaller window
    })
    
    config['monitoring'].update({
        'interval': 60,          # Less frequent monitoring
        'timeout': 15
    })
    
    config['database'].update({
        'cleanup_days': 7,       # Keep less data
        'backup_enabled': False  # Disable backups on edge
    })
    
    return config

#!/usr/bin/env python3
"""
Logging Utilities
================

Centralized logging configuration for the Network Intelligence Monitor.
Supports structured logging, multiple outputs, and performance monitoring.
"""

import logging
import logging.handlers
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import structlog

class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                          'filename', 'module', 'lineno', 'funcName', 'created',
                          'msecs', 'relativeCreated', 'thread', 'threadName',
                          'processName', 'process', 'exc_info', 'exc_text', 'stack_info']:
                log_entry[key] = value
        
        return json.dumps(log_entry)

class ColoredFormatter(logging.Formatter):
    """Colored console formatter"""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset_color = self.COLORS['RESET']
        
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        # Create colored log entry
        formatted = (
            f"{log_color}[{timestamp}] "
            f"{record.levelname:8s} "
            f"{record.name:20s} "
            f"{reset_color}"
            f"{record.getMessage()}"
        )
        
        # Add exception info if present
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"
        
        return formatted

class PerformanceLogger:
    """Performance monitoring logger"""
    
    def __init__(self, logger_name: str = "performance"):
        self.logger = logging.getLogger(logger_name)
        self.timers = {}
    
    def start_timer(self, operation: str):
        """Start timing an operation"""
        self.timers[operation] = time.time()
    
    def end_timer(self, operation: str, **kwargs):
        """End timing and log the duration"""
        if operation in self.timers:
            duration = time.time() - self.timers[operation]
            self.logger.info(
                f"Operation completed: {operation}",
                extra={
                    'operation': operation,
                    'duration_ms': duration * 1000,
                    **kwargs
                }
            )
            del self.timers[operation]
            return duration
        return None
    
    def log_metric(self, metric_name: str, value: float, **kwargs):
        """Log a performance metric"""
        self.logger.info(
            f"Metric: {metric_name} = {value}",
            extra={
                'metric_name': metric_name,
                'metric_value': value,
                'metric_type': 'performance',
                **kwargs
            }
        )

def setup_logging(config: Optional[Dict[str, Any]] = None):
    """Setup logging configuration"""
    
    if config is None:
        config = {
            'level': 'INFO',
            'file': 'data/logs/network_intelligence.log',
            'max_size_mb': 10,
            'backup_count': 5,
            'console_enabled': True,
            'json_format': False,
            'colored_console': True
        }
    
    # Get log level
    log_level = getattr(logging, config.get('level', 'INFO').upper())
    
    # Create logs directory
    log_file = config.get('file', 'data/logs/network_intelligence.log')
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # File handler with rotation
    if log_file:
        max_bytes = config.get('max_size_mb', 10) * 1024 * 1024
        backup_count = config.get('backup_count', 5)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        if config.get('json_format', False):
            file_handler.setFormatter(JSONFormatter())
        else:
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
        
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)
    
    # Console handler
    if config.get('console_enabled', True):
        console_handler = logging.StreamHandler(sys.stdout)
        
        if config.get('colored_console', True):
            console_handler.setFormatter(ColoredFormatter())
        else:
            console_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
        
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)
    
    # Set specific logger levels
    logger_configs = {
        'urllib3': logging.WARNING,
        'aiohttp': logging.WARNING,
        'matplotlib': logging.WARNING,
        'torch': logging.WARNING,
        'werkzeug': logging.WARNING
    }
    
    for logger_name, level in logger_configs.items():
        logging.getLogger(logger_name).setLevel(level)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info("Logging system initialized")
    logger.info(f"Log level: {log_level}")
    logger.info(f"Log file: {log_file}")

def setup_structured_logging():
    """Setup structured logging with structlog"""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer() if sys.stdout.isatty() else structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

class NetworkLogger:
    """Specialized logger for network operations"""
    
    def __init__(self, name: str = "network"):
        self.logger = logging.getLogger(name)
        self.performance = PerformanceLogger(f"{name}.performance")
    
    def log_connection_attempt(self, target: str, protocol: str, **kwargs):
        """Log connection attempt"""
        self.logger.info(
            f"Connecting to {target} via {protocol}",
            extra={
                'event_type': 'connection_attempt',
                'target': target,
                'protocol': protocol,
                **kwargs
            }
        )
    
    def log_connection_success(self, target: str, protocol: str, duration_ms: float, **kwargs):
        """Log successful connection"""
        self.logger.info(
            f"Connected to {target} via {protocol} in {duration_ms:.2f}ms",
            extra={
                'event_type': 'connection_success',
                'target': target,
                'protocol': protocol,
                'duration_ms': duration_ms,
                **kwargs
            }
        )
    
    def log_connection_failure(self, target: str, protocol: str, error: str, **kwargs):
        """Log connection failure"""
        self.logger.error(
            f"Failed to connect to {target} via {protocol}: {error}",
            extra={
                'event_type': 'connection_failure',
                'target': target,
                'protocol': protocol,
                'error': error,
                **kwargs
            }
        )
    
    def log_metrics_collected(self, target: str, metrics: Dict[str, Any]):
        """Log metrics collection"""
        self.logger.debug(
            f"Metrics collected for {target}",
            extra={
                'event_type': 'metrics_collected',
                'target': target,
                'metric_count': len(metrics),
                'metrics': metrics
            }
        )
    
    def log_anomaly_detected(self, target: str, anomaly_score: float, confidence: float, **kwargs):
        """Log anomaly detection"""
        self.logger.warning(
            f"Anomaly detected for {target}: score={anomaly_score:.3f}, confidence={confidence:.3f}",
            extra={
                'event_type': 'anomaly_detected',
                'target': target,
                'anomaly_score': anomaly_score,
                'confidence': confidence,
                **kwargs
            }
        )

class AILogger:
    """Specialized logger for AI/ML operations"""
    
    def __init__(self, name: str = "ai"):
        self.logger = logging.getLogger(name)
        self.performance = PerformanceLogger(f"{name}.performance")
    
    def log_training_start(self, model_type: str, samples: int, **kwargs):
        """Log training start"""
        self.logger.info(
            f"Starting {model_type} training with {samples} samples",
            extra={
                'event_type': 'training_start',
                'model_type': model_type,
                'training_samples': samples,
                **kwargs
            }
        )
    
    def log_training_complete(self, model_type: str, duration_ms: float, 
                             performance_metrics: Dict[str, float], **kwargs):
        """Log training completion"""
        self.logger.info(
            f"Training completed for {model_type} in {duration_ms:.2f}ms",
            extra={
                'event_type': 'training_complete',
                'model_type': model_type,
                'duration_ms': duration_ms,
                'performance_metrics': performance_metrics,
                **kwargs
            }
        )
    
    def log_inference(self, model_type: str, inference_time_ms: float, 
                     result: Dict[str, Any], **kwargs):
        """Log inference operation"""
        self.logger.debug(
            f"Inference completed for {model_type} in {inference_time_ms:.2f}ms",
            extra={
                'event_type': 'inference',
                'model_type': model_type,
                'inference_time_ms': inference_time_ms,
                'result': result,
                **kwargs
            }
        )
    
    def log_model_saved(self, model_type: str, file_path: str, file_size_mb: float):
        """Log model save operation"""
        self.logger.info(
            f"Model {model_type} saved to {file_path} ({file_size_mb:.2f}MB)",
            extra={
                'event_type': 'model_saved',
                'model_type': model_type,
                'file_path': file_path,
                'file_size_mb': file_size_mb
            }
        )
    
    def log_model_loaded(self, model_type: str, file_path: str):
        """Log model load operation"""
        self.logger.info(
            f"Model {model_type} loaded from {file_path}",
            extra={
                'event_type': 'model_loaded',
                'model_type': model_type,
                'file_path': file_path
            }
        )

class DatabaseLogger:
    """Specialized logger for database operations"""
    
    def __init__(self, name: str = "database"):
        self.logger = logging.getLogger(name)
        self.performance = PerformanceLogger(f"{name}.performance")
    
    def log_query(self, query_type: str, table: str, duration_ms: float, 
                  rows_affected: int = None, **kwargs):
        """Log database query"""
        message = f"{query_type} on {table} completed in {duration_ms:.2f}ms"
        if rows_affected is not None:
            message += f" ({rows_affected} rows)"
        
        self.logger.debug(
            message,
            extra={
                'event_type': 'database_query',
                'query_type': query_type,
                'table': table,
                'duration_ms': duration_ms,
                'rows_affected': rows_affected,
                **kwargs
            }
        )
    
    def log_cleanup(self, tables_cleaned: Dict[str, int], total_deleted: int):
        """Log database cleanup operation"""
        self.logger.info(
            f"Database cleanup completed: {total_deleted} records deleted",
            extra={
                'event_type': 'database_cleanup',
                'tables_cleaned': tables_cleaned,
                'total_deleted': total_deleted
            }
        )
    
    def log_backup(self, backup_path: str, success: bool, duration_ms: float = None):
        """Log database backup operation"""
        if success:
            message = f"Database backup created: {backup_path}"
            if duration_ms:
                message += f" in {duration_ms:.2f}ms"
            self.logger.info(
                message,
                extra={
                    'event_type': 'database_backup',
                    'backup_path': backup_path,
                    'success': True,
                    'duration_ms': duration_ms
                }
            )
        else:
            self.logger.error(
                f"Database backup failed: {backup_path}",
                extra={
                    'event_type': 'database_backup',
                    'backup_path': backup_path,
                    'success': False
                }
            )

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)

def get_network_logger() -> NetworkLogger:
    """Get network-specific logger"""
    return NetworkLogger()

def get_ai_logger() -> AILogger:
    """Get AI-specific logger"""
    return AILogger()

def get_database_logger() -> DatabaseLogger:
    """Get database-specific logger"""
    return DatabaseLogger()

def get_performance_logger(name: str = "performance") -> PerformanceLogger:
    """Get performance logger"""
    return PerformanceLogger(name)

# Context managers for performance logging
class timer:
    """Context manager for timing operations"""
    
    def __init__(self, operation: str, logger: Optional[logging.Logger] = None):
        self.operation = operation
        self.logger = logger or logging.getLogger(__name__)
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.logger.info(
            f"Operation '{self.operation}' completed in {duration*1000:.2f}ms",
            extra={
                'operation': self.operation,
                'duration_ms': duration * 1000,
                'success': exc_type is None
            }
        )

# Log filtering for sensitive data
class SensitiveDataFilter(logging.Filter):
    """Filter to remove sensitive data from logs"""
    
    SENSITIVE_PATTERNS = [
        'password', 'token', 'secret', 'key', 'auth'
    ]
    
    def filter(self, record):
        # Simple redaction of sensitive fields
        if hasattr(record, 'args') and record.args:
            record.args = self._redact_sensitive(record.args)
        
        if hasattr(record, 'msg'):
            record.msg = self._redact_sensitive_string(record.msg)
        
        return True
    
    def _redact_sensitive(self, data):
        """Redact sensitive data from log arguments"""
        if isinstance(data, dict):
            return {
                k: '***REDACTED***' if any(pattern in k.lower() for pattern in self.SENSITIVE_PATTERNS) else v
                for k, v in data.items()
            }
        elif isinstance(data, (list, tuple)):
            return [self._redact_sensitive(item) for item in data]
        return data
    
    def _redact_sensitive_string(self, text):
        """Redact sensitive data from log messages"""
        if isinstance(text, str):
            for pattern in self.SENSITIVE_PATTERNS:
                if pattern in text.lower():
                    # Simple redaction - in production, use regex
                    import re
                    text = re.sub(f'{pattern}[=:]\\s*\\S+', f'{pattern}=***REDACTED***', text, flags=re.IGNORECASE)
        return text

def add_sensitive_data_filter():
    """Add sensitive data filter to all loggers"""
    filter_instance = SensitiveDataFilter()
    
    # Add to root logger
    root_logger = logging.getLogger()
    root_logger.addFilter(filter_instance)
    
    logging.getLogger(__name__).info("Sensitive data filter added to logging system")

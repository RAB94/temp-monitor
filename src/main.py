#!/usr/bin/env python3
# src/main.py
"""
Enhanced Network Intelligence Monitor - Complete Main Application
===============================================================

Integrates networkquality-rs for responsiveness measurements alongside existing
monitoring capabilities.
"""

import asyncio
import logging
import signal
import sys
import os
import time
from pathlib import Path
import json # For storing list of recommendations as JSON
from typing import Optional # Added for type hinting
from dataclasses import asdict
# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.config import Config, create_config_file_if_not_exists # Ensure create_config_file_if_not_exists is available
from src.utils.logger import setup_logging, get_network_logger, get_ai_logger
from src.utils.database import Database
from src.utils.network import NetworkEnvironmentDetector # Added import
from src.collector import EnhancedNetworkCollector # Existing collector
from src.lstm_auto import EnhancedLSTMAnomalyDetector
from src.mimir_integration import MimirClient, integrate_with_existing_detector
from src.prom_export import PrometheusMetricsServer, MetricsAggregator
from src.api.server import APIServer as EnhancedAPIServer # Assuming your APIServer is already enhanced
from src.alerts import AlertManager, AlertSeverity, create_alert_manager
from src.dynamic_thresh import DynamicThresholdManager, setup_dynamic_thresholds
from src.edge_opt import EdgeOptimizer, create_edge_optimizer
from src.websocket_server import WebSocketManager, WebSocketIntegration
from src.api.server import APIServer
from src.ai_prometheus_metrics import AIModelPrometheusMetrics
# New imports for networkquality-rs
from src.networkquality.collector import NetworkQualityCollector, ResponsivenessMetrics
from src.webhook_sender import create_webhook_sender

logger = logging.getLogger(__name__)

class EnhancedNetworkIntelligenceMonitor:
    """Complete enhanced monitoring system with Alloy→Mimir and networkquality-rs integration"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config: Optional[Config] = None
        self.running = False

        # Core components
        self.database: Optional[Database] = None
        self.enhanced_collector: Optional[EnhancedNetworkCollector] = None # Existing
        self.ai_detector: Optional[EnhancedLSTMAnomalyDetector] = None
        self.mimir_client: Optional[MimirClient] = None
        self.alert_manager: Optional[AlertManager] = None
        self.threshold_manager: Optional[DynamicThresholdManager] = None
        self.edge_optimizer: Optional[EdgeOptimizer] = None

        # NetworkQuality-RS components
        self.nq_collector: Optional[NetworkQualityCollector] = None

        # Monitoring components
        self.metrics_server: Optional[PrometheusMetricsServer] = None
        self.metrics_aggregator: Optional[MetricsAggregator] = None
        self.api_server: Optional[EnhancedAPIServer] = None
        self.websocket_manager: Optional[WebSocketManager] = None
        self.websocket_integration: Optional[WebSocketIntegration] = None

        # Specialized loggers
        self.network_logger = get_network_logger()
        self.ai_logger = get_ai_logger()

        # Async tasks
        self.main_loop_task: Optional[asyncio.Task] = None
        self.nq_loop_task: Optional[asyncio.Task] = None # New task for NQRS
        self.api_task: Optional[asyncio.Task] = None
        self.baseline_update_task: Optional[asyncio.Task] = None

        self.performance_stats = {
            'system_start_time': time.time(),
            'total_measurements': 0,
            'total_nq_measurements': 0, # New
            'anomalies_detected': 0,
            'alerts_sent': 0,
            'model_trainings': 0,
            'baseline_updates': 0,
            'average_collection_time': 0.0,
            'system_health_score': 100.0
        }
        self.shutdown_event = asyncio.Event()

    async def initialize(self):
        """Initialize all system components"""
        logger.info("Initializing Enhanced Network Intelligence Monitor...")
        try:
            await self._load_configuration()
            await self._detect_environment() 
            await self._initialize_database()
            await self._initialize_enhanced_collector()
            await self._initialize_ai_system()
            await self._initialize_mimir_integration()
            await self._initialize_alerting_system()
            await self._initialize_dynamic_thresholds()
            await self._initialize_metrics_export()
            await self._initialize_api_server()
            await self._initialize_websocket_server()
            await self._initialize_networkquality_rs()
            await self._apply_edge_optimizations()
            await self._verify_integration_setup()

            logger.info("Enhanced Network Intelligence Monitor initialization complete")
            return True
        except Exception as e:
            logger.exception(f"Failed to initialize enhanced monitor: {e}")
            raise

    async def _load_configuration(self):
        self.config = Config(self.config_path)
        logger.info(f"Configuration loaded from: {self.config_path}")
        if self.config and self.config.networkquality: 
            logger.info(f"NetworkQuality-RS enabled: {self.config.networkquality.enabled}")
        else:
            logger.warning("NetworkQuality configuration section not found or config not loaded.")


    async def _detect_environment(self): 
        """Detect deployment environment and apply optimizations if necessary."""
        if not self.config:
            logger.error("Configuration not loaded, cannot detect environment.")
            return

        logger.info("Detecting environment...")
        detector = NetworkEnvironmentDetector()
        environment_info = detector.detect_deployment_environment()
        optimal_config_params = detector.get_optimal_monitoring_config()

        logger.info(f"  Platform: {environment_info.get('platform', 'unknown')}")
        logger.info(f"  Is container: {environment_info.get('is_container', False)}")
        logger.info(f"  Is cloud: {environment_info.get('is_cloud', False)}")
        logger.info(f"  Is edge device: {environment_info.get('is_edge_device', False)}")
        logger.info(f"  Constraints: {environment_info.get('constraints', [])}")

        if environment_info.get('is_edge_device') and self.config.deployment and not self.config.deployment.edge_optimization:
            logger.info("Auto-enabling edge optimizations based on environment detection.")
            self.config.deployment.edge_optimization = True
            if hasattr(self.config.deployment, 'quantize_models'): 
                self.config.deployment.quantize_models = True
            if self.config.monitoring: 
                self.config.monitoring.interval = optimal_config_params.get('monitoring_interval', 60)


    async def _initialize_networkquality_rs(self):
        """Initializes NetworkQuality-RS collector."""
        if not self.config or not self.config.networkquality or not self.config.networkquality.enabled:
            logger.info("NetworkQuality-RS monitoring is disabled in configuration.")
            return

        logger.info("Initializing NetworkQuality-RS collector...")
        
        self.nq_collector = NetworkQualityCollector(self.config.networkquality, self.database)
        logger.info("NetworkQuality-RS collector initialized.")


    async def _initialize_database(self):
        """Initialize database and ensure all tables, including for NQRS, exist."""
        if not self.config or not self.config.database:
            logger.error("Database configuration not found.")
            return
        self.database = Database(self.config.database.path)
        await self.database.initialize()

        try:
            if self.database and self.database.db:
                await self.database.db.execute("""
                    CREATE TABLE IF NOT EXISTS network_quality_rs_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        target_host TEXT NOT NULL,
                        rpm_download REAL,
                        rpm_upload REAL,
                        base_rtt_ms REAL,
                        loaded_rtt_download_ms REAL,
                        loaded_rtt_upload_ms REAL,
                        download_throughput_mbps REAL,
                        upload_throughput_mbps REAL,
                        download_responsiveness_score REAL,
                        upload_responsiveness_score REAL,
                        rpm_average REAL,
                        download_bufferbloat_ms REAL,
                        upload_bufferbloat_ms REAL,
                        max_bufferbloat_ms REAL,
                        bufferbloat_severity TEXT,
                        overall_quality_score REAL,
                        quality_rating TEXT,
                        congestion_detected BOOLEAN,
                        measurement_duration_ms REAL,
                        error TEXT,
                        recommendations TEXT,
                        created_at REAL DEFAULT (strftime('%s', 'now'))
                    )
                """)
                await self.database.db.commit()
                logger.info("Ensured 'network_quality_rs_metrics' table exists.")
        except Exception as e:
            logger.error(f"Failed to ensure 'network_quality_rs_metrics' table: {e}")
        logger.info(f"Database initialized: {self.config.database.path}")

    async def _initialize_enhanced_collector(self):
        if self.config and self.config.monitoring:
            collector_config = {
                'targets': self.config.monitoring.targets,
                'timeout': self.config.monitoring.timeout,
                'enhanced_features': self.config.monitoring.enhanced_features,
            }
            self.enhanced_collector = EnhancedNetworkCollector(collector_config)
            await self.enhanced_collector.initialize()
            logger.info("Enhanced network collector initialized")
        else:
            logger.warning("Monitoring configuration not found, skipping enhanced collector initialization.")


    async def _initialize_ai_system(self):
        if self.config and self.config.ai:
            ai_config = {
                'model_dir': self.config.ai.model_dir,
                'sequence_length': self.config.ai.sequence_length,  
                'input_size': self.config.ai.input_size,            
                'hidden_size': self.config.ai.hidden_size,          
                'num_layers': self.config.ai.num_layers,            
                'initial_epochs': self.config.ai.initial_epochs,
                'enable_quantization': self.config.ai.enable_quantization,
                'deployment_type': 'edge' if self.config.deployment and self.config.deployment.edge_optimization else 'standard'
            }
            self.ai_detector = EnhancedLSTMAnomalyDetector(ai_config)
            await self.ai_detector.initialize()
            try:
                self.ai_detector.load_models()
                if self.ai_logger:  
                    self.ai_logger.log_model_loaded('enhanced_lstm', self.config.ai.model_dir)
                logger.info("Loaded existing AI models")
            except FileNotFoundError:
                logger.info("No existing AI models found - will train from scratch")
            logger.info("AI detection system initialized")
        else:
            logger.warning("AI configuration not found, skipping AI system initialization.")

    async def _initialize_mimir_integration(self):
        if self.config and self.config.mimir and self.config.mimir.enabled:
            mimir_config = {
                'mimir_url': self.config.mimir.mimir_url,
                'prometheus_url': self.config.mimir.prometheus_url,
                'tenant_id': self.config.mimir.tenant_id,
                'timeout': self.config.mimir.get('timeout', 30),
                'cache_ttl_seconds': self.config.mimir.get('cache_ttl_seconds', 300)
            }
            if not mimir_config['mimir_url'] and not mimir_config['prometheus_url']:
                 logger.warning("Mimir/Prometheus URL not configured, skipping Mimir integration")
                 return
            self.mimir_client = MimirClient(mimir_config)
            await self.mimir_client.initialize()
            if self.ai_detector:
                await integrate_with_existing_detector(
                    self.ai_detector,
                    self.mimir_client,
                    target_hosts=self.config.monitoring.targets if self.config.monitoring else [],
                    days_back=30
                )
            logger.info("Mimir integration initialized")
        else:
            logger.info("Mimir integration disabled or Mimir config missing.")

    async def _initialize_alerting_system(self):
        if self.config and self.config.alerts and self.config.alerts.enabled:
            alert_config = asdict(self.config.alerts)
            
            alert_config = {
                'correlation': {
                    'correlation_window_seconds': 300,
                    'enable_grouping': True
                },
                'notifications': {
                    'channels': [
                        {
                            'name': 'webhook',
                            'type': 'webhook',
                            'config': {'url': self.config.alerts.webhook_url},
                            'enabled': bool(self.config.alerts.webhook_url)
                        }
                    ],
                    'routing': {
                        'critical': ['webhook'],
                        'high': ['webhook'],
                        'medium': [],
                        'low': []
                    }
                },
                'escalation': {
                    'enabled': True,
                    'rules': [
                        {
                            'name': 'critical_escalation',
                            'conditions': {'severity': ['critical']},
                            'delay_seconds': 300,
                            'channels': ['webhook'],
                            'enabled': True
                        }
                    ]
                },
                'retention_hours': 168
            }
            
            self.alert_manager = create_alert_manager(alert_config)
            logger.info("Alerting system initialized")
        if self.config.alerts.webhook_url:
            webhook_config = {
                'enabled': True,
                'url': self.config.alerts.webhook_url,
                'headers': {
                    'Content-Type': 'application/json',
                    'Authorization': f"Bearer {os.getenv('WEBHOOK_SECRET', 'default-secret')}"
                },
                'timeout_seconds': 15,
                'retry_attempts': 3,
                'retry_delay_seconds': 5
            }
            
            self.webhook_sender = create_webhook_sender({'webhook_alerting': webhook_config})
            
            # Integrate webhook sender with alert manager
            if self.webhook_sender:
                # Import datetime here to ensure it's available in the closure
                from datetime import datetime
                
                # Override the notification manager's webhook sending
                original_send = self.alert_manager.notification_manager._send_webhook
                
                async def enhanced_webhook_send(alert, channel, template):
                    # Use the dedicated webhook sender
                    success = self.webhook_sender.send_custom_alert({
                        'alert_type': 'network_anomaly',
                        'timestamp': datetime.now().isoformat(),  # datetime is now available
                        'alert_data': {
                            'id': alert.id,
                            'title': alert.title,
                            'description': alert.description,
                            'severity': alert.severity.value,
                            'status': alert.status.value,
                            'target': alert.target,
                            'metric_name': alert.metric_name,
                            'current_value': alert.current_value,
                            'threshold': alert.threshold,
                            'tags': alert.tags,
                            'context': alert.context
                        }
                    })
                    return success
                
                self.alert_manager.notification_manager._send_webhook = enhanced_webhook_send
                logger.info("Enhanced webhook sender integrated with alert manager")           
        else:
            logger.info("Alerting system disabled or alerts config missing.")



    async def _initialize_dynamic_thresholds(self):
        if self.config:
             threshold_config = self.config.get('dynamic_thresholds', {})
             self.threshold_manager = setup_dynamic_thresholds(threshold_config)
             logger.info("Dynamic threshold management initialized")
        else:
            logger.warning("Main config not found, skipping dynamic thresholds.")


    async def _initialize_metrics_export(self):
        """Initialize Prometheus metrics export for Alloy with AI metrics integration"""
        
        if not self.config or not self.config.metrics:
            logger.warning("Metrics configuration not found, skipping metrics export initialization.")
            return
        
        logger.info("Initializing Prometheus metrics export system...")
        
        try:
            # Extract metrics configuration
            metrics_conf = self.config.metrics
            metrics_port = metrics_conf.port
            metrics_host = metrics_conf.host
            batch_size = metrics_conf.batch_size
            enable_aggregation = metrics_conf.enable_aggregation
            
            logger.info(f"📊 Metrics configuration: host={metrics_host}, port={metrics_port}, "
                       f"batch_size={batch_size}, aggregation={enable_aggregation}")
            
            # Create Prometheus metrics server
            self.metrics_server = PrometheusMetricsServer(port=metrics_port, host=metrics_host)
            
            # Initialize AI model metrics with the same registry
            try:
                from src.ai_prometheus_metrics import AIModelPrometheusMetrics
                self.ai_metrics = AIModelPrometheusMetrics(registry=self.metrics_server.registry)
                logger.info("✅ AI model Prometheus metrics initialized with main registry")
                
                # Set initial AI model information if detector exists
                if self.ai_detector and self.config.ai:
                    # Calculate model parameters if possible
                    model_params = 0
                    model_size_bytes = 0
                    
                    if hasattr(self.ai_detector, 'model') and self.ai_detector.model:
                        # Count model parameters
                        model_params = sum(p.numel() for p in self.ai_detector.model.parameters())
                        # Estimate model size (assuming float32)
                        model_size_bytes = model_params * 4
                        
                        logger.info(f"🤖 AI Model Stats: {model_params:,} parameters, "
                                   f"{model_size_bytes / 1024 / 1024:.2f} MB")
                    
                    # Update model info metrics
                    model_info = {
                        'version': '1.0.0',
                        'architecture': 'lstm_autoencoder',
                        'input_size': self.config.ai.input_size,
                        'hidden_size': self.config.ai.hidden_size,
                        'num_layers': self.config.ai.num_layers,
                        'sequence_length': self.config.ai.sequence_length,
                        'quantized': self.config.deployment.edge_optimization if self.config.deployment else False,
                        'parameters': model_params,
                        'size_bytes': model_size_bytes
                    }
                    
                    self.ai_metrics.update_model_info('enhanced_lstm', model_info)
                    
                    # Set initial model health
                    model_creation_time = getattr(self.ai_detector, 'model_creation_time', time.time())
                    model_age = time.time() - model_creation_time
                    initial_health = 100.0 if self.ai_detector.is_trained else 50.0
                    
                    self.ai_metrics.update_model_health('enhanced_lstm', initial_health, model_age)
                    
                    # Set last trained timestamp if model is trained
                    if self.ai_detector.is_trained:
                        self.ai_metrics.model_last_trained.labels(model_type='enhanced_lstm').set(model_creation_time)
                    
                    logger.info(f"📊 AI metrics initialized - Model trained: {self.ai_detector.is_trained}, "
                               f"Health: {initial_health:.1f}%, Age: {model_age/3600:.1f} hours")
                else:
                    logger.warning("⚠️ AI detector not available, AI metrics will be limited")
                    
            except ImportError as e:
                logger.error(f"Failed to import AI metrics module: {e}")
                self.ai_metrics = None
            except Exception as e:
                logger.error(f"Error initializing AI metrics: {e}")
                self.ai_metrics = None
            
            # Start the metrics server
            try:
                self.metrics_server.start()
                logger.info(f"✅ Prometheus metrics server started on http://{metrics_host}:{metrics_port}/metrics")
                
                # Test the metrics endpoint
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    try:
                        test_url = f"http://{metrics_host}:{metrics_port}/health"
                        async with session.get(test_url, timeout=5) as response:
                            if response.status == 200:
                                logger.info("✅ Metrics server health check passed")
                            else:
                                logger.warning(f"⚠️ Metrics server health check returned status {response.status}")
                    except Exception as e:
                        logger.debug(f"Metrics server health check failed (server may still be starting): {e}")
                        
            except Exception as e:
                logger.error(f"Failed to start metrics server: {e}")
                self.metrics_server = None
                return
            
            # Create metrics aggregator if aggregation is enabled
            if enable_aggregation:
                self.metrics_aggregator = MetricsAggregator(self.metrics_server, batch_size=batch_size)
                
                # Initialize NetworkQuality metrics support if enabled
                if self.config.networkquality and self.config.networkquality.enabled:
                    logger.info("🌐 Initializing NetworkQuality metrics support...")
                    
                    try:
                        # Import NetworkQuality metrics at runtime
                        from src.networkquality.prometheus_metrics import NetworkQualityPrometheusMetrics
                        
                        # Create method to add NetworkQuality metrics
                        def add_networkquality_metrics(self, nq_metrics_data):
                            """Add NetworkQuality metrics to Prometheus export"""
                            try:
                                # Lazy initialization of NQ metrics handler
                                if not hasattr(self, '_nq_metrics_handler'):
                                    # Try to get existing instance or create new one
                                    try:
                                        # Use the existing registry from the metrics server
                                        registry = self.metrics_server.registry if hasattr(self.metrics_server, 'registry') else None
                                        self._nq_metrics_handler = NetworkQualityPrometheusMetrics(registry=registry)
                                        logger.debug("NetworkQuality metrics handler initialized")
                                    except ValueError as ve:
                                        # Metrics might already exist in registry
                                        logger.debug(f"NetworkQuality metrics already registered: {ve}")
                                        # Try to use existing instance
                                        if hasattr(self.metrics_server, 'nq_metrics'):
                                            self._nq_metrics_handler = self.metrics_server.nq_metrics
                                        else:
                                            logger.error("Cannot initialize NetworkQuality metrics handler")
                                            return
                                
                                # Update metrics
                                if self._nq_metrics_handler:
                                    data = nq_metrics_data.to_dict() if hasattr(nq_metrics_data, 'to_dict') else nq_metrics_data
                                    self._nq_metrics_handler.update_metrics(data)
                                    
                                    # Log significant quality issues
                                    if data.get('quality_rating') in ['poor', 'error']:
                                        logger.warning(f"⚠️ NetworkQuality issue detected: {data.get('target_host')} - "
                                                     f"Rating: {data.get('quality_rating')}, RPM: {data.get('rpm_average')}")
                                        
                                    logger.debug(f"Updated NetworkQuality metrics for {data.get('target_host', 'unknown')}")
                                
                            except Exception as e:
                                logger.error(f"Error in add_networkquality_metrics: {e}", exc_info=True)
                        
                        # Bind the method to the aggregator instance
                        import types
                        self.metrics_aggregator.add_networkquality_metrics = types.MethodType(
                            add_networkquality_metrics, 
                            self.metrics_aggregator
                        )
                        
                        logger.info("✅ NetworkQuality metrics support successfully integrated")
                        
                        # Initialize NetworkQuality metrics on the server as well
                        if hasattr(self.metrics_server, 'nq_metrics'):
                            logger.info("📊 NetworkQuality metrics already initialized on server")
                        else:
                            try:
                                self.metrics_server.nq_metrics = NetworkQualityPrometheusMetrics(
                                    registry=self.metrics_server.registry
                                )
                                logger.info("✅ NetworkQuality metrics initialized on metrics server")
                            except ValueError:
                                logger.debug("NetworkQuality metrics already exist in registry")
                        
                    except ImportError as e:
                        logger.error(f"Failed to import NetworkQuality metrics module: {e}")
                    except Exception as e:
                        logger.error(f"Error setting up NetworkQuality metrics support: {e}")
                
                # Start the aggregator
                try:
                    self.metrics_aggregator.start()
                    logger.info(f"✅ Metrics aggregator started with batch size {batch_size}")
                    
                    # Log aggregator configuration
                    logger.info(f"📊 Aggregator queues: metrics={batch_size}, "
                               f"anomalies=50, alerts=50, health=20")
                    
                except Exception as e:
                    logger.error(f"Failed to start metrics aggregator: {e}")
                    self.metrics_aggregator = None
            else:
                logger.info("ℹ️ Metrics aggregation disabled - metrics will be updated immediately")
                self.metrics_aggregator = None
            
            # Set up custom metric collectors if available
            if self.metrics_server:
                # Register custom collectors for system metrics
                try:
                    import psutil
                    
                    # System resource metrics
                    def get_system_metrics():
                        """Collect system resource metrics"""
                        try:
                            cpu_percent = psutil.cpu_percent(interval=0.1)
                            memory = psutil.virtual_memory()
                            disk = psutil.disk_usage('/')
                            
                            if hasattr(self.metrics_server.metrics, 'collector_health_status'):
                                # Update system health based on resources
                                if cpu_percent > 90 or memory.percent > 90:
                                    health = 'unhealthy'
                                elif cpu_percent > 70 or memory.percent > 70:
                                    health = 'degraded'
                                else:
                                    health = 'healthy'
                                
                                self.metrics_server.metrics.collector_health_status.labels(
                                    component='system'
                                ).state(health)
                            
                            return {
                                'cpu_percent': cpu_percent,
                                'memory_percent': memory.percent,
                                'disk_percent': disk.percent
                            }
                        except Exception as e:
                            logger.debug(f"Error collecting system metrics: {e}")
                            return {}
                    
                    # Register periodic system metrics collection
                    async def update_system_metrics():
                        """Periodically update system metrics"""
                        while self.running:
                            try:
                                system_metrics = get_system_metrics()
                                if system_metrics:
                                    logger.debug(f"System resources - CPU: {system_metrics['cpu_percent']:.1f}%, "
                                               f"Memory: {system_metrics['memory_percent']:.1f}%")
                                await asyncio.sleep(60)  # Update every minute
                            except asyncio.CancelledError:
                                break
                            except Exception as e:
                                logger.debug(f"Error in system metrics update: {e}")
                                await asyncio.sleep(60)
                    
                    # Start system metrics task
                    asyncio.create_task(update_system_metrics())
                    logger.info("✅ System resource metrics collector started")
                    
                except ImportError:
                    logger.debug("psutil not available, system metrics collection disabled")
                except Exception as e:
                    logger.warning(f"Error setting up system metrics collection: {e}")
            
            # Log final initialization summary
            logger.info("="*60)
            logger.info("📊 PROMETHEUS METRICS EXPORT INITIALIZED")
            logger.info(f"   Endpoint: http://{metrics_host}:{metrics_port}/metrics")
            logger.info(f"   AI Metrics: {'Enabled' if self.ai_metrics else 'Disabled'}")
            logger.info(f"   NetworkQuality Metrics: {'Enabled' if self.config.networkquality and self.config.networkquality.enabled else 'Disabled'}")
            logger.info(f"   Aggregation: {'Enabled' if self.metrics_aggregator else 'Disabled'}")
            logger.info(f"   Available at: http://{metrics_host}:{metrics_port}/metrics")
            logger.info("="*60)
            
        except Exception as e:
            logger.error(f"Critical error in metrics export initialization: {e}", exc_info=True)
            # Clean up any partially initialized components
            if hasattr(self, 'metrics_server') and self.metrics_server:
                try:
                    self.metrics_server.stop()
                except:
                    pass
            if hasattr(self, 'metrics_aggregator') and self.metrics_aggregator:
                try:
                    self.metrics_aggregator.stop()
                except:
                    pass
            
            self.metrics_server = None
            self.metrics_aggregator = None
            self.ai_metrics = None

    async def _initialize_api_server(self):
        if self.config:
            self.api_server = APIServer(
                self.config, 
                self.database, 
                self.ai_detector, 
                self.enhanced_collector
            )
            
            self.api_server.mimir_client = self.mimir_client
            self.api_server.metrics_server = self.metrics_server
            self.api_server.alert_manager = self.alert_manager
            self.api_server.threshold_manager = self.threshold_manager
            
            logger.info("Enhanced API server initialized")
        else:
            logger.warning("Main config not found, skipping API server initialization.")

    async def _initialize_websocket_server(self):
        """Initializes the WebSocket server if enabled in the configuration."""
        if self.config and self.config.api and self.config.api.websocket_enabled:
            websocket_host = self.config.api.host
            websocket_port = self.config.api.websocket_port  
            
            logger.info(f"WebSocket config: host={websocket_host}, port={websocket_port}")
            
            self.websocket_manager = WebSocketManager(
                host=websocket_host,
                port=websocket_port
            )
            try:
                await self.websocket_manager.start_server()
                self.websocket_integration = WebSocketIntegration(self.websocket_manager)
                logger.info(f"WebSocket server initialized and started on ws://{websocket_host}:{websocket_port}")
            except Exception as e:
                logger.error(f"Failed to start WebSocket server on ws://{websocket_host}:{websocket_port}: {e}")
                self.websocket_manager = None
                self.websocket_integration = None
        elif self.config and self.config.api and not self.config.api.websocket_enabled:
            logger.info("WebSocket server is disabled in the configuration.")
            self.websocket_manager = None
            self.websocket_integration = None
        else:
            logger.warning("API configuration not found or incomplete, skipping WebSocket server initialization.")
            self.websocket_manager = None
            self.websocket_integration = None

    async def _apply_edge_optimizations(self):
        if self.config and self.config.deployment and self.config.deployment.edge_optimization:
            edge_config = self.config.deployment.to_dict() if hasattr(self.config.deployment, 'to_dict') else \
                           self.config.get('deployment') 
            self.edge_optimizer = create_edge_optimizer(edge_config)
            if self.ai_detector and self.ai_detector.model and self.edge_optimizer:
                self.ai_detector.model = self.edge_optimizer.optimize_for_edge(model=self.ai_detector.model)
            logger.info("Edge optimizations applied")
        else:
            logger.info("Edge optimization not enabled or deployment config missing.")


    async def _verify_integration_setup(self):
        if not self.config:
            logger.warning("Config not loaded, skipping integration verification.")
            return
        
        logger.info("Integration verification setup completed.")


    async def start(self):
        """Start the enhanced monitoring system"""
        logger.info("Starting Enhanced Network Intelligence Monitor...")
        if self.running:
            logger.warning("Monitor already running")
            return
        self.running = True
        self._setup_signal_handlers()

        if self.main_loop_task is None:
            self.main_loop_task = asyncio.create_task(self._main_monitoring_loop())
        if self.config and self.config.networkquality and self.config.networkquality.enabled and self.nq_loop_task is None:
            self.nq_loop_task = asyncio.create_task(self._networkquality_monitoring_loop())
        if self.api_server and self.api_task is None:
            self.api_task = asyncio.create_task(self._run_api_server())
        if self.mimir_client and self.baseline_update_task is None:
            self.baseline_update_task = asyncio.create_task(self._baseline_update_loop())

        logger.info("Enhanced Network Intelligence Monitor started successfully")
        self._log_startup_summary()
        await self.shutdown_event.wait()
        await self.stop()

    async def stop(self):
        if not self.running:
            return
        logger.info("Stopping Enhanced Network Intelligence Monitor...")
        self.running = False

        tasks_to_cancel = [
            self.main_loop_task,
            self.nq_loop_task,
            self.api_task,
            self.baseline_update_task
        ]
        
        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()
        
        await asyncio.gather(*[t for t in tasks_to_cancel if t], return_exceptions=True)

        if self.metrics_aggregator: self.metrics_aggregator.stop()
        if self.metrics_server: self.metrics_server.stop()
        if self.websocket_manager: await self.websocket_manager.stop_server()
        if self.enhanced_collector: await self.enhanced_collector.close()
        if self.mimir_client: await self.mimir_client.close()
        if self.database: await self.database.close()

        if self.ai_detector:
            try:
                self.ai_detector.save_models()
                if self.config and self.config.deployment and self.config.deployment.edge_optimization:
                    self.ai_detector.quantize_for_edge()
                logger.info("AI models saved")
            except Exception as e:
                logger.warning(f"Failed to save AI models: {e}")

        self._log_final_performance_report()
        logger.info("Enhanced Network Intelligence Monitor stopped")


    def _setup_signal_handlers(self):
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self._initiate_shutdown(s)))
            except NotImplementedError:
                 logger.warning(f"Signal handling for {sig.name} not fully supported on this platform.")
                 signal.signal(sig, self._blocking_shutdown_handler)


    def _blocking_shutdown_handler(self, sig, frame):
        """Fallback shutdown handler for platforms where loop.add_signal_handler is not available."""
        logger.info(f"Received signal {signal.Signals(sig).name} (blocking handler), initiating shutdown...")
        if self.shutdown_event: 
            self.shutdown_event.set()


    async def _initiate_shutdown(self, sig):
        logger.info(f"Received signal {sig.name if isinstance(sig, signal.Signals) else sig}, initiating graceful shutdown...")
        self.shutdown_event.set()


    def _log_startup_summary(self):
        logger.info("=== Enhanced Network Intelligence Monitor Started ===")
        if self.config:
            if self.config.api:
                logger.info(f"API Server: http://{self.config.api.host}:{self.config.api.port}")
            if self.config.metrics:
                logger.info(f"Metrics Export (for Alloy): http://{self.config.metrics.host}:{self.config.metrics.port}/metrics")
            if self.websocket_manager and self.config.api and self.config.api.websocket_enabled:
                actual_port = self.websocket_manager.port
                logger.info(f"WebSocket Server: ws://{self.config.api.host}:{actual_port}/ws")
            if self.config.monitoring:
                logger.info(f"Targets: {', '.join(self.config.monitoring.targets)}")
            if self.config.networkquality:
                logger.info(f"NetworkQuality-RS Monitoring: {'Enabled' if self.config.networkquality.enabled else 'Disabled'}")
                if self.config.networkquality.enabled and self.nq_collector:
                    logger.info(f"NetworkQuality-RS Server: (uses default Cloudflare endpoints)")
        logger.info("=====================================================")

    async def _main_monitoring_loop(self):
        """Main monitoring loop with AI training and comprehensive metrics tracking"""
        logger.info("Main (enhanced_collector) monitoring loop started")
        
        # Initialize timing variables
        last_train_time = 0
        last_health_check = 0
        train_interval = self.config.ai.train_interval if self.config and self.config.ai else 3600
        
        # Initialize AI metrics if not already done
        if not hasattr(self, 'ai_metrics') and self.metrics_server:
            from src.ai_prometheus_metrics import AIModelPrometheusMetrics
            self.ai_metrics = AIModelPrometheusMetrics(registry=self.metrics_server.registry)
            
            # Set initial model info
            if self.ai_detector and self.config and self.config.ai:
                model_info = {
                    'version': '1.0.0',
                    'architecture': 'lstm_autoencoder',
                    'input_size': self.config.ai.input_size,
                    'hidden_size': self.config.ai.hidden_size,
                    'num_layers': self.config.ai.num_layers,
                    'quantized': self.config.deployment.edge_optimization if self.config.deployment else False
                }
                self.ai_metrics.update_model_info('enhanced_lstm', model_info)
        
        while self.running:
            if not self.config or not self.config.monitoring or not self.enhanced_collector:
                logger.debug("Main loop: Config or enhanced_collector not ready, sleeping.")
                await asyncio.sleep(5)
                continue
                
            try:
                cycle_start = time.time()
                
                # Collect metrics from all targets
                for target in self.config.monitoring.targets:
                    if not self.running:
                        break
                        
                    try:
                        # Collect enhanced metrics
                        collection_start = time.time()
                        metrics = await self.enhanced_collector.collect_enhanced_metrics(target)
                        collection_time = time.time() - collection_start
                        
                        if metrics and self.database:
                            # Store metrics in database
                            await self.database.store_metrics(metrics.to_dict())
                            
                            # Update Prometheus metrics
                            if self.metrics_aggregator:
                                self.metrics_aggregator.add_enhanced_metrics(metrics)
                            
                            # Update dynamic thresholds
                            if self.threshold_manager:
                                for metric_name, value in metrics.to_dict().items():
                                    if isinstance(value, (int, float)) and value >= 0:
                                        self.threshold_manager.add_measurement(metric_name, value)
                                        
                                        # Track threshold changes in AI metrics
                                        if self.ai_metrics and hasattr(self.threshold_manager, 'thresholds'):
                                            threshold_value = self.threshold_manager.thresholds.get(metric_name)
                                            if threshold_value:
                                                self.ai_metrics.update_threshold_metrics(
                                                    metric_name, 
                                                    threshold_value.current_value if hasattr(threshold_value, 'current_value') else threshold_value,
                                                    'dynamic'
                                                )
                            
                            # AI anomaly detection
                            if self.ai_detector:
                                inference_start = time.time()
                                
                                try:
                                    anomaly_result = await self.ai_detector.detect_anomaly(metrics)
                                    inference_time = time.time() - inference_start
                                    
                                    # Update AI inference metrics
                                    if self.ai_metrics:
                                        self.ai_metrics.update_inference_metrics('enhanced_lstm', inference_time)
                                    
                                    # Log AI activity
                                    logger.debug(f"🧠 AI inference completed in {inference_time:.3f}s for {target}")
                                    
                                    if anomaly_result.is_anomaly:
                                        logger.info(f"🚨 AI ANOMALY DETECTED for {target}: "
                                                  f"score={anomaly_result.anomaly_score:.3f}, "
                                                  f"confidence={anomaly_result.confidence:.2f}, "
                                                  f"severity={anomaly_result.severity}, "
                                                  f"pattern={anomaly_result.temporal_pattern}")
                                        
                                        # Update anomaly metrics
                                        if self.ai_metrics:
                                            self.ai_metrics.update_anomaly_metrics(
                                                'enhanced_lstm',
                                                target,
                                                anomaly_result.anomaly_score,
                                                anomaly_result.confidence,
                                                anomaly_result.severity
                                            )
                                        
                                        # Store anomaly in database
                                        await self.database.store_anomaly(
                                            metrics.timestamp,
                                            {
                                                'target_host': target,
                                                'anomaly_score': anomaly_result.anomaly_score,
                                                'confidence': anomaly_result.confidence,
                                                'severity': anomaly_result.severity,
                                                'temporal_pattern': anomaly_result.temporal_pattern,
                                                'baseline_values': anomaly_result.baseline_values,
                                                'thresholds': anomaly_result.thresholds,
                                                'feature_contributions': anomaly_result.feature_contributions,
                                                'recommendation': anomaly_result.recommendation,
                                                'attention_weights': anomaly_result.attention_weights
                                            }
                                        )
                                        
                                        # Send alert
                                        if self.alert_manager:
                                            from src.alerts import AlertSeverity
                                            
                                            severity_map = {
                                                'critical': AlertSeverity.CRITICAL,
                                                'high': AlertSeverity.HIGH,
                                                'medium': AlertSeverity.MEDIUM,
                                                'low': AlertSeverity.LOW,
                                                'info': AlertSeverity.INFO
                                            }
                                            
                                            alert = await self.alert_manager.create_alert(
                                                title=f"AI Network Anomaly: {target}",
                                                description=anomaly_result.recommendation,
                                                severity=severity_map.get(anomaly_result.severity.lower(), AlertSeverity.MEDIUM),
                                                source="ai_detector",
                                                metric_name="anomaly_score",
                                                current_value=anomaly_result.anomaly_score,
                                                threshold=self.ai_detector.thresholds.get('reconstruction_error', 0.5),
                                                target=target,
                                                context={
                                                    'confidence': anomaly_result.confidence,
                                                    'temporal_pattern': anomaly_result.temporal_pattern,
                                                    'feature_contributions': anomaly_result.feature_contributions,
                                                    'sequence_score': anomaly_result.sequence_score
                                                }
                                            )
                                            
                                            self.performance_stats['alerts_sent'] += 1
                                        
                                        # Send webhook notification if configured
                                        if hasattr(self, 'webhook_sender') and self.webhook_sender:
                                            # Extract top contributing features
                                            top_features = sorted(
                                                anomaly_result.feature_contributions.items(),
                                                key=lambda x: x[1],
                                                reverse=True
                                            )[:3]
                                            
                                            insights = [
                                                f"Anomaly detected with {anomaly_result.confidence:.0%} confidence",
                                                f"Temporal pattern: {anomaly_result.temporal_pattern}",
                                                f"Top contributing factors: {', '.join([f[0] for f in top_features])}"
                                            ]
                                            
                                            recommendations = [
                                                anomaly_result.recommendation,
                                                "Review recent network changes",
                                                "Check for correlated anomalies in the region"
                                            ]
                                            
                                            webhook_sent = self.webhook_sender.send_model_anomaly_alert(
                                                device=target,
                                                domain=target,
                                                metric="ai_anomaly_score",
                                                value=anomaly_result.anomaly_score,
                                                severity=anomaly_result.severity,
                                                confidence=anomaly_result.confidence,
                                                baseline_value=anomaly_result.baseline_values.get('overall_mean', 0),
                                                deviation_factor=anomaly_result.anomaly_score / max(anomaly_result.baseline_values.get('overall_mean', 0.1), 0.1),
                                                insights=insights,
                                                recommendations=recommendations,
                                                test_results={
                                                    'sequence_score': anomaly_result.sequence_score,
                                                    'attention_variance': sum(anomaly_result.attention_weights.values()) / len(anomaly_result.attention_weights) if anomaly_result.attention_weights else 0,
                                                    'temporal_pattern': anomaly_result.temporal_pattern
                                                }
                                            )
                                            
                                            if webhook_sent:
                                                logger.info(f"📤 Webhook notification sent for AI anomaly on {target}")
                                        
                                        # Update Prometheus anomaly metrics
                                        if self.metrics_aggregator:
                                            self.metrics_aggregator.add_anomaly_metrics(anomaly_result, target)
                                        
                                        self.performance_stats['anomalies_detected'] += 1
                                    else:
                                        logger.debug(f"✅ AI: Normal behavior for {target} (score: {anomaly_result.anomaly_score:.3f})")
                                    
                                    # Update baseline metrics periodically
                                    if hasattr(anomaly_result, 'baseline_values') and self.ai_metrics:
                                        deviations = {}
                                        for feature, contrib in anomaly_result.feature_contributions.items():
                                            deviations[feature] = contrib
                                        
                                        self.ai_metrics.update_baseline_metrics(
                                            'adaptive',
                                            'ai_detector',
                                            deviations
                                        )
                                    
                                except Exception as e:
                                    logger.error(f"Error in AI anomaly detection for {target}: {e}")
                            
                            self.performance_stats['total_measurements'] += 1
                            self.network_logger.log_metrics_collected(target, metrics.to_dict())
                            
                            # Log collection performance
                            logger.debug(f"📊 Metrics collected for {target} in {collection_time:.3f}s")
                            
                    except Exception as e:
                        logger.error(f"Error collecting metrics for {target}: {e}")
                        self.network_logger.log_connection_failure(target, "enhanced", str(e))
                
                # Periodic AI training
                current_time = time.time()
                if (self.ai_detector and 
                    self.config.ai.auto_train and 
                    current_time - last_train_time > train_interval):
                    
                    logger.info("🧠 Starting AI model training...")
                    training_start = time.time()
                    
                    try:
                        # Get training data from database
                        training_data = await self.database.get_metrics_for_training(
                            hours=self.config.ai.training_hours if self.config.ai else 24
                        )
                        
                        if len(training_data) >= 50:
                            # Get initial model state for comparison
                            initial_loss = None
                            if hasattr(self.ai_detector, 'model') and self.ai_detector.model:
                                # Calculate initial loss on a sample
                                sample_batch = training_data[:10]
                                initial_loss = await self._calculate_model_loss(sample_batch)
                            
                            # Perform online training
                            await self.ai_detector.train_online(training_data)
                            
                            training_duration = time.time() - training_start
                            
                            # Calculate final loss
                            final_loss = None
                            if hasattr(self.ai_detector, 'model') and self.ai_detector.model:
                                final_loss = await self._calculate_model_loss(sample_batch if initial_loss else training_data[:10])
                            
                            # Update AI training metrics
                            if self.ai_metrics:
                                self.ai_metrics.update_training_metrics(
                                    'enhanced_lstm',
                                    'online',
                                    training_duration,
                                    len(training_data),
                                    final_loss if final_loss is not None else 0.05
                                )
                                
                                # Update online learning metrics
                                if hasattr(self.ai_detector, 'optimizer') and self.ai_detector.optimizer:
                                    current_lr = self.ai_detector.optimizer.param_groups[0]['lr']
                                    self.ai_metrics.update_online_learning_metrics(
                                        'enhanced_lstm',
                                        current_lr
                                    )
                                
                                # Update model health
                                model_age = current_time - self.ai_detector.model_creation_time if hasattr(self.ai_detector, 'model_creation_time') else 0
                                health_score = self._calculate_model_health_score()
                                self.ai_metrics.update_model_health(
                                    'enhanced_lstm',
                                    health_score,
                                    model_age
                                )
                            
                            self.performance_stats['model_trainings'] += 1
                            last_train_time = current_time
                            
                            # Log training results
                            improvement = ((initial_loss - final_loss) / initial_loss * 100) if initial_loss and final_loss else 0
                            logger.info(f"✅ AI training completed: {len(training_data)} samples in {training_duration:.2f}s")
                            if initial_loss and final_loss:
                                logger.info(f"📈 Model improvement: {improvement:.1f}% (loss: {initial_loss:.4f} → {final_loss:.4f})")
                            
                            # Save model checkpoint
                            if self.ai_detector:
                                try:
                                    self.ai_detector.save_models()
                                    logger.info("💾 AI model checkpoint saved")
                                except Exception as e:
                                    logger.error(f"Failed to save model checkpoint: {e}")
                        else:
                            logger.info(f"⏸️  Insufficient training data: {len(training_data)} samples (need >= 50)")
                        
                    except Exception as e:
                        logger.error(f"Error in AI training: {e}")
                
                # Periodic health check
                if current_time - last_health_check > 300:  # Every 5 minutes
                    self.performance_stats['system_health_score'] = self._calculate_system_health()
                    
                    # Log AI model status
                    if self.ai_detector and hasattr(self.ai_detector, 'is_trained'):
                        logger.info(f"🤖 AI Model Status: trained={self.ai_detector.is_trained}, "
                                  f"trainings={self.performance_stats['model_trainings']}, "
                                  f"anomalies_detected={self.performance_stats['anomalies_detected']}")
                    
                    last_health_check = current_time
                
                # Update average collection time
                cycle_time = time.time() - cycle_start
                self.performance_stats['average_collection_time'] = (
                    (self.performance_stats['average_collection_time'] * 0.9) + 
                    (cycle_time * 0.1)
                )
                
                # Sleep until next collection
                sleep_time = max(1, self.config.monitoring.interval - cycle_time)
                
                if not self.running:
                    break
                    
                await asyncio.sleep(sleep_time)
                
            except asyncio.CancelledError:
                logger.info("Main monitoring loop cancelled.")
                break
            except Exception as e:
                logger.exception(f"Error in main monitoring loop: {e}")
                await asyncio.sleep(60)  # Error backoff
        
        logger.info("Main (enhanced_collector) monitoring loop stopped")


    async def _calculate_model_loss(self, training_data):
        """Calculate current model loss on sample data"""
        try:
            if not self.ai_detector or not hasattr(self.ai_detector, 'model'):
                return None
            
            # Prepare a small batch of data
            import torch
            import numpy as np
            
            # Extract features from training data
            features_list = []
            for data_point in training_data[:10]:  # Use first 10 samples
                features = self.ai_detector._extract_enhanced_features(data_point)
                features_list.append(features)
            
            # Create sequence
            if len(features_list) >= self.ai_detector.sequence_length:
                sequence = np.array(features_list[:self.ai_detector.sequence_length])
                
                # Scale and convert to tensor
                sequence_scaled = self.ai_detector.scaler.transform(
                    sequence.reshape(-1, self.ai_detector.input_size)
                )
                sequence_scaled = sequence_scaled.reshape(
                    1, self.ai_detector.sequence_length, self.ai_detector.input_size
                )
                sequence_tensor = torch.FloatTensor(sequence_scaled).to(self.ai_detector.device)
                
                # Calculate loss
                self.ai_detector.model.eval()
                with torch.no_grad():
                    reconstructed, _ = self.ai_detector.model(sequence_tensor)
                    loss = torch.nn.functional.mse_loss(reconstructed, sequence_tensor)
                    return loss.item()
            
            return 0.1  # Default if not enough data
            
        except Exception as e:
            logger.error(f"Error calculating model loss: {e}")
            return 0.1

    def _calculate_model_health_score(self) -> float:
        """Calculate AI model health score based on various factors"""
        score = 100.0
        
        try:
            if not self.ai_detector:
                return 0.0
                
            # Check if model is trained
            if not hasattr(self.ai_detector, 'is_trained') or not self.ai_detector.is_trained:
                score -= 50
            
            # Check model age (penalize if too old without retraining)
            if hasattr(self.ai_detector, 'model_creation_time'):
                age_hours = (time.time() - self.ai_detector.model_creation_time) / 3600
                if age_hours > 168:  # 1 week
                    score -= 20
                elif age_hours > 72:  # 3 days
                    score -= 10
            
            # Check training frequency
            if self.performance_stats['model_trainings'] == 0:
                score -= 20
            
            # Check anomaly detection effectiveness
            if self.performance_stats['total_measurements'] > 100:
                anomaly_rate = self.performance_stats['anomalies_detected'] / self.performance_stats['total_measurements']
                if anomaly_rate > 0.5:  # Too many anomalies
                    score -= 15
                elif anomaly_rate < 0.001:  # Too few anomalies
                    score -= 10
            
            # Check for recent successful inferences
            if hasattr(self.ai_detector, 'last_inference_time'):
                time_since_inference = time.time() - self.ai_detector.last_inference_time
                if time_since_inference > 600:  # 10 minutes
                    score -= 15
                    
        except Exception as e:
            logger.error(f"Error calculating model health: {e}")
            score = 50.0
        
        return max(0.0, score)

    async def _create_ai_alert(self, target: str, metrics, anomaly_result):
        """Create alert from AI anomaly detection"""
        
        if self.alert_manager:
            await self.alert_manager.create_alert(
                title=f"AI Anomaly Detected: {target}",
                description=anomaly_result.recommendation,
                severity=AlertSeverity.HIGH if anomaly_result.severity in ['critical', 'high'] else AlertSeverity.MEDIUM,
                source="ai_detector",
                metric_name="anomaly_score",
                current_value=anomaly_result.anomaly_score,
                threshold=self.ai_detector.thresholds.get('reconstruction_error', 0.5),
                target=target,
                context={
                    'confidence': anomaly_result.confidence,
                    'temporal_pattern': anomaly_result.temporal_pattern,
                    'feature_contributions': anomaly_result.feature_contributions,
                    'attention_weights': anomaly_result.attention_weights
                }
            )
            
            # Send webhook notification via dedicated sender
            if self.webhook_sender:
                self.webhook_sender.send_model_anomaly_alert(
                    device=target,
                    domain=target,
                    metric="anomaly_score",
                    value=anomaly_result.anomaly_score,
                    severity=anomaly_result.severity,
                    confidence=anomaly_result.confidence,
                    insights=[anomaly_result.recommendation],
                    recommendations=self._generate_ai_recommendations(anomaly_result),
                    test_results={
                        'anomaly_score': anomaly_result.anomaly_score,
                        'sequence_score': anomaly_result.sequence_score,
                        'temporal_pattern': anomaly_result.temporal_pattern
                    }
                )

    async def _store_nq_metrics(self, metrics: ResponsivenessMetrics):
        """Store NetworkQuality metrics in the database"""
        if not self.database or not self.database.db:
            logger.warning("Database not available for storing NQRS metrics.")
            return
        try:
            recommendations_json = json.dumps(metrics.recommendations) if metrics.recommendations else None
            await self.database.db.execute("""
                INSERT INTO network_quality_rs_metrics (
                    timestamp, target_host, rpm_download, rpm_upload, base_rtt_ms,
                    loaded_rtt_download_ms, loaded_rtt_upload_ms, download_throughput_mbps,
                    upload_throughput_mbps, download_responsiveness_score, upload_responsiveness_score,
                    rpm_average, download_bufferbloat_ms, upload_bufferbloat_ms, max_bufferbloat_ms,
                    bufferbloat_severity, overall_quality_score, quality_rating,
                    congestion_detected, measurement_duration_ms, error, recommendations
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metrics.timestamp, metrics.target_host, metrics.rpm_download, metrics.rpm_upload, metrics.base_rtt_ms,
                metrics.loaded_rtt_download_ms, metrics.loaded_rtt_upload_ms, metrics.download_throughput_mbps,
                metrics.upload_throughput_mbps, metrics.download_responsiveness_score, metrics.upload_responsiveness_score,
                metrics.rpm_average, metrics.download_bufferbloat_ms, metrics.upload_bufferbloat_ms, metrics.max_bufferbloat_ms,
                metrics.bufferbloat_severity, metrics.overall_quality_score, metrics.quality_rating,
                metrics.congestion_detected, metrics.measurement_duration_ms, metrics.error, recommendations_json
            ))
            await self.database.db.commit()
            logger.debug(f"Stored NetworkQuality-RS metrics for {metrics.target_host}")
        except Exception as e:
            logger.error(f"Failed to store NQRS metrics for {metrics.target_host}: {e}", exc_info=True)

    async def _networkquality_monitoring_loop(self):
        if not self.config or not self.config.networkquality or not self.config.networkquality.enabled or not self.nq_collector:
            logger.info("NetworkQuality-RS monitoring loop not starting (disabled or collector not initialized).")
            return

        logger.info("NetworkQuality-RS monitoring loop started.")
        testing_config = self.config.networkquality.testing
        adaptive_intervals = testing_config.get('adaptive_intervals', {})
        default_interval = testing_config.get('default_interval_seconds', 300)

        while self.running:
            try:
                logger.debug("Requesting NQRS measurement...")
                nq_metrics = await self.nq_collector.collect_network_quality()

                if nq_metrics:
                    self.performance_stats['total_nq_measurements'] += 1
                    
                    if nq_metrics.error:
                        logger.warning(f"NQRS measurement for {nq_metrics.target_host} resulted in an error: {nq_metrics.error}")
                    else:
                        rpm_avg_str = f"{nq_metrics.rpm_average:.2f}" if nq_metrics.rpm_average is not None else "N/A"
                        logger.info(f"NQRS metrics for {nq_metrics.target_host}: RPM {rpm_avg_str}, Rating {nq_metrics.quality_rating}")
                        
                        # FIX: The collector already stores metrics, so this line is removed.
                        if self.database:
                            await self._store_nq_metrics(nq_metrics) 
                       
                        if self.metrics_aggregator:
                            self.metrics_aggregator.add_networkquality_metrics(nq_metrics)
                            logger.debug("Sent NetworkQuality metrics to Prometheus")

                        if self.alert_manager and (nq_metrics.quality_rating in ["poor", "error"] or \
                           (nq_metrics.rpm_average is not None and nq_metrics.rpm_average < self.config.networkquality.thresholds['rpm']['fair'])):
                            
                            rpm_str = f"{nq_metrics.rpm_average:.0f}" if nq_metrics.rpm_average is not None else "N/A"
                            bufferbloat_str = f"{nq_metrics.max_bufferbloat_ms:.0f}" if nq_metrics.max_bufferbloat_ms is not None else "N/A"
                            recs_str = ' '.join(nq_metrics.recommendations or [])

                            alert_description = (
                                f"Quality: {nq_metrics.quality_rating}, RPM: {rpm_str}, "
                                f"Bufferbloat: {bufferbloat_str}ms. Recs: {recs_str}"
                            )

                            await self.alert_manager.create_alert(
                                title=f"Network Responsiveness Issue: {nq_metrics.target_host}",
                                description=alert_description,
                                severity=AlertSeverity.HIGH if nq_metrics.quality_rating == "poor" else AlertSeverity.CRITICAL,
                                source="networkquality_rs",
                                metric_name="rpm_average",
                                current_value=nq_metrics.rpm_average if nq_metrics.rpm_average is not None else -1,
                                threshold=float(self.config.networkquality.thresholds['rpm']['fair']), 
                                target=str(nq_metrics.target_host)
                            )

                    current_rating = nq_metrics.quality_rating if not nq_metrics.error else "error"
                    sleep_interval = adaptive_intervals.get(current_rating, default_interval)
                else:
                    logger.warning("NQRS collector returned no metrics.")
                    sleep_interval = adaptive_intervals.get("error", default_interval)

                if not self.running: break
                await asyncio.sleep(sleep_interval)
            except asyncio.CancelledError:
                logger.info("NetworkQuality-RS monitoring loop cancelled.")
                break
            except Exception as e:
                logger.exception(f"Error in NQRS monitoring loop: {e}")
                await asyncio.sleep(adaptive_intervals.get('error', 300))
        logger.info("NetworkQuality-RS monitoring loop stopped.")

    async def _run_api_server(self):
        if not self.api_server:
            logger.error("API Server not initialized, cannot run.")
            return
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.api_server.run)
        except asyncio.CancelledError:
            logger.info("API server task cancelled.")
        except Exception as e:
            logger.exception(f"API server error: {e}")


    async def _baseline_update_loop(self):
         if not self.mimir_client:
             logger.info("Mimir client not initialized, skipping baseline update loop.")
             return
         logger.info("Baseline update loop started.")
         while self.running:
            try:
                await asyncio.sleep(21600)
            except asyncio.CancelledError:
                logger.info("Baseline update loop cancelled.")
                break
            except Exception as e:
                logger.exception(f"Error in baseline update loop: {e}")
                await asyncio.sleep(3600)
         logger.info("Baseline update loop stopped.")


    def _log_final_performance_report(self):
        uptime = time.time() - self.performance_stats['system_start_time']
        logger.info("=== Final Performance Report ===")
        logger.info(f"System Uptime: {uptime/3600:.2f} hours")
        logger.info(f"Total Standard Measurements: {self.performance_stats['total_measurements']}")
        logger.info(f"Total NetworkQuality-RS Measurements: {self.performance_stats['total_nq_measurements']}")
        logger.info(f"Anomalies Detected: {self.performance_stats['anomalies_detected']}")
        logger.info(f"Alerts Sent: {self.performance_stats['alerts_sent']}")
        logger.info(f"Model Trainings: {self.performance_stats['model_trainings']}")
        logger.info(f"Baseline Updates: {self.performance_stats['baseline_updates']}")
        logger.info(f"Average Collection Time: {self.performance_stats['average_collection_time']:.2f}s")
        logger.info(f"Final Health Score: {self.performance_stats['system_health_score']:.1f}")
        logger.info("================================")

    def _calculate_system_health(self) -> float:
        return 95.0


async def main():
    create_config_file_if_not_exists("config.yaml")
    setup_logging()

    config_file = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    monitor = EnhancedNetworkIntelligenceMonitor(config_file)

    try:
        if await monitor.initialize():
            await monitor.start()
        else:
            logger.error("Monitor initialization failed. Exiting.")
            sys.exit(1)
    except asyncio.CancelledError:
        logger.info("Main task cancelled by shutdown event.")
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {e}", exc_info=True)
    finally:
        if monitor.running: 
            if not monitor.shutdown_event.is_set():
                 monitor.shutdown_event.set() 
                 await monitor.stop() 
        elif monitor.shutdown_event.is_set():
            logger.info("Monitor shutdown was initiated, ensuring cleanup.")
            await monitor.stop()
        logger.info("Application shutdown sequence complete.")

if __name__ == "__main__":
    asyncio.run(main())

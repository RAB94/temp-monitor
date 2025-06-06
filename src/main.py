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
# New imports for networkquality-rs
from src.networkquality.collector import NetworkQualityCollector, ResponsivenessMetrics

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
        if self.config and self.config.metrics:
            metrics_conf = self.config.metrics
            self.metrics_server = PrometheusMetricsServer(port=metrics_conf.port, host=metrics_conf.host)
            
            try:
                self.metrics_server.start()
            except Exception as e:
                logger.error(f"Failed to start metrics server: {e}")
                return

            # Create the aggregator
            self.metrics_aggregator = MetricsAggregator(self.metrics_server, batch_size=metrics_conf.batch_size)
            
            # Initialize NetworkQuality metrics support if enabled
            if self.config.networkquality and self.config.networkquality.enabled:
                # Import and add the method directly to MetricsAggregator
                def add_networkquality_metrics(self, nq_metrics_data):
                    """Add NetworkQuality metrics to Prometheus export"""
                    try:
                        # Lazy initialization with proper singleton pattern
                        if not hasattr(self, 'nq_metrics'):
                            from src.networkquality.prometheus_metrics import NetworkQualityPrometheusMetrics
                            
                            # Always use the main registry
                            registry = self.metrics_server.metrics.registry
                            
                            try:
                                self.nq_metrics = NetworkQualityPrometheusMetrics(registry=registry)
                                logger.info("NetworkQuality Prometheus metrics initialized with main registry")
                            except ValueError as ve:
                                logger.error(f"Cannot initialize NetworkQuality metrics: {ve}")
                                self.nq_metrics = None
                                return
                        
                        # Update metrics if handler exists
                        if self.nq_metrics:
                            data = nq_metrics_data.to_dict() if hasattr(nq_metrics_data, 'to_dict') else nq_metrics_data
                            self.nq_metrics.update_metrics(data)
                            logger.debug(f"Updated NetworkQuality metrics for {data.get('target_host', 'unknown')}")
                        
                    except Exception as e:
                        logger.error(f"Error in add_networkquality_metrics: {e}")
                
                # Bind the method to the aggregator instance
                import types
                self.metrics_aggregator.add_networkquality_metrics = types.MethodType(
                    add_networkquality_metrics, 
                    self.metrics_aggregator
                )
                
                logger.info("NetworkQuality metrics support added to aggregator")
            
            # Start the aggregator
            self.metrics_aggregator.start()
            logger.info(f"Prometheus metrics server configured on port {metrics_conf.port}")
        else:
            logger.warning("Metrics configuration not found, skipping metrics export.")

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
        logger.info("Main (enhanced_collector) monitoring loop started")
        while self.running:
            if not self.config or not self.config.monitoring or not self.enhanced_collector:
                logger.debug("Main loop: Config or enhanced_collector not ready, sleeping.")
                await asyncio.sleep(5)
                continue
            try:
                for target in self.config.monitoring.targets:
                    if not self.running: break
                    metrics = await self.enhanced_collector.collect_enhanced_metrics(target)
                    if metrics and self.database:
                        await self.database.store_metrics(metrics.to_dict())
                        if self.metrics_aggregator:
                           self.metrics_aggregator.add_enhanced_metrics(metrics)
                        self.performance_stats['total_measurements'] += 1
                if not self.running: break
                await asyncio.sleep(self.config.monitoring.interval)
            except asyncio.CancelledError:
                logger.info("Main monitoring loop cancelled.")
                break
            except Exception as e:
                logger.exception(f"Error in main monitoring loop: {e}")
                await asyncio.sleep(60)
        logger.info("Main (enhanced_collector) monitoring loop stopped")


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

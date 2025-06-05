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
from src.networkquality.server import NetworkQualityServerManager

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
        self.nq_server_manager: Optional[NetworkQualityServerManager] = None
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
            await self._detect_environment() # Call to the method that was missing
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
        if self.config and self.config.networkquality: # Check if config and networkquality section exist
            logger.info(f"NetworkQuality-RS enabled: {self.config.networkquality.enabled}")
        else:
            logger.warning("NetworkQuality configuration section not found or config not loaded.")


    async def _detect_environment(self): # Added method definition
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

        # Example of applying optimizations based on detection
        if environment_info.get('is_edge_device') and self.config.deployment and not self.config.deployment.edge_optimization:
            logger.info("Auto-enabling edge optimizations based on environment detection.")
            self.config.deployment.edge_optimization = True
            if hasattr(self.config.deployment, 'quantize_models'): # Ensure attribute exists
                self.config.deployment.quantize_models = True
            if self.config.monitoring: # Ensure attribute exists
                self.config.monitoring.interval = optimal_config_params.get('monitoring_interval', 60)
        # Further logic to adjust self.config based on environment_info can be added here.


    async def _initialize_networkquality_rs(self):
        """Initializes NetworkQuality-RS server manager and collector."""
        if not self.config or not self.config.networkquality or not self.config.networkquality.enabled:
            logger.info("NetworkQuality-RS monitoring is disabled in configuration.")
            return

        logger.info("Initializing NetworkQuality-RS components...")

        if self.config.networkquality.server.type == 'self_hosted' and \
           self.config.networkquality.server.auto_start:
            self.nq_server_manager = NetworkQualityServerManager(self.config.networkquality)
            started = await self.nq_server_manager.start()
            if not started:
                logger.error("Failed to start self-hosted NetworkQuality server. RPM tests might fail.")
            else:
                logger.info("Self-hosted NetworkQuality server manager started.")
        else:
            logger.info("NetworkQuality server is configured as external or auto_start is false. Not managing server process.")

        self.nq_collector = NetworkQualityCollector(self.config.networkquality, self.database)
        logger.info("NetworkQuality-RS collector initialized.")
        if self.nq_collector and not self.nq_collector.server_url and self.config.networkquality.enabled:
             logger.warning("NetworkQuality-RS is enabled, but no server URL is configured for the collector. RPM tests may not run.")


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
                'sequence_length': self.config.ai.sequence_length,  # Direct attribute access
                'input_size': self.config.ai.input_size,            # Direct attribute access
                'hidden_size': self.config.ai.hidden_size,          # Direct attribute access
                'num_layers': self.config.ai.num_layers,            # Direct attribute access
                'initial_epochs': self.config.ai.initial_epochs,
                'enable_quantization': self.config.ai.enable_quantization,
                'deployment_type': 'edge' if self.config.deployment and self.config.deployment.edge_optimization else 'standard'
            }
            self.ai_detector = EnhancedLSTMAnomalyDetector(ai_config)
            await self.ai_detector.initialize()
            try:
                self.ai_detector.load_models()
                if self.ai_logger:  # Check if logger exists
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
            # Convert dataclass to dictionary
            alert_config = asdict(self.config.alerts)
            
            # The alert manager expects a specific structure, so we need to wrap it properly
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
                'retention_hours': 168  # 1 week
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
            # Ensure start is called in a non-blocking way if it's blocking
            # For Flask, self.metrics_server.start() might be blocking.
            # If so, it should be run in a separate thread or using asyncio.to_thread in an async context.
            # For simplicity here, assuming it's non-blocking or managed by its own thread.
            try:
                self.metrics_server.start() # Review this start call
            except Exception as e:
                logger.error(f"Failed to start metrics server: {e}")
                return


            self.metrics_aggregator = MetricsAggregator(self.metrics_server, batch_size=metrics_conf.batch_size)
            self.metrics_aggregator.start()
            logger.info(f"Prometheus metrics server configured on port {metrics_conf.port}")
        else:
            logger.warning("Metrics configuration not found, skipping metrics export.")


    async def _initialize_api_server(self):
        if self.config:
            # Create API server with only the expected parameters
            self.api_server = APIServer(
                self.config, 
                self.database, 
                self.ai_detector, 
                self.enhanced_collector
            )
            
            # Add additional components as attributes after creation
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
            websocket_port = self.config.api.websocket_port # Use port from APIConfig

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
                self.websocket_manager = None # Ensure it's None if start failed
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
                           self.config.get('deployment') # fallback
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
        # ... (existing verification logic) ...
        if self.config.networkquality and self.config.networkquality.enabled:
            logger.info("Verifying NetworkQuality-RS setup...")
            if self.nq_collector and self.nq_collector.server_url:
                logger.info(f"✓ NetworkQuality-RS collector configured for server: {self.nq_collector.server_url}")
            elif self.config.networkquality.enabled: # Check again if enabled but collector has no URL
                 logger.warning("✗ NetworkQuality-RS is enabled, but collector server URL not found.")

            if self.nq_server_manager and self.config.networkquality.server.type == 'self_hosted':
                if self.nq_server_manager.is_running():
                    logger.info("✓ Self-hosted NetworkQuality server is running.")
                elif self.config.networkquality.server.auto_start:
                    logger.warning("✗ Self-hosted NetworkQuality server was configured to auto-start but is not running.")
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
        # Cancel tasks
        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()
        # Wait for tasks to complete cancellation
        await asyncio.gather(*[t for t in tasks_to_cancel if t], return_exceptions=True)


        if self.nq_server_manager:
            await self.nq_server_manager.stop()
        if self.metrics_aggregator: self.metrics_aggregator.stop() # Typically synchronous
        if self.metrics_server: self.metrics_server.stop() # Flask dev server might not have a clean async stop
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
                 # For Windows, signal handling is different or not fully supported for asyncio loop
                 logger.warning(f"Signal handling for {sig.name} not fully supported on this platform.")
                 signal.signal(sig, self._blocking_shutdown_handler)


    def _blocking_shutdown_handler(self, sig, frame):
        """Fallback shutdown handler for platforms where loop.add_signal_handler is not available."""
        logger.info(f"Received signal {signal.Signals(sig).name} (blocking handler), initiating shutdown...")
        # This will set the event, and the main start() method's await self.shutdown_event.wait() will unblock.
        if self.shutdown_event: # Check if event exists
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
            if self.websocket_manager and self.config.api:
                 websocket_port = self.config.get('websocket_port', 8001)
                 logger.info(f"WebSocket Server: ws://{self.config.api.host}:{websocket_port}/ws")
            if self.config.monitoring:
                logger.info(f"Targets: {', '.join(self.config.monitoring.targets)}")
            if self.config.networkquality:
                logger.info(f"NetworkQuality-RS Monitoring: {'Enabled' if self.config.networkquality.enabled else 'Disabled'}")
                if self.config.networkquality.enabled and self.nq_collector:
                    logger.info(f"NetworkQuality-RS Server: {self.nq_collector.server_url or 'Not specified'}")
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
                    if not self.running: break # Check running flag frequently
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
                target_nq_server = self.nq_collector.server_url
                if not target_nq_server:
                    logger.warning("NQRS server URL not available. Skipping cycle.")
                    await asyncio.sleep(default_interval)
                    continue

                logger.debug(f"Requesting NQRS measurement: {target_nq_server}")
                nq_metrics = await self.nq_collector.collect_network_quality()

                if nq_metrics:
                    self.performance_stats['total_nq_measurements'] += 1
                    if nq_metrics.error:
                        logger.warning(f"NQRS measurement for {nq_metrics.target_host} error: {nq_metrics.error}")
                    else:
                        logger.info(f"NQRS metrics for {nq_metrics.target_host}: RPM {nq_metrics.rpm_average:.2f}, Rating {nq_metrics.quality_rating}")
                        if self.database:
                            await self._store_nq_metrics(nq_metrics)
                        # ... (Prometheus and alerting logic from previous version) ...
                        if self.alert_manager and (nq_metrics.quality_rating in ["poor", "error"] or \
                            (nq_metrics.rpm_average is not None and nq_metrics.rpm_average < self.config.networkquality.thresholds['rpm']['fair'])):
                             await self.alert_manager.create_alert(
                                title=f"Network Responsiveness Issue: {nq_metrics.target_host}",
                                description=f"Quality: {nq_metrics.quality_rating}, RPM: {nq_metrics.rpm_average:.0f if nq_metrics.rpm_average is not None else 'N/A'}, Bufferbloat: {nq_metrics.max_bufferbloat_ms:.0f if nq_metrics.max_bufferbloat_ms is not None else 'N/A'}ms. Recs: {' '.join(nq_metrics.recommendations or [])}",
                                severity=AlertSeverity.HIGH if nq_metrics.quality_rating == "poor" else AlertSeverity.CRITICAL,
                                source="networkquality_rs",
                                metric_name="rpm_average",
                                current_value=nq_metrics.rpm_average if nq_metrics.rpm_average is not None else -1,
                                threshold=float(self.config.networkquality.thresholds['rpm']['fair']), # Ensure float
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

    async def _store_nq_metrics(self, metrics: ResponsivenessMetrics):
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


    async def _run_api_server(self):
        if not self.api_server:
            logger.error("API Server not initialized, cannot run.")
            return
        try:
            loop = asyncio.get_event_loop()
            # Assuming self.api_server.run() is a blocking call (typical for Flask dev server)
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
                # ... (existing baseline update logic, ensure it's async or run in executor if blocking) ...
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
        # Placeholder
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
        if monitor.running: # Check if it was ever started
            logger.info("Main function ensuring monitor stop is called upon exit.")
            # If shutdown_event was already set, stop() would have been called.
            # If shutdown_event was not set (e.g. direct exception in start),
            # we ensure stop is called.
            if not monitor.shutdown_event.is_set():
                 monitor.shutdown_event.set() # Ensure loops know to stop
                 await monitor.stop() # Call stop if not already called via shutdown
        elif monitor.shutdown_event.is_set(): # If shutdown was initiated but start might not have fully completed
            logger.info("Monitor shutdown was initiated, ensuring cleanup.")
            await monitor.stop() # Ensure cleanup happens
        logger.info("Application shutdown sequence complete.")

if __name__ == "__main__":
    asyncio.run(main())

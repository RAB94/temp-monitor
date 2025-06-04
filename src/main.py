#!/usr/bin/env python3
"""
Enhanced Network Intelligence Monitor - Complete Main Application
===============================================================

Complete integration with Alloy→Mimir pipeline:
1. Collects enhanced network metrics
2. Exports metrics in Prometheus format for Alloy to scrape
3. Uses Mimir for historical baseline analysis
4. Provides AI-powered anomaly detection
5. Supports edge device deployment
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
from src.utils.logger import setup_logging, get_network_logger, get_ai_logger
from src.utils.database import Database
from src.collector import EnhancedNetworkCollector
from src.lstm_auto import EnhancedLSTMAnomalyDetector
from src.mimir_integration import MimirClient, integrate_with_existing_detector  # Fixed import
from src.prom_export import PrometheusMetricsServer, MetricsAggregator
from src.api.server import APIServer
from src.alerts import AlertManager, AlertSeverity
from src.dynamic_thresh import DynamicThresholdManager
from src.edge_opt import EdgeOptimizer
from src.websocket_server import WebSocketManager, WebSocketIntegration

logger = logging.getLogger(__name__)

class EnhancedNetworkIntelligenceMonitor:
    """Complete enhanced monitoring system with Alloy→Mimir integration"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = None
        self.running = False
        
        # Core components
        self.database = None
        self.enhanced_collector = None
        self.ai_detector = None
        self.mimir_client = None
        self.alert_manager = None
        self.threshold_manager = None
        self.edge_optimizer = None
        
        # Monitoring components
        self.metrics_server = None
        self.metrics_aggregator = None
        self.api_server = None
        self.websocket_manager = None
        self.websocket_integration = None
        
        # Specialized loggers
        self.network_logger = get_network_logger()
        self.ai_logger = get_ai_logger()
        
        # Threading and monitoring
        self.main_loop_task = None
        self.api_task = None
        self.baseline_update_task = None
        
        # Performance tracking
        self.performance_stats = {
            'system_start_time': time.time(),
            'total_measurements': 0,
            'anomalies_detected': 0,
            'alerts_sent': 0,
            'model_trainings': 0,
            'baseline_updates': 0,
            'average_collection_time': 0.0,
            'system_health_score': 100.0
        }
        
        # Shutdown handling
        self.shutdown_event = asyncio.Event()
        
    async def initialize(self):
        """Initialize all system components"""
        
        logger.info("Initializing Enhanced Network Intelligence Monitor with Alloy→Mimir integration...")
        
        try:
            # Load and validate configuration
            await self._load_configuration()
            
            # Detect and optimize for environment
            await self._detect_environment()
            
            # Initialize core database
            await self._initialize_database()
            
            # Initialize enhanced network collector
            await self._initialize_enhanced_collector()
            
            # Initialize AI detection system
            await self._initialize_ai_system()
            
            # Initialize Mimir integration (no Prometheus!)
            await self._initialize_mimir_integration()
            
            # Initialize alerting system
            await self._initialize_alerting_system()
            
            # Initialize dynamic thresholds
            await self._initialize_dynamic_thresholds()
            
            # Initialize Prometheus metrics export (for Alloy to scrape)
            await self._initialize_metrics_export()
            
            # Initialize API server
            await self._initialize_api_server()
            
            # Initialize WebSocket server
            await self._initialize_websocket_server()
            
            # Apply edge optimizations if needed
            await self._apply_edge_optimizations()
            
            # Verify Alloy→Mimir integration
            await self._verify_integration_setup()
            
            logger.info("Enhanced Network Intelligence Monitor initialization complete")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize enhanced monitor: {e}")
            raise
    
    async def _load_configuration(self):
        """Load and validate configuration"""
        
        self.config = Config(self.config_path)
        
        # Log configuration summary
        logger.info(f"Configuration loaded from: {self.config_path}")
        logger.info(f"Monitoring targets: {self.config.monitoring.targets}")
        logger.info(f"Monitoring interval: {self.config.monitoring.interval}s")
        logger.info(f"AI features enabled: {self.config.ai.auto_train}")
        logger.info(f"Edge optimization: {self.config.deployment.edge_optimization}")
        logger.info(f"Mimir enabled: {self.config.mimir.enabled}")
        
        # Validate Mimir configuration
        if self.config.mimir.enabled and not self.config.mimir.mimir_url:
            logger.warning("Mimir is enabled but no Mimir URL configured")
    
    async def _detect_environment(self):
        """Detect deployment environment and apply optimizations"""
        
        from src.utils.network import NetworkEnvironmentDetector
        
        environment = NetworkEnvironmentDetector.detect_deployment_environment()
        optimal_config = NetworkEnvironmentDetector.get_optimal_monitoring_config()
        
        logger.info(f"Environment detection:")
        logger.info(f"  Platform: {environment['platform']}")
        logger.info(f"  Is container: {environment['is_container']}")
        logger.info(f"  Is cloud: {environment['is_cloud']}")
        logger.info(f"  Is edge device: {environment['is_edge_device']}")
        logger.info(f"  Constraints: {environment['constraints']}")
        
        # Apply optimal configuration
        if environment['is_edge_device'] and not self.config.deployment.edge_optimization:
            logger.info("Auto-enabling edge optimizations")
            self.config.deployment.edge_optimization = True
            self.config.deployment.quantize_models = True
            self.config.monitoring.interval = optimal_config['monitoring_interval']
    
    async def _initialize_database(self):
        """Initialize database with enhanced schema"""
        
        self.database = Database(self.config.database_path)
        await self.database.initialize()
        
        logger.info(f"Database initialized: {self.config.database_path}")
    
    async def _initialize_enhanced_collector(self):
        """Initialize enhanced network metrics collector"""
        
        collector_config = {
            'targets': self.config.monitoring.targets,
            'timeout': self.config.monitoring.timeout,
            'enhanced_features': self.config.monitoring.enhanced_features,
            'quality_metrics': True,
            'path_analysis': True,
            'interface_monitoring': True
        }
        
        self.enhanced_collector = EnhancedNetworkCollector(collector_config)
        await self.enhanced_collector.initialize()
        
        logger.info("Enhanced network collector initialized")
    
    async def _initialize_ai_system(self):
        """Initialize AI detection system"""
        
        ai_config = {
            'model_dir': self.config.ai.model_dir,
            'sequence_length': 20,
            'input_size': 14,  # Enhanced feature count
            'hidden_size': 64,
            'num_layers': 2,
            'initial_epochs': self.config.ai.initial_epochs,
            'enable_quantization': self.config.ai.enable_quantization,
            'deployment_type': 'edge' if self.config.deployment.edge_optimization else 'standard'
        }
        
        self.ai_detector = EnhancedLSTMAnomalyDetector(ai_config)
        await self.ai_detector.initialize()
        
        # Try to load existing models
        try:
            self.ai_detector.load_models()
            self.ai_logger.log_model_loaded('enhanced_lstm', self.config.ai.model_dir)
            logger.info("Loaded existing AI models")
        except FileNotFoundError:
            logger.info("No existing AI models found - will train from scratch")
        
        logger.info("AI detection system initialized")
    
    async def _initialize_mimir_integration(self):
        """Initialize Mimir integration (no Prometheus!)"""
        
        if not self.config.mimir.enabled:
            logger.info("Mimir integration disabled")
            return
        
        mimir_config = {
            'mimir_url': self.config.mimir.mimir_url,
            'tenant_id': self.config.mimir.tenant_id,
            'timeout': 30,
            'cache_ttl_seconds': 300
        }
        
        if not mimir_config['mimir_url']:
            logger.warning("Mimir URL not configured, skipping Mimir integration")
            return
        
        self.mimir_client = MimirClient(mimir_config)
        await self.mimir_client.initialize()
        
        # Test connectivity
        connectivity = await self.mimir_client.test_connectivity()
        logger.info(f"Mimir connectivity: {connectivity}")
        
        # Integrate with AI detector for historical baselines
        if self.ai_detector:
            await integrate_with_existing_detector(
                self.ai_detector,
                self.mimir_client,
                target_hosts=self.config.monitoring.targets,
                days_back=30
            )
        
        logger.info("Mimir integration initialized")
    
    async def _initialize_alerting_system(self):
        """Initialize intelligent alerting system"""
        
        if not self.config.alerts.enabled:
            logger.info("Alerting system disabled")
            return
        
        alert_config = {
            'correlation': {
                'correlation_window_seconds': 300,
                'enable_grouping': True
            },
            'notifications': {
                'channels': [],
                'routing': {
                    'critical': [],
                    'high': [],
                    'medium': [],
                    'low': []
                }
            },
            'escalation': {
                'enabled': True,
                'rules': []
            },
            'retention_hours': 168  # 1 week
        }
        
        # Add webhook channel if configured
        if self.config.alerts.webhook_url:
            alert_config['notifications']['channels'].append({
                'name': 'webhook',
                'type': 'webhook',
                'config': {'url': self.config.alerts.webhook_url},
                'enabled': True
            })
            alert_config['notifications']['routing']['critical'] = ['webhook']
            alert_config['notifications']['routing']['high'] = ['webhook']
        
        from src.alerts import create_alert_manager
        self.alert_manager = create_alert_manager(alert_config)
        
        logger.info("Alerting system initialized")
    
    async def _initialize_dynamic_thresholds(self):
        """Initialize dynamic threshold management"""
        
        threshold_config = {
            'analysis_window_size': 1000,
            'adjustment_interval_seconds': 3600,
            'min_confidence': 0.3,
            'max_adjustment_factor': 0.2
        }
        
        from src.dynamic_thresh import setup_dynamic_thresholds
        self.threshold_manager = setup_dynamic_thresholds(threshold_config)
        
        logger.info("Dynamic threshold management initialized")
    
    async def _initialize_metrics_export(self):
        """Initialize Prometheus metrics export for Alloy"""
        
        metrics_config = {
            'metrics_port': self.config.metrics.port,
            'metrics_host': self.config.metrics.host,
            'metrics_batch_size': self.config.metrics.batch_size,
            'enable_aggregation': self.config.metrics.enable_aggregation
        }
        
        # Create metrics server for Alloy to scrape
        from src.prom_export import create_metrics_server, create_metrics_aggregator
        self.metrics_server = create_metrics_server(metrics_config)
        self.metrics_server.start()
        
        # Create metrics aggregator for efficiency
        self.metrics_aggregator = create_metrics_aggregator(
            self.metrics_server,
            metrics_config
        )
        self.metrics_aggregator.start()
        
        logger.info(f"Prometheus metrics server started on port {metrics_config['metrics_port']} for Alloy to scrape")
    
    async def _initialize_api_server(self):
        """Initialize enhanced API server"""
        
        self.api_server = EnhancedAPIServer(
            self.config,
            self.database,
            self.ai_detector,
            self.enhanced_collector,
            self.mimir_client,
            self.metrics_server,
            self.alert_manager,
            self.threshold_manager
        )
        
        logger.info("Enhanced API server initialized")
    
    async def _initialize_websocket_server(self):
        """Initialize WebSocket server for real-time updates"""
        
        self.websocket_manager = WebSocketManager(
            host=self.config.api.host,
            port=8001  # Different port from API
        )
        await self.websocket_manager.start_server()
        
        # Create integration
        self.websocket_integration = WebSocketIntegration(self.websocket_manager)
        
        logger.info("WebSocket server initialized on port 8001")
    
    async def _apply_edge_optimizations(self):
        """Apply edge device optimizations if needed"""
        
        if not self.config.deployment.edge_optimization:
            return
        
        edge_config = {
            'model_optimization': {
                'enable_quantization': self.config.deployment.quantize_models,
                'enable_pruning': False,
                'quantization_method': 'dynamic'
            },
            'memory_management': {
                'memory_limit_mb': self.config.deployment.max_memory_mb,
                'gc_threshold_mb': self.config.deployment.max_memory_mb * 0.8,
                'enable_monitoring': True
            },
            'cpu_optimization': {
                'max_cpu_percent': 80,
                'thread_count': 'auto'
            }
        }
        
        from src.edge_opt import create_edge_optimizer
        self.edge_optimizer = create_edge_optimizer(edge_config)
        
        # Optimize AI model
        if self.ai_detector and self.ai_detector.model:
            optimized_model = self.edge_optimizer.optimize_for_edge(
                model=self.ai_detector.model
            )
            self.ai_detector.model = optimized_model
        
        logger.info("Edge optimizations applied")
    
    async def _verify_integration_setup(self):
        """Verify the Alloy→Mimir integration setup"""
        
        logger.info("Verifying Alloy→Mimir integration setup...")
        
        integration_status = {
            'metrics_export': False,
            'mimir_connectivity': False,
            'alloy_config': False
        }
        
        # Check metrics export endpoint
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://localhost:{self.config.metrics.port}/metrics") as response:
                    if response.status == 200:
                        metrics_text = await response.text()
                        if 'network_' in metrics_text:
                            integration_status['metrics_export'] = True
                            logger.info("✓ Metrics export endpoint working")
                        else:
                            logger.warning("✗ Metrics endpoint accessible but no network metrics found")
                    else:
                        logger.warning(f"✗ Metrics endpoint returned status {response.status}")
        except Exception as e:
            logger.warning(f"✗ Could not verify metrics endpoint: {e}")
        
        # Check Mimir connectivity
        if self.mimir_client:
            try:
                connectivity = await self.mimir_client.test_connectivity()
                if connectivity.get('mimir', {}).get('status') == 'connected':
                    integration_status['mimir_connectivity'] = True
                    logger.info("✓ Mimir connectivity working")
                else:
                    logger.warning("✗ Mimir connectivity failed")
            except Exception as e:
                logger.warning(f"✗ Mimir connectivity test failed: {e}")
        
        # Check if Alloy config exists
        alloy_config_path = Path("configs/alloy/alloy")
        if alloy_config_path.exists():
            integration_status['alloy_config'] = True
            logger.info("✓ Alloy configuration file found")
        else:
            logger.warning("✗ Alloy configuration file not found")
        
        # Summary
        working_components = sum(integration_status.values())
        total_components = len(integration_status)
        
        if working_components == total_components:
            logger.info("🎉 Alloy→Mimir integration setup is complete and working!")
        else:
            logger.warning(f"⚠️  Integration setup partially working: {working_components}/{total_components} components operational")
            
            # Provide guidance
            if not integration_status['alloy_config']:
                logger.info("📋 To complete setup: Start Grafana Alloy with the provided configuration")
            if not integration_status['mimir_connectivity']:
                logger.info("📋 Check Mimir URL and tenant configuration")
    
    async def start(self):
        """Start the enhanced monitoring system"""
        
        logger.info("Starting Enhanced Network Intelligence Monitor...")
        
        if self.running:
            logger.warning("Monitor already running")
            return
        
        self.running = True
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        # Start main monitoring loop
        self.main_loop_task = asyncio.create_task(self._main_monitoring_loop())
        
        # Start API server
        self.api_task = asyncio.create_task(self._run_api_server())
        
        # Start baseline updates if Mimir is enabled
        if self.mimir_client:
            self.baseline_update_task = asyncio.create_task(self._baseline_update_loop())
        
        logger.info("Enhanced Network Intelligence Monitor started successfully")
        self._log_startup_summary()
        
        # Wait for shutdown signal
        await self.shutdown_event.wait()
        
        # Cleanup
        await self.stop()
    
    async def stop(self):
        """Stop the enhanced monitoring system"""
        
        logger.info("Stopping Enhanced Network Intelligence Monitor...")
        
        self.running = False
        
        # Cancel tasks
        tasks = [self.main_loop_task, self.api_task, self.baseline_update_task]
        for task in tasks:
            if task and not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # Stop components
        if self.threshold_manager:
            self.threshold_manager.stop()
        
        if self.alert_manager:
            self.alert_manager.stop()
        
        if self.metrics_aggregator:
            self.metrics_aggregator.stop()
        
        if self.metrics_server:
            self.metrics_server.stop()
        
        if self.websocket_manager:
            await self.websocket_manager.stop_server()
        
        # Close async components
        if self.enhanced_collector:
            await self.enhanced_collector.close()
        
        if self.mimir_client:
            await self.mimir_client.close()
        
        if self.database:
            await self.database.close()
        
        # Save AI models
        if self.ai_detector:
            try:
                self.ai_detector.save_models()
                
                if self.config.deployment.edge_optimization:
                    self.ai_detector.quantize_for_edge()
                
                self.ai_logger.log_model_saved(
                    'enhanced_lstm', 
                    self.config.ai.model_dir,
                    0.0  # File size would be calculated
                )
                logger.info("AI models saved")
            except Exception as e:
                logger.warning(f"Failed to save AI models: {e}")
        
        # Final performance report
        self._log_final_performance_report()
        
        logger.info("Enhanced Network Intelligence Monitor stopped")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            asyncio.create_task(self._initiate_shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, signal_handler)
    
    async def _initiate_shutdown(self):
        """Initiate shutdown"""
        self.shutdown_event.set()
    
    def _log_startup_summary(self):
        """Log startup summary"""
        
        logger.info("=== Enhanced Network Intelligence Monitor Started ===")
        logger.info(f"API Server: http://0.0.0.0:{self.config.api.port}")
        logger.info(f"Metrics Export (for Alloy): http://0.0.0.0:{self.config.metrics.port}/metrics")
        logger.info(f"WebSocket Server: ws://0.0.0.0:8001/ws")
        logger.info(f"Targets: {', '.join(self.config.monitoring.targets)}")
        logger.info(f"AI Detection: {'Enabled' if self.ai_detector else 'Disabled'}")
        logger.info(f"Mimir Integration: {'Enabled' if self.mimir_client else 'Disabled'}")
        logger.info(f"Edge Optimization: {'Enabled' if self.edge_optimizer else 'Disabled'}")
        logger.info(f"Alerting: {'Enabled' if self.alert_manager else 'Disabled'}")
        logger.info("=====================================================")
        
        if self.mimir_client:
            logger.info("📊 Data Flow: Monitor → Alloy (scrapes :8000/metrics) → Mimir")
        else:
            logger.info("📊 Data Flow: Monitor → Alloy (scrapes :8000/metrics)")
    
    async def _main_monitoring_loop(self):
        """Main monitoring loop with all enhancements"""
        
        last_train_time = 0
        last_health_check = 0
        train_interval = self.config.ai.train_interval
        
        logger.info("Main monitoring loop started")
        
        while self.running:
            try:
                cycle_start = time.time()
                
                # Collect metrics from all targets
                for target in self.config.monitoring.targets:
                    try:
                        # Collect enhanced metrics
                        metrics = await self.enhanced_collector.collect_enhanced_metrics(target)
                        
                        if metrics:
                            # Store in database
                            await self.database.store_metrics(metrics.to_dict())
                            
                            # Update Prometheus metrics (for Alloy to scrape)
                            if self.metrics_aggregator:
                                self.metrics_aggregator.add_enhanced_metrics(metrics)
                            
                            # Update dynamic thresholds
                            if self.threshold_manager:
                                for metric_name, value in metrics.to_dict().items():
                                    if isinstance(value, (int, float)) and value >= 0:
                                        self.threshold_manager.add_measurement(
                                            metric_name, value
                                        )
                            
                            # AI anomaly detection
                            if self.ai_detector:
                                anomaly_result = await self.ai_detector.detect_anomaly(metrics)
                                
                                if anomaly_result.is_anomaly:
                                    self.network_logger.log_anomaly_detected(
                                        target,
                                        anomaly_result.anomaly_score,
                                        anomaly_result.confidence,
                                        severity=anomaly_result.severity
                                    )
                                    
                                    # Store anomaly
                                    await self.database.store_anomaly(
                                        metrics.timestamp,
                                        {
                                            'target_host': target,
                                            'anomaly_score': anomaly_result.anomaly_score,
                                            'confidence': anomaly_result.confidence,
                                            'severity': anomaly_result.severity,
                                            'baseline_values': anomaly_result.baseline_values,
                                            'thresholds': anomaly_result.thresholds,
                                            'feature_contributions': anomaly_result.feature_contributions,
                                            'recommendation': anomaly_result.recommendation
                                        }
                                    )
                                    
                                    # Send alert
                                    if self.alert_manager:
                                        await self.alert_manager.create_alert(
                                            title=f"Network Anomaly: {target}",
                                            description=anomaly_result.recommendation,
                                            severity=getattr(AlertSeverity, anomaly_result.severity.upper()),
                                            source="ai_detector",
                                            metric_name="anomaly_score",
                                            current_value=anomaly_result.anomaly_score,
                                            threshold=0.5,
                                            target=target,
                                            context=anomaly_result.feature_contributions
                                        )
                                        self.performance_stats['alerts_sent'] += 1
                                    
                                    # Send WebSocket notification
                                    if self.websocket_integration:
                                        await self.websocket_integration.on_anomaly_detected(
                                            anomaly_result, target
                                        )
                                    
                                    # Update metrics
                                    if self.metrics_aggregator:
                                        self.metrics_aggregator.add_anomaly_metrics(
                                            anomaly_result, target
                                        )
                                    
                                    self.performance_stats['anomalies_detected'] += 1
                            
                            # Send WebSocket metrics update
                            if self.websocket_integration:
                                await self.websocket_integration.on_metrics_collected(metrics)
                            
                            self.performance_stats['total_measurements'] += 1
                            
                            self.network_logger.log_metrics_collected(target, metrics.to_dict())
                        
                    except Exception as e:
                        logger.error(f"Error collecting metrics for {target}: {e}")
                        self.network_logger.log_connection_failure(target, "enhanced", str(e))
                
                # Periodic AI training
                current_time = time.time()
                if (self.ai_detector and 
                    self.config.ai.auto_train and 
                    current_time - last_train_time > train_interval):
                    
                    logger.info("Starting periodic AI training...")
                    
                    try:
                        training_data = await self.database.get_metrics_for_training(hours=24)
                        
                        if len(training_data) >= 50:
                            training_start = time.time()
                            
                            await self.ai_detector.train_online(training_data)
                            
                            training_time = time.time() - training_start
                            
                            self.ai_logger.log_training_complete(
                                'enhanced_lstm',
                                training_time * 1000,
                                {'samples': len(training_data)}
                            )
                            
                            self.performance_stats['model_trainings'] += 1
                            last_train_time = current_time
                            
                            logger.info(f"AI training completed in {training_time:.2f}s")
                        else:
                            logger.info(f"Insufficient training data: {len(training_data)} samples")
                    
                    except Exception as e:
                        logger.error(f"Error in AI training: {e}")
                
                # Health check
                if current_time - last_health_check > 300:  # Every 5 minutes
                    self.performance_stats['system_health_score'] = self._calculate_system_health()
                    last_health_check = current_time
                
                # Update average collection time
                cycle_time = time.time() - cycle_start
                self.performance_stats['average_collection_time'] = (
                    (self.performance_stats['average_collection_time'] * 0.9) + 
                    (cycle_time * 0.1)
                )
                
                # Sleep until next collection
                sleep_time = max(1, self.config.monitoring.interval - cycle_time)
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Error in main monitoring loop: {e}")
                await asyncio.sleep(60)  # Error backoff
        
        logger.info("Main monitoring loop stopped")
    
    async def _run_api_server(self):
        """Run API server"""
        
        try:
            def run_server():
                self.api_server.run(
                    host=self.config.api.host,
                    port=self.config.api.port,
                    debug=self.config.api.debug
                )
            
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, run_server)
        except Exception as e:
            logger.error(f"API server error: {e}")
    
    async def _baseline_update_loop(self):
        """Run periodic baseline updates from Mimir"""
        
        while self.running:
            try:
                logger.info("Updating baselines from Mimir...")
                
                baselines = await self.mimir_client.get_network_metrics_baselines(
                    target_hosts=self.config.monitoring.targets,
                    days_back=7
                )
                
                if baselines:
                    # Update AI detector baselines
                    for query, baseline in baselines.items():
                        # Store baseline update in database
                        await self.database.store_baseline_update({
                            'metric_name': query,
                            'baseline_type': baseline.baseline_type,
                            'new_value': baseline.values.get('overall_mean', 0),
                            'confidence': 0.8,
                            'source': 'mimir'
                        })
                    
                    self.performance_stats['baseline_updates'] += 1
                    logger.info(f"Updated {len(baselines)} baselines from Mimir")
                
                # Sleep for 6 hours
                await asyncio.sleep(21600)
                
            except Exception as e:
                logger.error(f"Error updating baselines: {e}")
                await asyncio.sleep(3600)  # Retry in 1 hour
    
    def _calculate_system_health(self) -> float:
        """Calculate overall system health score"""
        
        score = 100.0
        
        try:
            # Component health checks
            if not self.database:
                score -= 20
            
            if not self.enhanced_collector:
                score -= 20
            
            if not self.ai_detector:
                score -= 15
            
            if not self.metrics_server:
                score -= 10
            
            # Performance checks
            if self.performance_stats['average_collection_time'] > 30:
                score -= 10
            
            # System resource checks
            import psutil
            if psutil.virtual_memory().percent > 90:
                score -= 15
            
            if psutil.cpu_percent() > 90:
                score -= 15
            
            # Recent activity check
            if self.performance_stats['total_measurements'] == 0:
                score -= 25
            
        except Exception as e:
            logger.error(f"Error calculating system health: {e}")
            score = 50
        
        return max(0, score)
    
    def _log_final_performance_report(self):
        """Log final performance statistics"""
        
        uptime = time.time() - self.performance_stats['system_start_time']
        
        logger.info("=== Final Performance Report ===")
        logger.info(f"System Uptime: {uptime/3600:.2f} hours")
        logger.info(f"Total Measurements: {self.performance_stats['total_measurements']}")
        logger.info(f"Anomalies Detected: {self.performance_stats['anomalies_detected']}")
        logger.info(f"Alerts Sent: {self.performance_stats['alerts_sent']}")
        logger.info(f"Model Trainings: {self.performance_stats['model_trainings']}")
        logger.info(f"Baseline Updates: {self.performance_stats['baseline_updates']}")
        logger.info(f"Average Collection Time: {self.performance_stats['average_collection_time']:.2f}s")
        logger.info(f"Final Health Score: {self.performance_stats['system_health_score']:.1f}")
        logger.info("================================")

class EnhancedAPIServer(APIServer):
    """Enhanced API server with additional endpoints"""
    
    def __init__(self, config, database, detector, collector, mimir_client, 
                 metrics_server, alert_manager=None, threshold_manager=None):
        super().__init__(config, database, detector, collector)
        
        self.mimir_client = mimir_client
        self.metrics_server = metrics_server
        self.alert_manager = alert_manager
        self.threshold_manager = threshold_manager
        
        # Add enhanced routes
        self._setup_enhanced_routes()
    
    def _setup_enhanced_routes(self):
        """Setup additional enhanced routes"""
        
        from flask import jsonify
        import asyncio
        
        @self.app.route('/api/enhanced/status', methods=['GET'])
        def get_enhanced_status():
            """Get enhanced system status"""
            return jsonify({
                'system': 'Enhanced Network Intelligence Monitor',
                'version': '1.0.0',
                'integration': 'Alloy→Mimir',
                'components': {
                    'database': bool(self.database),
                    'collector': bool(self.collector),
                    'ai_detector': bool(self.detector),
                    'mimir_client': bool(self.mimir_client),
                    'metrics_server': bool(self.metrics_server),
                    'alert_manager': bool(self.alert_manager),
                    'threshold_manager': bool(self.threshold_manager)
                },
                'endpoints': {
                    'metrics_export': f'http://localhost:{self.config.get("metrics", {}).get("port", 8000)}/metrics',
                    'api_base': f'http://localhost:{self.config.get("api", {}).get("port", 5000)}/api',
                    'websocket': 'ws://localhost:8001/ws'
                }
            })
        
        @self.app.route('/api/integration/verify', methods=['GET'])
        def verify_integration():
            """Verify Alloy→Mimir integration"""
            return asyncio.run(self._verify_integration())
    
    async def _verify_integration(self):
        """Verify integration setup"""
        
        status = {
            'metrics_endpoint': False,
            'mimir_connectivity': False,
            'alloy_config_exists': False
        }
        
        # Check metrics endpoint
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                metrics_port = self.config.get('metrics', {}).get('port', 8000)
                async with session.get(f"http://localhost:{metrics_port}/metrics") as response:
                    if response.status == 200:
                        text = await response.text()
                        status['metrics_endpoint'] = 'network_' in text
        except:
            pass
        
        # Check Mimir
        if self.mimir_client:
            try:
                result = await self.mimir_client.test_connectivity()
                status['mimir_connectivity'] = result.get('mimir', {}).get('status') == 'connected'
            except:
                pass
        
        # Check Alloy config
        from pathlib import Path
        status['alloy_config_exists'] = Path("configs/alloy/alloy").exists()
        
        from flask import jsonify
        return jsonify({
            'status': status,
            'integration_ready': all(status.values()),
            'next_steps': self._get_integration_next_steps(status)
        })
    
    def _get_integration_next_steps(self, status):
        """Get next steps for integration setup"""
        
        steps = []
        
        if not status['metrics_endpoint']:
            steps.append("Ensure metrics server is running and accessible")
        
        if not status['mimir_connectivity']:
            steps.append("Configure Mimir URL and check connectivity")
        
        if not status['alloy_config_exists']:
            steps.append("Deploy Alloy configuration from configs/alloy/alloy")
        
        if all(status.values()):
            steps.append("Integration is complete! Monitor data flow in Mimir.")
        
        return steps

# Main execution
async def main():
    """Main function"""
    
    # Setup logging
    setup_logging()
    
    # Create enhanced monitor
    config_file = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    
    monitor = EnhancedNetworkIntelligenceMonitor(config_file)
    
    try:
        await monitor.initialize()
        await monitor.start()
        
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        if monitor.running:
            await monitor.stop()

if __name__ == "__main__":
    asyncio.run(main())

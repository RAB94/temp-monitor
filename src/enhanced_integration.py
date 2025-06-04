#!/usr/bin/env python3
"""
Enhanced Network Intelligence Monitor - Complete Integration
===========================================================

This module brings together all enhanced components into a cohesive system:
- LSTM Autoencoder AI Detection
- Mimir/Prometheus Integration  
- Enhanced Network Metrics Collection
- Prometheus Metrics Export for Alloy
- Intelligent Alerting
- Edge Device Optimization
- Dynamic Threshold Management
"""

import asyncio
import logging
import signal
import sys
import os
import time
import threading
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import asdict

# Import enhanced components
from src.collector import EnhancedNetworkCollector
from src.lstm_auto import EnhancedLSTMAnomalyDetector
from src.prom_int import MimirPrometheusClient, integrate_with_existing_detector
from src.prom_export import PrometheusMetricsServer, MetricsAggregator
from src.alerts import AlertManager, create_alert_manager
from src.dynamic_thresh import DynamicThresholdManager, setup_dynamic_thresholds
from src.edge_opt import EdgeOptimizer, create_edge_optimizer

# Import core components
from src.config import Config
from src.utils.database import Database
from src.utils.logger import setup_logging, get_network_logger, get_ai_logger
from src.utils.network import (
    NetworkInterfaceMonitor, NetworkTopologyDiscovery, 
    NetworkEnvironmentDetector, get_default_interface
)
from src.api.server import APIServer

logger = logging.getLogger(__name__)

class EnhancedNetworkIntelligenceMonitor:
    """Complete enhanced network intelligence monitoring system"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the enhanced monitor with configuration"""
        
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
        self.interface_monitor = None
        
        # Specialized loggers
        self.network_logger = get_network_logger()
        self.ai_logger = get_ai_logger()
        
        # Threading and monitoring
        self.main_loop_thread = None
        self.api_thread = None
        self.interface_monitor_thread = None
        self.baseline_update_thread = None
        
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
        
        logger.info("Initializing Enhanced Network Intelligence Monitor...")
        
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
            
            # Initialize Mimir/Prometheus integration
            await self._initialize_mimir_integration()
            
            # Initialize alerting system
            await self._initialize_alerting_system()
            
            # Initialize dynamic thresholds
            await self._initialize_dynamic_thresholds()
            
            # Initialize Prometheus metrics export
            await self._initialize_metrics_export()
            
            # Initialize API server
            await self._initialize_api_server()
            
            # Initialize interface monitoring
            await self._initialize_interface_monitoring()
            
            # Apply edge optimizations if needed
            await self._apply_edge_optimizations()
            
            # Setup health monitoring
            await self._setup_health_monitoring()
            
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
        
        # Validate network interfaces
        interfaces = self.config.get_network_interfaces()
        if interfaces:
            logger.info(f"Detected network interfaces: {[iface['name'] for iface in interfaces]}")
        else:
            logger.warning("No network interfaces detected")
    
    async def _detect_environment(self):
        """Detect deployment environment and apply optimizations"""
        
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
        """Initialize Mimir/Prometheus integration"""
        
        if not self.config.mimir.enabled:
            logger.info("Mimir integration disabled")
            return
        
        mimir_config = {
            'prometheus_url': self.config.mimir.prometheus_url,
            'mimir_url': self.config.mimir.mimir_url,
            'tenant_id': self.config.mimir.tenant_id,
            'timeout': 30,
            'cache_ttl_seconds': 300
        }
        
        self.mimir_client = MimirPrometheusClient(mimir_config)
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
    
    async def _initialize_dynamic_thresholds(self):
        """Initialize dynamic threshold management"""
        
        threshold_config = {
            'analysis_window_size': 1000,
            'adjustment_interval_seconds': 3600,
            'min_confidence': 0.3,
            'max_adjustment_factor': 0.2
        }
        
        self.threshold_manager = DynamicThresholdManager(threshold_config)
        
        # Initialize with default thresholds
        default_thresholds = {
            'icmp_ping_time': 100.0,
            'tcp_handshake_time': 200.0,
            'dns_resolve_time': 50.0,
            'packet_loss': 5.0,
            'jitter': 20.0,
            'http_response_time': 2000.0,
            'mos_score': 3.0
        }
        
        self.threshold_manager.initialize(default_thresholds)
        self.threshold_manager.start()
        
        logger.info("Dynamic threshold management initialized")
    
    async def _initialize_metrics_export(self):
        """Initialize Prometheus metrics export for Alloy"""
        
        metrics_config = {
            'metrics_port': self.config.metrics.port,
            'metrics_host': self.config.metrics.host,
            'metrics_batch_size': self.config.metrics.batch_size,
            'enable_aggregation': self.config.metrics.enable_aggregation
        }
        
        # Create metrics server
        self.metrics_server = PrometheusMetricsServer(
            port=metrics_config['metrics_port'],
            host=metrics_config['metrics_host']
        )
        self.metrics_server.start()
        
        # Create metrics aggregator for efficiency
        self.metrics_aggregator = MetricsAggregator(
            self.metrics_server,
            batch_size=metrics_config['metrics_batch_size']
        )
        self.metrics_aggregator.start()
        
        logger.info(f"Prometheus metrics server started on port {metrics_config['metrics_port']}")
    
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
    
    async def _initialize_interface_monitoring(self):
        """Initialize network interface monitoring"""
        
        self.interface_monitor = NetworkInterfaceMonitor()
        
        logger.info("Network interface monitoring initialized")
    
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
        
        self.edge_optimizer = create_edge_optimizer(edge_config)
        
        # Optimize AI model
        if self.ai_detector and self.ai_detector.model:
            optimized_model = self.edge_optimizer.optimize_for_edge(
                model=self.ai_detector.model
            )
            self.ai_detector.model = optimized_model
        
        logger.info("Edge optimizations applied")
    
    async def _setup_health_monitoring(self):
        """Setup comprehensive health monitoring"""
        
        # This will be handled in the main monitoring loop
        logger.info("Health monitoring configured")
    
    def start(self):
        """Start the enhanced monitoring system"""
        
        logger.info("Starting Enhanced Network Intelligence Monitor...")
        
        if self.running:
            logger.warning("Monitor already running")
            return
        
        self.running = True
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        # Start main monitoring loop
        self.main_loop_thread = threading.Thread(
            target=self._run_main_loop, daemon=True
        )
        self.main_loop_thread.start()
        
        # Start API server
        self.api_thread = threading.Thread(
            target=self._run_api_server, daemon=True
        )
        self.api_thread.start()
        
        # Start interface monitoring
        self.interface_monitor_thread = threading.Thread(
            target=self._run_interface_monitoring, daemon=True
        )
        self.interface_monitor_thread.start()
        
        # Start baseline updates if Mimir is enabled
        if self.mimir_client:
            self.baseline_update_thread = threading.Thread(
                target=self._run_baseline_updates, daemon=True
            )
            self.baseline_update_thread.start()
        
        logger.info("Enhanced Network Intelligence Monitor started successfully")
        logger.info("=== System Status ===")
        logger.info(f"API Server: http://0.0.0.0:{self.config.api.port}")
        logger.info(f"Metrics Export: http://0.0.0.0:{self.config.metrics.port}/metrics")
        logger.info(f"Targets: {', '.join(self.config.monitoring.targets)}")
        logger.info(f"AI Detection: {'Enabled' if self.ai_detector else 'Disabled'}")
        logger.info(f"Mimir Integration: {'Enabled' if self.mimir_client else 'Disabled'}")
        logger.info(f"Edge Optimization: {'Enabled' if self.edge_optimizer else 'Disabled'}")
        logger.info("=====================")
    
    def stop(self):
        """Stop the enhanced monitoring system"""
        
        logger.info("Stopping Enhanced Network Intelligence Monitor...")
        
        self.running = False
        
        # Stop components
        if self.threshold_manager:
            self.threshold_manager.stop()
        
        if self.alert_manager:
            self.alert_manager.stop()
        
        if self.metrics_aggregator:
            self.metrics_aggregator.stop()
        
        if self.metrics_server:
            self.metrics_server.stop()
        
        # Close async components
        if self.enhanced_collector:
            asyncio.run(self.enhanced_collector.close())
        
        if self.mimir_client:
            asyncio.run(self.mimir_client.close())
        
        if self.database:
            asyncio.run(self.database.close())
        
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
        
        # Wait for threads to finish
        threads = [
            self.main_loop_thread,
            self.api_thread,
            self.interface_monitor_thread,
            self.baseline_update_thread
        ]
        
        for thread in threads:
            if thread and thread.is_alive():
                thread.join(timeout=5)
        
        # Final performance report
        self._log_final_performance_report()
        
        logger.info("Enhanced Network Intelligence Monitor stopped")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, signal_handler)
    
    def _run_main_loop(self):
        """Main monitoring loop with all enhancements"""
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
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
                        metrics = loop.run_until_complete(
                            self.enhanced_collector.collect_enhanced_metrics(target)
                        )
                        
                        if metrics:
                            # Store in database
                            loop.run_until_complete(
                                self.database.store_metrics(metrics.to_dict())
                            )
                            
                            # Update Prometheus metrics
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
                                anomaly_result = loop.run_until_complete(
                                    self.ai_detector.detect_anomaly(metrics)
                                )
                                
                                if anomaly_result.is_anomaly:
                                    self.network_logger.log_anomaly_detected(
                                        target,
                                        anomaly_result.anomaly_score,
                                        anomaly_result.confidence,
                                        severity=anomaly_result.severity
                                    )
                                    
                                    # Store anomaly
                                    loop.run_until_complete(
                                        self.database.store_anomaly(
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
                                    )
                                    
                                    # Send alert
                                    if self.alert_manager:
                                        loop.run_until_complete(
                                            self.alert_manager.create_alert(
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
                                        )
                                        self.performance_stats['alerts_sent'] += 1
                                    
                                    # Update metrics
                                    if self.metrics_aggregator:
                                        self.metrics_aggregator.add_anomaly_metrics(
                                            anomaly_result, target
                                        )
                                    
                                    self.performance_stats['anomalies_detected'] += 1
                            
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
                        training_data = loop.run_until_complete(
                            self.database.get_metrics_for_training(hours=24)
                        )
                        
                        if len(training_data) >= 50:
                            training_start = time.time()
                            
                            loop.run_until_complete(
                                self.ai_detector.train_online(training_data)
                            )
                            
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
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Error in main monitoring loop: {e}")
                time.sleep(60)  # Error backoff
        
        loop.close()
        logger.info("Main monitoring loop stopped")
    
    def _run_api_server(self):
        """Run API server"""
        
        try:
            self.api_server.run(
                host=self.config.api.host,
                port=self.config.api.port,
                debug=self.config.api.debug
            )
        except Exception as e:
            logger.error(f"API server error: {e}")
    
    def _run_interface_monitoring(self):
        """Run interface monitoring"""
        
        while self.running:
            try:
                interfaces = self.interface_monitor.get_all_interfaces()
                
                # Update interface metrics
                interface_stats = {}
                for name, interface in interfaces.items():
                    utilization = self.interface_monitor.get_interface_utilization(name)
                    
                    interface_stats[name] = {
                        'utilization': utilization.get('rx_utilization', 0) + utilization.get('tx_utilization', 0),
                        'errors_in': interface.statistics.get('errin', 0),
                        'errors_out': interface.statistics.get('errout', 0),
                        'drops_in': interface.statistics.get('dropin', 0),
                        'drops_out': interface.statistics.get('dropout', 0)
                    }
                
                # Update Prometheus metrics
                if self.metrics_aggregator:
                    for name, stats in interface_stats.items():
                        self.metrics_aggregator.add_interface_metrics(name, stats)
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in interface monitoring: {e}")
                time.sleep(60)
    
    def _run_baseline_updates(self):
        """Run periodic baseline updates from Mimir"""
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self.running:
            try:
                logger.info("Updating baselines from Mimir...")
                
                baselines = loop.run_until_complete(
                    self.mimir_client.get_network_metrics_baselines(
                        target_hosts=self.config.monitoring.targets,
                        days_back=7
                    )
                )
                
                if baselines:
                    # Update AI detector baselines
                    for query, baseline in baselines.items():
                        # Store baseline update in database
                        loop.run_until_complete(
                            self.database.store_baseline_update({
                                'metric_name': query,
                                'baseline_type': baseline.baseline_type,
                                'new_value': baseline.values.get('overall_mean', 0),
                                'confidence': 0.8,
                                'source': 'mimir'
                            })
                        )
                    
                    self.performance_stats['baseline_updates'] += 1
                    logger.info(f"Updated {len(baselines)} baselines from Mimir")
                
                # Sleep for 6 hours
                time.sleep(21600)
                
            except Exception as e:
                logger.error(f"Error updating baselines: {e}")
                time.sleep(3600)  # Retry in 1 hour
        
        loop.close()
    
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
        
        @self.app.route('/api/enhanced/status', methods=['GET'])
        def get_enhanced_status():
            """Get enhanced system status"""
            return self._get_enhanced_status()
        
        @self.app.route('/api/enhanced/performance', methods=['GET'])
        def get_performance_stats():
            """Get performance statistics"""
            return self._get_performance_statistics()
        
        @self.app.route('/api/enhanced/baselines', methods=['GET'])
        def get_enhanced_baselines():
            """Get enhanced baselines from Mimir"""
            return asyncio.run(self._get_enhanced_baselines())
        
        @self.app.route('/api/enhanced/alerts', methods=['GET'])
        def get_enhanced_alerts():
            """Get enhanced alert information"""
            return self._get_enhanced_alerts()
        
        @self.app.route('/api/enhanced/thresholds', methods=['GET'])
        def get_dynamic_thresholds():
            """Get current dynamic thresholds"""
            return self._get_dynamic_thresholds()
        
        @self.app.route('/api/enhanced/interfaces', methods=['GET'])
        def get_network_interfaces():
            """Get network interface information"""
            return self._get_network_interfaces()
    
    def _get_enhanced_status(self):
        """Get enhanced system status"""
        
        status = {
            'system': 'Enhanced Network Intelligence Monitor',
            'version': '1.0.0',
            'components': {
                'database': bool(self.database),
                'collector': bool(self.collector),
                'ai_detector': bool(self.detector),
                'mimir_client': bool(self.mimir_client),
                'metrics_server': bool(self.metrics_server),
                'alert_manager': bool(self.alert_manager),
                'threshold_manager': bool(self.threshold_manager)
            },
            'features': {
                'enhanced_metrics': True,
                'ai_anomaly_detection': bool(self.detector),
                'historical_baselines': bool(self.mimir_client),
                'dynamic_thresholds': bool(self.threshold_manager),
                'intelligent_alerting': bool(self.alert_manager),
                'prometheus_export': bool(self.metrics_server)
            }
        }
        
        return jsonify(status)

# Utility functions

def create_example_config():
    """Create example configuration file"""
    
    config = {
        'logging': {
            'level': 'INFO',
            'file': 'data/logs/network_intelligence.log',
            'max_size_mb': 10,
            'backup_count': 5,
            'console_enabled': True,
            'json_format': False
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
            'prometheus_url': os.getenv('PROMETHEUS_URL'),
            'mimir_url': os.getenv('MIMIR_URL'),
            'tenant_id': 'network-monitoring',
            'enabled': bool(os.getenv('MIMIR_URL') or os.getenv('PROMETHEUS_URL'))
        },
        'alerts': {
            'enabled': True,
            'webhook_url': os.getenv('WEBHOOK_URL'),
            'email_enabled': False
        },
        'deployment': {
            'edge_optimization': False,
            'quantize_models': False,
            'reduce_memory_usage': False,
            'max_memory_mb': 512
        }
    }
    
    with open("config-enhanced.yaml", "w") as f:
        yaml.dump(config, f, default_flow_style=False, indent=2)
    
    logger.info("Example configuration created: config-enhanced.yaml")

def create_deployment_scripts():
    """Create deployment scripts"""
    
    # Environment setup script
    setup_script = '''#!/bin/bash
# Enhanced Network Intelligence Monitor - Environment Setup

set -e

echo "Setting up Enhanced Network Intelligence Monitor..."

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# Create necessary directories
mkdir -p data/logs data/models data/database data/exports

# Set permissions
chmod +x scripts/*.sh

echo "Environment setup complete!"
echo ""
echo "To activate the virtual environment:"
echo "  source venv/bin/activate"
echo ""
echo "To start the monitor:"
echo "  python -m src.main"
'''
    
    # Raspberry Pi optimization script
    pi_script = '''#!/bin/bash
# Raspberry Pi Optimization Script

set -e

echo "Optimizing for Raspberry Pi deployment..."

# Install system dependencies
sudo apt-get update
sudo apt-get install -y python3-dev python3-pip python3-venv
sudo apt-get install -y build-essential libatlas-base-dev

# Install optimized PyTorch for Pi
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Set environment variables for edge deployment
export DEPLOYMENT_TYPE=edge
export PYTORCH_JIT=0
export OMP_NUM_THREADS=4

# Create optimized config
cat > config-pi.yaml << EOF
deployment:
  edge_optimization: true
  quantize_models: true
  reduce_memory_usage: true
  max_memory_mb: 256

monitoring:
  interval: 60
  timeout: 15
  targets: ['8.8.8.8', '1.1.1.1']

ai:
  train_interval: 7200
  initial_epochs: 50
  baseline_window: 500
EOF

echo "Raspberry Pi optimization complete!"
'''
    
    # Create scripts directory and files
    scripts_dir = Path("scripts")
    scripts_dir.mkdir(exist_ok=True)
    
    with open(scripts_dir / "setup_environment.sh", "w") as f:
        f.write(setup_script)
    
    with open(scripts_dir / "optimize_pi.sh", "w") as f:
        f.write(pi_script)
    
    # Make scripts executable
    import stat
    for script in scripts_dir.glob("*.sh"):
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
    
    logger.info("Deployment scripts created in scripts/ directory")

# Main execution
async def main():
    """Main function"""
    
    # Setup logging
    setup_logging()
    
    # Create example config if it doesn't exist
    if not Path("config-enhanced.yaml").exists():
        create_example_config()
    
    # Create deployment scripts
    create_deployment_scripts()
    
    # Create and run monitor
    config_file = sys.argv[1] if len(sys.argv) > 1 else "config-enhanced.yaml"
    
    monitor = EnhancedNetworkIntelligenceMonitor(config_file)
    
    try:
        await monitor.initialize()
        monitor.start()
        
        # Keep running until interrupted
        while monitor.running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        monitor.stop()

if __name__ == "__main__":
    asyncio.run(main())

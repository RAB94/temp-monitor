#!/usr/bin/env python3
"""
Enhanced System Integration Module
=================================

Integrates all enhanced components with the existing Network Intelligence Monitor:
- Enhanced LSTM anomaly detector
- Mimir/Prometheus historical baseline integration
- Enhanced network metrics collector
- Prometheus metrics exporter for Alloy
- Intelligent alerting system
- Edge device optimization
"""

import asyncio
import logging
import time
import threading
from typing import Dict, Any, Optional
from pathlib import Path
import json

# Import enhanced components
from enhanced_lstm_detector import EnhancedLSTMAnomalyDetector
from mimir_integration import MimirPrometheusClient, integrate_with_existing_detector
from enhanced_network_collector import EnhancedNetworkCollector
from prometheus_metrics_exporter import (
    PrometheusMetricsServer, MetricsAggregator, 
    create_metrics_server, create_metrics_aggregator
)

# Import original system components
from src.config import Config
from src.utils.database import Database
from src.utils.logger import setup_logging
from src.api.server import APIServer

logger = logging.getLogger(__name__)

class EnhancedNetworkIntelligenceMonitor:
    """Enhanced Network Intelligence Monitor with all improvements"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = Config(config_path)
        self.running = False
        
        # Core components
        self.database = None
        self.enhanced_collector = None
        self.enhanced_detector = None
        self.mimir_client = None
        self.api_server = None
        
        # Metrics and monitoring
        self.metrics_server = None
        self.metrics_aggregator = None
        
        # Threading
        self.monitor_thread = None
        self.api_thread = None
        self.baseline_update_thread = None
        
        # Performance tracking
        self.performance_metrics = {
            'collections_per_minute': 0,
            'anomalies_detected': 0,
            'baseline_updates': 0,
            'system_health_score': 100.0
        }
        
        logger.info("Enhanced Network Intelligence Monitor initialized")
    
    async def initialize(self):
        """Initialize all enhanced components"""
        
        logger.info("Initializing Enhanced Network Intelligence Monitor...")
        
        try:
            # Initialize database
            await self._initialize_database()
            
            # Initialize enhanced network collector
            await self._initialize_enhanced_collector()
            
            # Initialize enhanced AI detector
            await self._initialize_enhanced_detector()
            
            # Initialize Mimir integration
            await self._initialize_mimir_integration()
            
            # Initialize metrics exporter
            await self._initialize_metrics_exporter()
            
            # Initialize API server with enhancements
            await self._initialize_enhanced_api()
            
            # Setup component health monitoring
            await self._setup_health_monitoring()
            
            logger.info("Enhanced Network Intelligence Monitor initialization complete")
            
        except Exception as e:
            logger.error(f"Failed to initialize enhanced monitor: {e}")
            raise
    
    async def _initialize_database(self):
        """Initialize database with enhanced schema"""
        
        self.database = Database(self.config.database_path)
        await self.database.initialize()
        
        # Add enhanced metrics tables if needed
        await self._setup_enhanced_database_schema()
        
        logger.info("Enhanced database initialized")
    
    async def _setup_enhanced_database_schema(self):
        """Setup additional database tables for enhanced metrics"""
        
        try:
            # Add enhanced metrics table
            await self.database.db.execute("""
                CREATE TABLE IF NOT EXISTS enhanced_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    target_host TEXT,
                    
                    -- Enhanced latency metrics
                    tcp_connect_time REAL,
                    tcp_ssl_handshake_time REAL,
                    http_response_time REAL,
                    http_first_byte_time REAL,
                    
                    -- Quality metrics
                    burst_loss_rate REAL,
                    out_of_order_packets REAL,
                    duplicate_packets REAL,
                    delay_variation REAL,
                    
                    -- Throughput metrics
                    bandwidth_download REAL,
                    bandwidth_upload REAL,
                    concurrent_connections INTEGER,
                    connection_setup_rate REAL,
                    
                    -- Application metrics
                    http_status_code INTEGER,
                    http_content_length INTEGER,
                    certificate_days_remaining INTEGER,
                    redirect_count INTEGER,
                    
                    -- Interface metrics
                    interface_utilization REAL,
                    interface_errors INTEGER,
                    interface_drops INTEGER,
                    interface_collisions INTEGER,
                    
                    -- Path metrics
                    hop_count INTEGER,
                    path_mtu INTEGER,
                    route_changes INTEGER,
                    
                    -- Quality scores
                    mos_score REAL,
                    r_factor REAL,
                    
                    -- Metadata
                    source_interface TEXT,
                    network_type TEXT,
                    measurement_duration REAL,
                    
                    created_at REAL DEFAULT (strftime('%s', 'now'))
                )
            """)
            
            # Add AI model performance tracking table
            await self.database.db.execute("""
                CREATE TABLE IF NOT EXISTS ai_model_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    model_type TEXT,
                    accuracy REAL,
                    precision REAL,
                    recall REAL,
                    f1_score REAL,
                    training_samples INTEGER,
                    inference_time_ms REAL,
                    memory_usage_mb REAL,
                    created_at REAL DEFAULT (strftime('%s', 'now'))
                )
            """)
            
            # Add baseline tracking table
            await self.database.db.execute("""
                CREATE TABLE IF NOT EXISTS baseline_updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    metric_name TEXT,
                    baseline_type TEXT,
                    old_value REAL,
                    new_value REAL,
                    confidence REAL,
                    source TEXT,
                    created_at REAL DEFAULT (strftime('%s', 'now'))
                )
            """)
            
            # Create indexes for performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_enhanced_metrics_timestamp ON enhanced_metrics(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_enhanced_metrics_target ON enhanced_metrics(target_host)",
                "CREATE INDEX IF NOT EXISTS idx_ai_performance_timestamp ON ai_model_performance(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_baseline_updates_timestamp ON baseline_updates(timestamp)"
            ]
            
            for index_sql in indexes:
                await self.database.db.execute(index_sql)
            
            await self.database.db.commit()
            
            logger.info("Enhanced database schema created")
            
        except Exception as e:
            logger.error(f"Failed to setup enhanced database schema: {e}")
    
    async def _initialize_enhanced_collector(self):
        """Initialize enhanced network collector"""
        
        collector_config = {
            'targets': self.config.get('monitoring.targets', ['8.8.8.8', '1.1.1.1', 'google.com']),
            'timeout': self.config.get('monitoring.timeout', 10),
            'enhanced_features': True,
            'quality_metrics': True,
            'path_analysis': True
        }
        
        self.enhanced_collector = EnhancedNetworkCollector(collector_config)
        await self.enhanced_collector.initialize()
        
        logger.info("Enhanced network collector initialized")
    
    async def _initialize_enhanced_detector(self):
        """Initialize enhanced LSTM anomaly detector"""
        
        detector_config = {
            'model_dir': self.config.get('ai.model_dir', 'data/models'),
            'sequence_length': 20,
            'input_size': 10,
            'hidden_size': 64,
            'num_layers': 2,
            'initial_epochs': self.config.get('ai.initial_epochs', 100),
            'enable_quantization': True  # Enable for edge deployment
        }
        
        self.enhanced_detector = EnhancedLSTMAnomalyDetector(detector_config)
        await self.enhanced_detector.initialize()
        
        # Try to load existing models
        try:
            self.enhanced_detector.load_models()
            logger.info("Loaded existing enhanced AI models")
        except FileNotFoundError:
            logger.info("No existing enhanced models found, will train from scratch")
        
        logger.info("Enhanced LSTM detector initialized")
    
    async def _initialize_mimir_integration(self):
        """Initialize Mimir/Prometheus integration"""
        
        mimir_config = {
            'prometheus_url': self.config.get('mimir.prometheus_url'),
            'mimir_url': self.config.get('mimir.mimir_url'),
            'tenant_id': self.config.get('mimir.tenant_id', 'network-monitoring'),
            'timeout': 30,
            'cache_ttl_seconds': 300
        }
        
        # Only initialize if Mimir/Prometheus is configured
        if mimir_config['prometheus_url'] or mimir_config['mimir_url']:
            self.mimir_client = MimirPrometheusClient(mimir_config)
            await self.mimir_client.initialize()
            
            # Integrate with enhanced detector
            await integrate_with_existing_detector(
                self.enhanced_detector, 
                self.mimir_client,
                target_hosts=self.config.get('monitoring.targets'),
                days_back=30
            )
            
            logger.info("Mimir integration initialized")
        else:
            logger.info("Mimir integration skipped - no endpoints configured")
    
    async def _initialize_metrics_exporter(self):
        """Initialize Prometheus metrics exporter"""
        
        metrics_config = {
            'metrics_port': self.config.get('metrics.port', 8000),
            'metrics_host': self.config.get('metrics.host', '0.0.0.0'),
            'metrics_batch_size': 10,
            'enable_aggregation': True
        }
        
        # Create metrics server
        self.metrics_server = create_metrics_server(metrics_config)
        self.metrics_server.start()
        
        # Create metrics aggregator for efficiency
        self.metrics_aggregator = create_metrics_aggregator(
            self.metrics_server, metrics_config
        )
        self.metrics_aggregator.start()
        
        logger.info(f"Prometheus metrics server started on port {metrics_config['metrics_port']}")
    
    async def _initialize_enhanced_api(self):
        """Initialize enhanced API server"""
        
        # Create enhanced API server with additional endpoints
        self.api_server = EnhancedAPIServer(
            self.config.api,
            self.database,
            self.enhanced_detector,
            self.enhanced_collector,
            self.mimir_client,
            self.metrics_server
        )
        
        logger.info("Enhanced API server initialized")
    
    async def _setup_health_monitoring(self):
        """Setup component health monitoring"""
        
        # Start health monitoring thread
        def health_monitor():
            while self.running:
                try:
                    health_score = self._calculate_system_health()
                    self.performance_metrics['system_health_score'] = health_score
                    
                    # Update metrics
                    if self.metrics_server:
                        self.metrics_server.metrics.collector_health_status.labels(
                            component='system'
                        ).state('healthy' if health_score > 80 else 'degraded')
                    
                    time.sleep(60)  # Check every minute
                    
                except Exception as e:
                    logger.error(f"Health monitoring error: {e}")
                    time.sleep(60)
        
        self.health_thread = threading.Thread(target=health_monitor, daemon=True)
        
        logger.info("Health monitoring setup complete")
    
    def start(self):
        """Start the enhanced monitoring system"""
        
        logger.info("Starting Enhanced Network Intelligence Monitor...")
        
        self.running = True
        
        # Start health monitoring
        if hasattr(self, 'health_thread'):
            self.health_thread.start()
        
        # Start enhanced monitoring loop
        self.monitor_thread = threading.Thread(target=self._enhanced_monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        # Start API server
        self.api_thread = threading.Thread(target=self._api_server_loop, daemon=True)
        self.api_thread.start()
        
        # Start baseline update loop
        self.baseline_update_thread = threading.Thread(target=self._baseline_update_loop, daemon=True)
        self.baseline_update_thread.start()
        
        logger.info("Enhanced Network Intelligence Monitor started")
        
        # Wait for shutdown signal
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
            self.stop()
    
    def stop(self):
        """Stop the enhanced monitoring system"""
        
        logger.info("Stopping Enhanced Network Intelligence Monitor...")
        
        self.running = False
        
        # Stop components
        if self.metrics_aggregator:
            self.metrics_aggregator.stop()
        
        if self.metrics_server:
            self.metrics_server.stop()
        
        if self.enhanced_collector:
            asyncio.run(self.enhanced_collector.close())
        
        if self.mimir_client:
            asyncio.run(self.mimir_client.close())
        
        # Save AI models
        if self.enhanced_detector:
            try:
                self.enhanced_detector.save_models()
                
                # Quantize for edge deployment
                if self.config.get('deployment.edge_optimization', False):
                    self.enhanced_detector.quantize_for_edge()
                
                logger.info("Enhanced AI models saved")
            except Exception as e:
                logger.warning(f"Failed to save enhanced models: {e}")
        
        # Wait for threads
        for thread in [self.monitor_thread, self.api_thread, self.baseline_update_thread]:
            if thread and thread.is_alive():
                thread.join(timeout=5)
        
        logger.info("Enhanced Network Intelligence Monitor stopped")
    
    def _enhanced_monitoring_loop(self):
        """Enhanced monitoring loop with all improvements"""
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        last_train_time = 0
        train_interval = self.config.ai.get('train_interval', 3600)
        collections_count = 0
        
        while self.running:
            try:
                start_time = time.time()
                
                # Collect enhanced metrics
                for target in self.config.monitoring.get('targets', ['8.8.8.8']):
                    enhanced_metrics = loop.run_until_complete(
                        self.enhanced_collector.collect_enhanced_metrics(target)
                    )
                    
                    if enhanced_metrics:
                        # Store in database
                        loop.run_until_complete(
                            self._store_enhanced_metrics(enhanced_metrics)
                        )
                        
                        # Update Prometheus metrics
                        if self.metrics_aggregator:
                            self.metrics_aggregator.add_enhanced_metrics(enhanced_metrics)
                        
                        # AI anomaly detection
                        anomaly_result = loop.run_until_complete(
                            self.enhanced_detector.detect_anomaly(enhanced_metrics)
                        )
                        
                        if anomaly_result.is_anomaly:
                            logger.warning(f"Enhanced anomaly detected: {anomaly_result.recommendation}")
                            
                            # Store enhanced anomaly
                            loop.run_until_complete(
                                self._store_enhanced_anomaly(enhanced_metrics.timestamp, anomaly_result)
                            )
                            
                            # Update anomaly metrics
                            if self.metrics_aggregator:
                                self.metrics_aggregator.add_anomaly_metrics(anomaly_result, target)
                            
                            self.performance_metrics['anomalies_detected'] += 1
                        
                        collections_count += 1
                
                # Update performance metrics
                cycle_time = time.time() - start_time
                self.performance_metrics['collections_per_minute'] = (
                    collections_count / max(1, cycle_time / 60)
                )
                
                # Periodic training
                current_time = time.time()
                if current_time - last_train_time > train_interval:
                    logger.info("Starting enhanced periodic training...")
                    loop.run_until_complete(self._enhanced_periodic_training())
                    last_train_time = current_time
                
                # Sleep until next collection
                interval = self.config.monitoring.get('interval', 30)
                time.sleep(max(1, interval - cycle_time))
                
            except Exception as e:
                logger.error(f"Error in enhanced monitoring loop: {e}")
                time.sleep(60)
        
        loop.close()
    
    async def _store_enhanced_metrics(self, metrics):
        """Store enhanced metrics in database"""
        
        try:
            # Convert to dictionary and store
            metrics_dict = metrics.to_dict()
            
            # Store in enhanced metrics table
            placeholders = ', '.join(['?' for _ in metrics_dict.keys()])
            columns = ', '.join(metrics_dict.keys())
            values = list(metrics_dict.values())
            
            await self.database.db.execute(
                f"INSERT INTO enhanced_metrics ({columns}) VALUES ({placeholders})",
                values
            )
            
            await self.database.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to store enhanced metrics: {e}")
    
    async def _store_enhanced_anomaly(self, timestamp: float, anomaly_result):
        """Store enhanced anomaly result"""
        
        try:
            await self.database.db.execute("""
                INSERT INTO anomalies (
                    timestamp, anomaly_score, confidence, is_critical,
                    baseline_values, thresholds, feature_scores, recommendation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                anomaly_result.anomaly_score,
                anomaly_result.confidence,
                anomaly_result.severity in ['critical', 'high'],
                json.dumps(anomaly_result.baseline_values),
                json.dumps(anomaly_result.thresholds),
                json.dumps(anomaly_result.feature_contributions),
                anomaly_result.recommendation
            ))
            
            await self.database.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to store enhanced anomaly: {e}")
    
    async def _enhanced_periodic_training(self):
        """Enhanced periodic training with performance tracking"""
        
        try:
            start_time = time.time()
            
            # Get recent training data
            hours_back = self.config.ai.get('training_hours', 24)
            
            # Get enhanced metrics for training
            training_data = await self.database.db.execute(
                "SELECT * FROM enhanced_metrics WHERE timestamp > ? ORDER BY timestamp",
                (time.time() - hours_back * 3600,)
            ).fetchall()
            
            if len(training_data) > 50:
                # Convert to format expected by detector
                training_metrics = []
                for row in training_data:
                    metrics_dict = dict(row)
                    training_metrics.append(metrics_dict)
                
                # Perform online training
                await self.enhanced_detector.train_online(training_metrics)
                
                training_time = time.time() - start_time
                
                # Store training performance
                await self.database.db.execute("""
                    INSERT INTO ai_model_performance (
                        timestamp, model_type, training_samples, inference_time_ms
                    ) VALUES (?, ?, ?, ?)
                """, (
                    time.time(),
                    'enhanced_lstm_autoencoder',
                    len(training_metrics),
                    training_time * 1000
                ))
                
                await self.database.db.commit()
                
                logger.info(f"Enhanced model trained on {len(training_metrics)} samples in {training_time:.2f}s")
                
                self.performance_metrics['baseline_updates'] += 1
            else:
                logger.debug("Insufficient data for enhanced training")
                
        except Exception as e:
            logger.error(f"Error in enhanced periodic training: {e}")
    
    def _baseline_update_loop(self):
        """Background loop for updating baselines from Mimir"""
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self.running:
            try:
                if self.mimir_client:
                    # Update baselines every 6 hours
                    logger.info("Updating baselines from Mimir...")
                    
                    baselines = loop.run_until_complete(
                        self.mimir_client.get_network_metrics_baselines(
                            target_hosts=self.config.monitoring.get('targets'),
                            days_back=7
                        )
                    )
                    
                    if baselines:
                        # Update detector baselines
                        for query, baseline in baselines.items():
                            # Store baseline update
                            loop.run_until_complete(
                                self.database.db.execute("""
                                    INSERT INTO baseline_updates (
                                        timestamp, metric_name, baseline_type, 
                                        new_value, confidence, source
                                    ) VALUES (?, ?, ?, ?, ?, ?)
                                """, (
                                    time.time(),
                                    query,
                                    baseline.baseline_type,
                                    baseline.values.get('overall_mean', 0),
                                    0.8,
                                    'mimir'
                                ))
                            )
                        
                        await self.database.db.commit()
                        logger.info(f"Updated {len(baselines)} baselines from Mimir")
                
                # Sleep for 6 hours
                time.sleep(21600)
                
            except Exception as e:
                logger.error(f"Error in baseline update loop: {e}")
                time.sleep(3600)  # Retry in 1 hour
        
        loop.close()
    
    def _api_server_loop(self):
        """Enhanced API server loop"""
        
        try:
            self.api_server.run()
        except Exception as e:
            logger.error(f"Enhanced API server error: {e}")
    
    def _calculate_system_health(self) -> float:
        """Calculate overall system health score"""
        
        score = 100.0
        
        try:
            # Check component health
            components = [
                ('database', self.database),
                ('collector', self.enhanced_collector),
                ('detector', self.enhanced_detector),
                ('metrics_server', self.metrics_server)
            ]
            
            for name, component in components:
                if component is None:
                    score -= 20
                    logger.warning(f"Component {name} is not initialized")
            
            # Check performance metrics
            if self.performance_metrics['collections_per_minute'] < 1:
                score -= 15
            
            # Check recent anomalies (too many is bad)
            recent_anomalies = self.performance_metrics['anomalies_detected']
            if recent_anomalies > 10:
                score -= min(20, recent_anomalies - 10)
            
            # Memory and CPU checks (simplified)
            import psutil
            if psutil.virtual_memory().percent > 90:
                score -= 10
            if psutil.cpu_percent() > 90:
                score -= 10
            
        except Exception as e:
            logger.error(f"Error calculating system health: {e}")
            score = 50  # Degraded state if can't calculate
        
        return max(0, score)

class EnhancedAPIServer(APIServer):
    """Enhanced API server with additional endpoints"""
    
    def __init__(self, config, database, detector, collector, mimir_client, metrics_server):
        super().__init__(config, database, detector)
        self.enhanced_collector = collector
        self.mimir_client = mimir_client
        self.metrics_server = metrics_server
        
        # Add enhanced routes
        self._setup_enhanced_routes()
    
    def _setup_enhanced_routes(self):
        """Setup additional API routes for enhanced features"""
        
        @self.app.route('/api/enhanced/metrics/current', methods=['GET'])
        def get_current_enhanced_metrics():
            return asyncio.run(self._get_current_enhanced_metrics())
        
        @self.app.route('/api/enhanced/baselines', methods=['GET'])
        def get_enhanced_baselines():
            return asyncio.run(self._get_enhanced_baselines())
        
        @self.app.route('/api/enhanced/health', methods=['GET'])
        def get_enhanced_health():
            return self._get_enhanced_health()
        
        @self.app.route('/api/enhanced/performance', methods=['GET'])
        def get_performance_metrics():
            return self._get_performance_metrics()
        
        @self.app.route('/api/enhanced/test', methods=['POST'])
        def trigger_enhanced_test():
            return asyncio.run(self._trigger_enhanced_test())
        
        @self.app.route('/api/metrics/prometheus', methods=['GET'])
        def get_prometheus_metrics():
            """Return Prometheus metrics (for debugging)"""
            try:
                if self.metrics_server:
                    metrics_text = self.metrics_server.metrics.get_metrics_text()
                    return Response(metrics_text, mimetype='text/plain')
                else:
                    return jsonify({'error': 'Metrics server not available'}), 503
            except Exception as e:
                return jsonify({'error': str(e)}), 500
    
    async def _get_current_enhanced_metrics(self):
        """Get current enhanced metrics"""
        
        try:
            if not self.enhanced_collector:
                return jsonify({'error': 'Enhanced collector not available'}), 503
            
            # Get metrics from primary target
            target = self.config.get('monitoring.targets', ['8.8.8.8'])[0]
            metrics = await self.enhanced_collector.collect_enhanced_metrics(target)
            
            if metrics:
                return jsonify({
                    'status': 'success',
                    'metrics': metrics.to_dict(),
                    'timestamp': time.time()
                })
            else:
                return jsonify({'error': 'Failed to collect enhanced metrics'}), 500
                
        except Exception as e:
            logger.error(f"Error getting current enhanced metrics: {e}")
            return jsonify({'error': str(e)}), 500
    
    async def _get_enhanced_baselines(self):
        """Get enhanced baselines from Mimir"""
        
        try:
            if not self.mimir_client:
                return jsonify({'error': 'Mimir client not available'}), 503
            
            targets = self.config.get('monitoring.targets', ['8.8.8.8'])
            baselines = await self.mimir_client.get_network_metrics_baselines(targets, days_back=7)
            
            # Format for API response
            formatted_baselines = {}
            for query, baseline in baselines.items():
                formatted_baselines[query] = {
                    'metric_name': baseline.metric_name,
                    'baseline_type': baseline.baseline_type,
                    'time_period': baseline.time_period,
                    'values': baseline.values,
                    'seasonal_patterns': baseline.seasonal_patterns,
                    'last_updated': baseline.last_updated
                }
            
            return jsonify({
                'status': 'success',
                'baselines': formatted_baselines,
                'count': len(formatted_baselines)
            })
            
        except Exception as e:
            logger.error(f"Error getting enhanced baselines: {e}")
            return jsonify({'error': str(e)}), 500
    
    def _get_enhanced_health(self):
        """Get enhanced system health"""
        
        try:
            health_data = {
                'overall_status': 'healthy',
                'components': {},
                'performance_metrics': {},
                'system_resources': {}
            }
            
            # Component health
            components = [
                ('database', self.database),
                ('enhanced_collector', self.enhanced_collector),
                ('enhanced_detector', self.detector),
                ('mimir_client', self.mimir_client),
                ('metrics_server', self.metrics_server)
            ]
            
            for name, component in components:
                health_data['components'][name] = {
                    'status': 'healthy' if component else 'unavailable',
                    'initialized': component is not None
                }
            
            # System resources
            import psutil
            health_data['system_resources'] = {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
            }
            
            # Determine overall status
            cpu_ok = health_data['system_resources']['cpu_percent'] < 80
            memory_ok = health_data['system_resources']['memory_percent'] < 80
            components_ok = all(c['status'] == 'healthy' for c in health_data['components'].values())
            
            if not (cpu_ok and memory_ok and components_ok):
                health_data['overall_status'] = 'degraded'
            
            if health_data['system_resources']['cpu_percent'] > 95 or health_data['system_resources']['memory_percent'] > 95:
                health_data['overall_status'] = 'critical'
            
            return jsonify(health_data)
            
        except Exception as e:
            logger.error(f"Error getting enhanced health: {e}")
            return jsonify({'error': str(e)}), 500
    
    def _get_performance_metrics(self):
        """Get performance metrics"""
        
        try:
            # Get performance data (this would be stored somewhere in real implementation)
            performance_data = {
                'collections_per_minute': 2.0,
                'average_response_time_ms': 150.5,
                'anomaly_detection_rate': 0.05,
                'model_accuracy': 0.92,
                'system_uptime_hours': time.time() / 3600,  # Simplified
                'memory_usage_mb': 128.5,
                'cpu_usage_percent': 15.2
            }
            
            return jsonify({
                'status': 'success',
                'performance': performance_data,
                'timestamp': time.time()
            })
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return jsonify({'error': str(e)}), 500
    
    async def _trigger_enhanced_test(self):
        """Trigger enhanced connectivity test"""
        
        try:
            if not self.enhanced_collector:
                return jsonify({'error': 'Enhanced collector not available'}), 503
            
            # Get test targets from request or use defaults
            from flask import request
            data = request.get_json() or {}
            targets = data.get('targets', self.config.get('monitoring.targets', ['8.8.8.8']))
            
            # Run enhanced test
            results = await self.enhanced_collector.test_enhanced_connectivity(targets)
            
            return jsonify({
                'status': 'success',
                'test_results': results,
                'timestamp': time.time()
            })
            
        except Exception as e:
            logger.error(f"Error triggering enhanced test: {e}")
            return jsonify({'error': str(e)}), 500

# Utility functions for deployment

async def create_enhanced_monitor(config_path: str = "config.yaml") -> EnhancedNetworkIntelligenceMonitor:
    """Create and initialize enhanced monitor"""
    
    monitor = EnhancedNetworkIntelligenceMonitor(config_path)
    await monitor.initialize()
    return monitor

def create_deployment_scripts():
    """Create deployment scripts for different environments"""
    
    # Docker deployment script
    docker_script = '''#!/bin/bash
# Enhanced Network Intelligence Monitor - Docker Deployment

set -e

echo "Building enhanced network intelligence monitor..."

# Build Docker image
docker build -t network-intelligence-monitor:enhanced .

# Create network for monitoring
docker network create monitoring-net 2>/dev/null || true

# Run with environment variables
docker run -d \\
  --name network-monitor-enhanced \\
  --network monitoring-net \\
  -p 8000:8000 \\
  -p 5000:5000 \\
  -e MIMIR_ENDPOINT="${MIMIR_ENDPOINT}" \\
  -e MIMIR_TOKEN="${MIMIR_TOKEN}" \\
  -e ENVIRONMENT="${ENVIRONMENT:-production}" \\
  -e REGION="${REGION:-us-west-2}" \\
  -e CLUSTER_NAME="${CLUSTER_NAME:-network-monitoring}" \\
  -v $(pwd)/data:/app/data \\
  -v $(pwd)/config.yaml:/app/config.yaml \\
  network-intelligence-monitor:enhanced

echo "Enhanced monitor deployed successfully!"
echo "Metrics available at: http://localhost:8000/metrics"
echo "API available at: http://localhost:5000"
'''
    
    # Raspberry Pi deployment script
    pi_script = '''#!/bin/bash
# Enhanced Network Intelligence Monitor - Raspberry Pi Deployment

set -e

echo "Setting up enhanced monitor on Raspberry Pi..."

# Install Python dependencies
pip3 install -r requirements-pi.txt

# Optimize for Pi
export PYTORCH_JIT=0
export OMP_NUM_THREADS=4

# Create systemd service
sudo tee /etc/systemd/system/network-monitor.service > /dev/null <<EOF
[Unit]
Description=Enhanced Network Intelligence Monitor
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/network-intelligence-monitor
ExecStart=/usr/bin/python3 -m src.main
Restart=always
RestartSec=10
Environment=PYTHONPATH=/home/pi/network-intelligence-monitor
Environment=DEPLOYMENT_TYPE=edge

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable network-monitor.service
sudo systemctl start network-monitor.service

echo "Enhanced monitor deployed on Raspberry Pi!"
echo "Status: sudo systemctl status network-monitor"
'''
    
    # Write scripts
    scripts_dir = Path("scripts")
    scripts_dir.mkdir(exist_ok=True)
    
    with open(scripts_dir / "deploy_docker.sh", "w") as f:
        f.write(docker_script)
    
    with open(scripts_dir / "deploy_pi.sh", "w") as f:
        f.write(pi_script)
    
    # Make executable
    import stat
    for script in [scripts_dir / "deploy_docker.sh", scripts_dir / "deploy_pi.sh"]:
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
    
    logger.info("Deployment scripts created in scripts/ directory")

def create_example_config():
    """Create example configuration with all enhanced features"""
    
    config = {
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
            'prometheus_url': 'http://localhost:9090',
            'mimir_url': 'https://mimir.example.com',
            'tenant_id': 'network-monitoring',
            'enabled': True
        },
        'alerts': {
            'enabled': True,
            'webhook_url': None,
            'email_enabled': False
        },
        'deployment': {
            'edge_optimization': True,
            'quantize_models': True,
            'reduce_memory_usage': True
        }
    }
    
    import yaml
    with open("config-enhanced.yaml", "w") as f:
        yaml.dump(config, f, default_flow_style=False, indent=2)
    
    logger.info("Example enhanced configuration created: config-enhanced.yaml")

# Main execution function
async def main():
    """Main function for running enhanced monitor"""
    
    # Setup logging
    setup_logging()
    
    # Create enhanced monitor
    monitor = await create_enhanced_monitor("config-enhanced.yaml")
    
    try:
        # Start monitoring
        monitor.start()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        monitor.stop()

if __name__ == "__main__":
    # Create example configuration
    create_example_config()
    
    # Create deployment scripts
    create_deployment_scripts()
    
    # Run enhanced monitor
    asyncio.run(main())

#!/usr/bin/env python3
"""
Flask API Server
===============

RESTful API server for the Network Intelligence Monitor.
Provides endpoints for metrics, anomalies, health checks, and AI model status.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS
import threading

logger = logging.getLogger(__name__)

class APIServer:
    """Flask API server for the Network Intelligence Monitor"""
    
    def __init__(self, config, database, detector, collector=None):
        self.config = config
        self.database = database
        self.detector = detector
        self.collector = collector
        
        # Initialize Flask app
        self.app = Flask(__name__)
        
        # Enable CORS if configured
        if config.get('cors_enabled', True):
            CORS(self.app, resources={
                r"/api/*": {
                    "origins": "*",
                    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                    "allow_headers": ["Content-Type", "Authorization"]
                }
            })
        
        # Setup routes
        self._setup_routes()
        
        # Threading
        self.server_thread = None
        self.running = False
    
    def _setup_routes(self):
        """Setup API routes"""
        
        # Health check endpoints
        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Basic health check"""
            return jsonify({
                'status': 'healthy',
                'timestamp': time.time(),
                'service': 'network-intelligence-monitor'
            })
        
        @self.app.route('/api/health', methods=['GET'])
        def api_health():
            """Detailed health check"""
            return asyncio.run(self._get_health_status())
        
        # Metrics endpoints
        @self.app.route('/api/metrics/current', methods=['GET'])
        def get_current_metrics():
            """Get current metrics"""
            return asyncio.run(self._get_current_metrics())
        
        @self.app.route('/api/metrics/recent', methods=['GET'])
        def get_recent_metrics():
            """Get recent metrics"""
            target = request.args.get('target')
            hours = int(request.args.get('hours', 24))
            limit = int(request.args.get('limit', 1000))
            
            return asyncio.run(self._get_recent_metrics(target, hours, limit))
        
        @self.app.route('/api/metrics/targets', methods=['GET'])
        def get_monitored_targets():
            """Get list of monitored targets"""
            return jsonify({
                'targets': self.config.get('monitoring.targets', []),
                'count': len(self.config.get('monitoring.targets', []))
            })
        
        # Anomaly endpoints
        @self.app.route('/api/anomalies/recent', methods=['GET'])
        def get_recent_anomalies():
            """Get recent anomalies"""
            target = request.args.get('target')
            hours = int(request.args.get('hours', 24))
            limit = int(request.args.get('limit', 100))
            
            return asyncio.run(self._get_recent_anomalies(target, hours, limit))
        
        @self.app.route('/api/anomalies/summary', methods=['GET'])
        def get_anomaly_summary():
            """Get anomaly summary"""
            hours = int(request.args.get('hours', 24))
            return asyncio.run(self._get_anomaly_summary(hours))
        
        # AI Model endpoints
        @self.app.route('/api/ai/status', methods=['GET'])
        def get_ai_status():
            """Get AI model status"""
            return self._get_ai_status()
        
        @self.app.route('/api/ai/retrain', methods=['POST'])
        def trigger_retrain():
            """Trigger model retraining"""
            return asyncio.run(self._trigger_retrain())
        
        @self.app.route('/api/ai/performance', methods=['GET'])
        def get_ai_performance():
            """Get AI model performance metrics"""
            return asyncio.run(self._get_ai_performance())
        
        # Database endpoints
        @self.app.route('/api/database/stats', methods=['GET'])
        def get_database_stats():
            """Get database statistics"""
            return asyncio.run(self._get_database_stats())
        
        @self.app.route('/api/database/cleanup', methods=['POST'])
        def trigger_cleanup():
            """Trigger database cleanup"""
            days = request.json.get('days', 30) if request.json else 30
            return asyncio.run(self._trigger_cleanup(days))
        
        # Configuration endpoints
        @self.app.route('/api/config', methods=['GET'])
        def get_config():
            """Get current configuration"""
            return jsonify(self.config.to_dict())
        
        @self.app.route('/api/config', methods=['PUT'])
        def update_config():
            """Update configuration"""
            return self._update_config(request.json)
        
        # Test endpoints
        @self.app.route('/api/test/connectivity', methods=['POST'])
        def test_connectivity():
            """Test connectivity to targets"""
            data = request.json or {}
            targets = data.get('targets', self.config.get('monitoring.targets', []))
            return asyncio.run(self._test_connectivity(targets))
        
        @self.app.route('/api/test/single', methods=['POST'])
        def test_single_target():
            """Test single target"""
            data = request.json or {}
            target = data.get('target')
            if not target:
                return jsonify({'error': 'Target required'}), 400
            
            return asyncio.run(self._test_single_target(target))
        
        # Dashboard data endpoints
        @self.app.route('/api/dashboard/overview', methods=['GET'])
        def get_dashboard_overview():
            """Get dashboard overview data"""
            return asyncio.run(self._get_dashboard_overview())
        
        @self.app.route('/api/dashboard/charts', methods=['GET'])
        def get_chart_data():
            """Get chart data for dashboard"""
            chart_type = request.args.get('type', 'latency')
            hours = int(request.args.get('hours', 24))
            target = request.args.get('target')
            
            return asyncio.run(self._get_chart_data(chart_type, hours, target))
        
        # WebSocket endpoint for real-time data
        @self.app.route('/api/ws/info', methods=['GET'])
        def websocket_info():
            """WebSocket connection information"""
            return jsonify({
                'websocket_url': f"ws://{request.host}/ws",
                'protocols': ['metrics', 'anomalies', 'health'],
                'update_interval': 30
            })
        
        # Static files for dashboard
        @self.app.route('/')
        def serve_dashboard():
            """Serve dashboard index"""
            return send_from_directory('frontend/build', 'index.html')
        
        @self.app.route('/<path:path>')
        def serve_static(path):
            """Serve static dashboard files"""
            return send_from_directory('frontend/build', path)
        
        # Error handlers
        @self.app.errorhandler(404)
        def not_found(error):
            return jsonify({'error': 'Endpoint not found'}), 404
        
        @self.app.errorhandler(500)
        def internal_error(error):
            return jsonify({'error': 'Internal server error'}), 500
        
        @self.app.errorhandler(Exception)
        def handle_exception(e):
            logger.error(f"Unhandled API exception: {e}")
            return jsonify({'error': 'An unexpected error occurred'}), 500
    
    async def _get_health_status(self):
        """Get detailed health status"""
        
        try:
            # Check database
            db_stats = await self.database.get_database_stats()
            db_healthy = db_stats.get('recent_metrics_count', 0) > 0
            
            # Check AI detector
            ai_healthy = self.detector and hasattr(self.detector, 'is_trained') and self.detector.is_trained
            
            # Check collector
            collector_healthy = self.collector is not None
            
            # Overall health
            overall_healthy = db_healthy and ai_healthy
            
            health_data = {
                'status': 'healthy' if overall_healthy else 'degraded',
                'timestamp': time.time(),
                'components': {
                    'database': {
                        'status': 'healthy' if db_healthy else 'unhealthy',
                        'recent_metrics': db_stats.get('recent_metrics_count', 0),
                        'size_mb': db_stats.get('database_size_mb', 0)
                    },
                    'ai_detector': {
                        'status': 'healthy' if ai_healthy else 'unhealthy',
                        'trained': ai_healthy,
                        'model_type': 'lstm_autoencoder' if ai_healthy else None
                    },
                    'collector': {
                        'status': 'healthy' if collector_healthy else 'unavailable',
                        'available': collector_healthy
                    }
                },
                'system': await self._get_system_health()
            }
            
            return jsonify(health_data)
            
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return jsonify({'error': str(e)}), 500
    
    async def _get_system_health(self):
        """Get system health metrics"""
        
        try:
            import psutil
            
            return {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0],
                'uptime_seconds': time.time() - psutil.boot_time()
            }
            
        except ImportError:
            return {'error': 'System monitoring not available'}
        except Exception as e:
            return {'error': str(e)}
    
    async def _get_current_metrics(self):
        """Get current/latest metrics"""
        
        try:
            if self.collector:
                # Get real-time metrics
                target = self.config.get('monitoring.targets', ['8.8.8.8'])[0]
                metrics = await self.collector.collect_enhanced_metrics(target)
                
                if metrics:
                    return jsonify({
                        'status': 'success',
                        'metrics': metrics.to_dict(),
                        'source': 'real_time'
                    })
            
            # Fallback to database
            recent_metrics = await self.database.get_recent_metrics(limit=1)
            if recent_metrics:
                return jsonify({
                    'status': 'success',
                    'metrics': recent_metrics[0],
                    'source': 'database'
                })
            else:
                return jsonify({
                    'status': 'no_data',
                    'message': 'No metrics available'
                })
            
        except Exception as e:
            logger.error(f"Error getting current metrics: {e}")
            return jsonify({'error': str(e)}), 500
    
    async def _get_recent_metrics(self, target: str = None, hours: int = 24, limit: int = 1000):
        """Get recent metrics"""
        
        try:
            metrics = await self.database.get_recent_metrics(target, hours, limit)
            
            return jsonify({
                'status': 'success',
                'metrics': metrics,
                'count': len(metrics),
                'target': target,
                'hours': hours,
                'limit': limit
            })
            
        except Exception as e:
            logger.error(f"Error getting recent metrics: {e}")
            return jsonify({'error': str(e)}), 500
    
    async def _get_recent_anomalies(self, target: str = None, hours: int = 24, limit: int = 100):
        """Get recent anomalies"""
        
        try:
            anomalies = await self.database.get_recent_anomalies(target, hours, limit)
            
            return jsonify({
                'status': 'success',
                'anomalies': anomalies,
                'count': len(anomalies),
                'target': target,
                'hours': hours
            })
            
        except Exception as e:
            logger.error(f"Error getting recent anomalies: {e}")
            return jsonify({'error': str(e)}), 500
    
    async def _get_anomaly_summary(self, hours: int = 24):
        """Get anomaly summary"""
        
        try:
            anomalies = await self.database.get_recent_anomalies(hours=hours, limit=1000)
            
            summary = {
                'total_anomalies': len(anomalies),
                'critical_anomalies': len([a for a in anomalies if a.get('is_critical')]),
                'by_severity': {},
                'by_target': {},
                'recent_trend': []
            }
            
            # Group by severity and target
            for anomaly in anomalies:
                # Extract severity from recommendation or use default
                if 'critical' in anomaly.get('recommendation', '').lower():
                    severity = 'critical'
                elif 'high' in anomaly.get('recommendation', '').lower():
                    severity = 'high'
                else:
                    severity = 'medium'
                
                summary['by_severity'][severity] = summary['by_severity'].get(severity, 0) + 1
                
                target = anomaly.get('target_host', 'unknown')
                summary['by_target'][target] = summary['by_target'].get(target, 0) + 1
            
            # Recent trend (last 24 hours in 4-hour buckets)
            now = time.time()
            for i in range(6):
                bucket_start = now - (i + 1) * 4 * 3600
                bucket_end = now - i * 4 * 3600
                
                bucket_anomalies = len([
                    a for a in anomalies 
                    if bucket_start <= a.get('timestamp', 0) < bucket_end
                ])
                
                summary['recent_trend'].append({
                    'time_bucket': bucket_start,
                    'anomaly_count': bucket_anomalies
                })
            
            summary['recent_trend'].reverse()
            
            return jsonify({
                'status': 'success',
                'summary': summary,
                'hours': hours
            })
            
        except Exception as e:
            logger.error(f"Error getting anomaly summary: {e}")
            return jsonify({'error': str(e)}), 500
    
    def _get_ai_status(self):
        """Get AI model status"""
        
        try:
            if not self.detector:
                return jsonify({
                    'status': 'unavailable',
                    'message': 'AI detector not initialized'
                })
            
            status = {
                'status': 'healthy' if hasattr(self.detector, 'is_trained') and self.detector.is_trained else 'untrained',
                'model_type': 'lstm_autoencoder',
                'trained': hasattr(self.detector, 'is_trained') and self.detector.is_trained,
                'model_info': {
                    'sequence_length': getattr(self.detector, 'sequence_length', 20),
                    'input_size': getattr(self.detector, 'input_size', 10),
                    'hidden_size': getattr(self.detector, 'hidden_size', 64)
                }
            }
            
            # Add model file info if available
            if hasattr(self.detector, 'model_dir'):
                from pathlib import Path
                model_path = Path(self.detector.model_dir) / 'lstm_autoencoder.pt'
                if model_path.exists():
                    status['model_file'] = {
                        'path': str(model_path),
                        'size_mb': model_path.stat().st_size / (1024**2),
                        'modified': model_path.stat().st_mtime
                    }
            
            return jsonify(status)
            
        except Exception as e:
            logger.error(f"Error getting AI status: {e}")
            return jsonify({'error': str(e)}), 500
    
    async def _trigger_retrain(self):
        """Trigger model retraining"""
        
        try:
            if not self.detector:
                return jsonify({'error': 'AI detector not available'}), 503
            
            # Get training data
            training_data = await self.database.get_metrics_for_training(hours=24)
            
            if len(training_data) < 50:
                return jsonify({
                    'error': 'Insufficient training data',
                    'available_samples': len(training_data),
                    'required_samples': 50
                }), 400
            
            # Start training (this should be non-blocking in production)
            start_time = time.time()
            
            if hasattr(self.detector, 'train_online'):
                await self.detector.train_online(training_data)
            else:
                await self.detector.train_initial_model()
            
            training_time = time.time() - start_time
            
            return jsonify({
                'status': 'success',
                'message': 'Model retraining completed',
                'training_samples': len(training_data),
                'training_time_seconds': training_time
            })
            
        except Exception as e:
            logger.error(f"Error triggering retrain: {e}")
            return jsonify({'error': str(e)}), 500
    
    async def _get_ai_performance(self):
        """Get AI model performance metrics"""
        
        try:
            # This would get performance data from database
            # For now, return placeholder data
            performance = {
                'accuracy': 0.92,
                'precision': 0.89,
                'recall': 0.94,
                'f1_score': 0.91,
                'false_positive_rate': 0.08,
                'last_training': time.time() - 3600,  # 1 hour ago
                'total_predictions': 1250,
                'anomalies_detected': 45
            }
            
            return jsonify({
                'status': 'success',
                'performance': performance
            })
            
        except Exception as e:
            logger.error(f"Error getting AI performance: {e}")
            return jsonify({'error': str(e)}), 500
    
    async def _get_database_stats(self):
        """Get database statistics"""
        
        try:
            stats = await self.database.get_database_stats()
            
            return jsonify({
                'status': 'success',
                'statistics': stats
            })
            
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return jsonify({'error': str(e)}), 500
    
    async def _trigger_cleanup(self, days: int):
        """Trigger database cleanup"""
        
        try:
            cleanup_stats = await self.database.cleanup_old_data(days)
            
            return jsonify({
                'status': 'success',
                'message': f'Cleanup completed for data older than {days} days',
                'cleanup_stats': cleanup_stats
            })
            
        except Exception as e:
            logger.error(f"Error triggering cleanup: {e}")
            return jsonify({'error': str(e)}), 500
    
    def _update_config(self, new_config: Dict[str, Any]):
        """Update configuration"""
        
        try:
            if not new_config:
                return jsonify({'error': 'No configuration provided'}), 400
            
            # Update configuration (simplified - in production, validate first)
            for key, value in new_config.items():
                self.config.set(key, value)
            
            return jsonify({
                'status': 'success',
                'message': 'Configuration updated'
            })
            
        except Exception as e:
            logger.error(f"Error updating config: {e}")
            return jsonify({'error': str(e)}), 500
    
    async def _test_connectivity(self, targets: List[str]):
        """Test connectivity to targets"""
        
        try:
            if not self.collector:
                return jsonify({'error': 'Collector not available'}), 503
            
            results = await self.collector.test_enhanced_connectivity(targets)
            
            return jsonify({
                'status': 'success',
                'test_results': results,
                'timestamp': time.time()
            })
            
        except Exception as e:
            logger.error(f"Error testing connectivity: {e}")
            return jsonify({'error': str(e)}), 500
    
    async def _test_single_target(self, target: str):
        """Test single target"""
        
        try:
            if not self.collector:
                return jsonify({'error': 'Collector not available'}), 503
            
            metrics = await self.collector.collect_enhanced_metrics(target)
            
            if metrics:
                return jsonify({
                    'status': 'success',
                    'target': target,
                    'metrics': metrics.to_dict(),
                    'timestamp': time.time()
                })
            else:
                return jsonify({
                    'status': 'failed',
                    'target': target,
                    'message': 'Failed to collect metrics'
                })
            
        except Exception as e:
            logger.error(f"Error testing single target: {e}")
            return jsonify({'error': str(e)}), 500
    
    async def _get_dashboard_overview(self):
        """Get dashboard overview data"""
        
        try:
            # Get recent metrics and anomalies
            recent_metrics = await self.database.get_recent_metrics(hours=1, limit=10)
            recent_anomalies = await self.database.get_recent_anomalies(hours=24, limit=10)
            
            # Calculate overview stats
            overview = {
                'current_time': time.time(),
                'monitoring_status': 'active' if recent_metrics else 'inactive',
                'total_targets': len(self.config.get('monitoring.targets', [])),
                'recent_metrics_count': len(recent_metrics),
                'anomalies_24h': len(recent_anomalies),
                'critical_anomalies': len([a for a in recent_anomalies if a.get('is_critical')]),
                'system_health': await self._get_system_health(),
                'ai_status': self._get_ai_status().get_json() if self.detector else None
            }
            
            # Add latest metrics summary
            if recent_metrics:
                latest = recent_metrics[0]
                overview['latest_metrics'] = {
                    'timestamp': latest.get('timestamp'),
                    'target': latest.get('target_host'),
                    'latency': latest.get('icmp_ping_time', 0),
                    'packet_loss': latest.get('packet_loss', 0),
                    'jitter': latest.get('jitter', 0)
                }
            
            return jsonify({
                'status': 'success',
                'overview': overview
            })
            
        except Exception as e:
            logger.error(f"Error getting dashboard overview: {e}")
            return jsonify({'error': str(e)}), 500
    
    async def _get_chart_data(self, chart_type: str, hours: int, target: str = None):
        """Get chart data for dashboard"""
        
        try:
            metrics = await self.database.get_recent_metrics(target, hours, 1000)
            
            if not metrics:
                return jsonify({
                    'status': 'no_data',
                    'chart_type': chart_type,
                    'message': 'No data available'
                })
            
            # Process data based on chart type
            chart_data = []
            
            for metric in metrics:
                timestamp = metric.get('timestamp', 0)
                
                if chart_type == 'latency':
                    value = metric.get('icmp_ping_time', 0)
                elif chart_type == 'packet_loss':
                    value = metric.get('packet_loss', 0)
                elif chart_type == 'jitter':
                    value = metric.get('jitter', 0)
                elif chart_type == 'mos_score':
                    value = metric.get('mos_score', 0)
                else:
                    value = 0
                
                chart_data.append({
                    'timestamp': timestamp,
                    'value': value,
                    'target': metric.get('target_host', 'unknown')
                })
            
            # Sort by timestamp
            chart_data.sort(key=lambda x: x['timestamp'])
            
            return jsonify({
                'status': 'success',
                'chart_type': chart_type,
                'data': chart_data,
                'count': len(chart_data)
            })
            
        except Exception as e:
            logger.error(f"Error getting chart data: {e}")
            return jsonify({'error': str(e)}), 500
    
    def run(self, host: str = None, port: int = None, debug: bool = None):
        """Run the API server"""
        
        host = host or self.config.get('api.host', '0.0.0.0')
        port = port or self.config.get('api.port', 5000)
        debug = debug if debug is not None else self.config.get('api.debug', False)
        
        logger.info(f"Starting API server on {host}:{port}")
        
        try:
            self.app.run(
                host=host,
                port=port,
                debug=debug,
                threaded=True,
                use_reloader=False  # Disable reloader to avoid issues
            )
        except Exception as e:
            logger.error(f"API server error: {e}")
            raise
    
    def run_threaded(self, host: str = None, port: int = None, debug: bool = None):
        """Run the API server in a separate thread"""
        
        if self.running:
            logger.warning("API server already running")
            return
        
        self.running = True
        
        def run_server():
            self.run(host, port, debug)
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        logger.info("API server started in background thread")
    
    def stop(self):
        """Stop the API server"""
        self.running = False
        
        # Note: Flask dev server doesn't have a clean shutdown method
        # In production, use a proper WSGI server like Gunicorn
        logger.info("API server stop requested")

#!/usr/bin/env python3
# src/api/server.py - Updated with NetworkQuality integration
"""
Enhanced API Server with NetworkQuality-RS integration
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
import logging
from typing import Optional, Dict, Any

# Import the NetworkQuality routes
from .networkquality_routes import create_networkquality_routes

logger = logging.getLogger(__name__)

class APIServer:
    def __init__(self, config, database, ai_detector=None, enhanced_collector=None):
        self.config = config
        self.database = database
        self.ai_detector = ai_detector
        self.enhanced_collector = enhanced_collector
        
        # These will be set later by main.py
        self.mimir_client = None
        self.metrics_server = None
        self.alert_manager = None
        self.threshold_manager = None
        self.nq_collector = None  # NetworkQuality collector
        
        self.app = Flask(__name__)
        
        if config.api.cors_enabled:
            CORS(self.app)
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup all API routes including NetworkQuality routes"""
        
        # Health check
        @self.app.route('/health')
        def health_check():
            return jsonify({
                'status': 'healthy',
                'timestamp': time.time(),
                'services': {
                    'database': self.database is not None,
                    'ai_detector': self.ai_detector is not None,
                    'enhanced_collector': self.enhanced_collector is not None,
                    'networkquality': self.nq_collector is not None,
                    'mimir_client': self.mimir_client is not None,
                    'alert_manager': self.alert_manager is not None
                }
            })
        
        # System status
        @self.app.route('/api/status')
        def system_status():
            return jsonify({
                'status': 'success',
                'data': {
                    'uptime_seconds': time.time() - getattr(self, 'start_time', time.time()),
                    'config': {
                        'monitoring_enabled': self.config.monitoring.enabled,
                        'ai_enabled': self.ai_detector is not None,
                        'networkquality_enabled': self.config.networkquality.enabled if hasattr(self.config, 'networkquality') else False,
                        'mimir_enabled': self.config.mimir.enabled if hasattr(self.config, 'mimir') else False,
                        'alerts_enabled': self.config.alerts.enabled if hasattr(self.config, 'alerts') else False,
                    },
                    'targets': self.config.monitoring.targets if self.config.monitoring else [],
                    'intervals': {
                        'monitoring': self.config.monitoring.interval if self.config.monitoring else None,
                        'networkquality': self.config.networkquality.testing.get('default_interval_seconds') if hasattr(self.config, 'networkquality') and hasattr(self.config.networkquality, 'testing') else None
                    }
                },
                'timestamp': time.time()
            })
        
        # Enhanced metrics endpoints
        @self.app.route('/api/metrics/latest')
        def get_latest_metrics():
            return asyncio.run(self._get_latest_metrics())
        
        @self.app.route('/api/metrics/history')
        def get_metrics_history():
            return asyncio.run(self._get_metrics_history())
        
        # Dashboard endpoint
        @self.app.route('/')
        def dashboard():
            return render_template_string(self._get_dashboard_template())
        
        # NetworkQuality routes integration
        if hasattr(self.config, 'networkquality') and self.config.networkquality.enabled:
            # We'll register the NetworkQuality blueprint after it's created
            pass
    
    def register_networkquality_routes(self, nq_collector):
        """Register NetworkQuality routes after collector is available"""
        self.nq_collector = nq_collector
        nq_blueprint = create_networkquality_routes(self.database, nq_collector)
        self.app.register_blueprint(nq_blueprint)
        logger.info("NetworkQuality API routes registered")
    
    async def _get_latest_metrics(self):
        """Get latest enhanced metrics"""
        try:
            if not self.database or not self.database.db:
                return jsonify({'error': 'Database not available'}), 500
            
            query = """
                SELECT * FROM enhanced_metrics 
                ORDER BY timestamp DESC 
                LIMIT 1
            """
            
            cursor = await self.database.db.execute(query)
            row = await cursor.fetchone()
            
            if not row:
                return jsonify({'error': 'No metrics found'}), 404
            
            columns = [description[0] for description in cursor.description]
            result = dict(zip(columns, row))
            
            return jsonify({
                'status': 'success',
                'data': result,
                'timestamp': time.time()
            })
            
        except Exception as e:
            logger.error(f"Error fetching latest metrics: {e}")
            return jsonify({'error': str(e)}), 500
    
    async def _get_metrics_history(self):
        """Get metrics history"""
        try:
            if not self.database or not self.database.db:
                return jsonify({'error': 'Database not available'}), 500
            
            hours = int(request.args.get('hours', 24))
            limit = int(request.args.get('limit', 100))
            target = request.args.get('target')
            
            where_conditions = []
            params = []
            
            start_time = time.time() - (hours * 3600)
            where_conditions.append("timestamp >= ?")
            params.append(start_time)
            
            if target:
                where_conditions.append("target_host = ?")
                params.append(target)
            
            where_clause = " AND ".join(where_conditions)
            
            query = f"""
                SELECT * FROM enhanced_metrics 
                WHERE {where_clause}
                ORDER BY timestamp DESC 
                LIMIT ?
            """
            params.append(limit)
            
            cursor = await self.database.db.execute(query, params)
            rows = await cursor.fetchall()
            
            columns = [description[0] for description in cursor.description]
            results = [dict(zip(columns, row)) for row in rows]
            
            return jsonify({
                'status': 'success',
                'data': results,
                'count': len(results),
                'filters': {
                    'hours': hours,
                    'limit': limit,
                    'target': target
                },
                'timestamp': time.time()
            })
            
        except Exception as e:
            logger.error(f"Error fetching metrics history: {e}")
            return jsonify({'error': str(e)}), 500
    
    def _get_dashboard_template(self):
        """Enhanced dashboard template with NetworkQuality integration"""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>Network Intelligence Monitor</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0; padding: 20px; background: #f5f5f5; 
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px;
            text-align: center;
        }
        .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .card { 
            background: white; border-radius: 10px; padding: 20px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
        }
        .card h3 { margin: 0 0 15px 0; color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px; }
        .metric { display: flex; justify-content: space-between; margin: 10px 0; }
        .metric-label { font-weight: 500; color: #666; }
        .metric-value { font-weight: bold; color: #333; }
        .status-healthy { color: #28a745; }
        .status-warning { color: #ffc107; }
        .status-danger { color: #dc3545; }
        .button { 
            background: #007bff; color: white; border: none; padding: 10px 20px; 
            border-radius: 5px; cursor: pointer; margin: 5px; text-decoration: none;
            display: inline-block;
        }
        .button:hover { background: #0056b3; }
        .loading { text-align: center; color: #666; padding: 20px; }
        .nq-quality { font-size: 1.2em; font-weight: bold; }
        .quality-excellent { color: #28a745; }
        .quality-good { color: #20c997; }
        .quality-fair { color: #ffc107; }
        .quality-poor { color: #fd7e14; }
        .quality-error { color: #dc3545; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>倹 Network Intelligence Monitor</h1>
            <p>Enhanced monitoring with NetworkQuality-RS integration</p>
        </div>
        
        <div class="cards">
            <div class="card">
                <h3>投 System Status</h3>
                <div id="system-status" class="loading">Loading...</div>
            </div>
            
            <div class="card">
                <h3>嶋 Latest Enhanced Metrics</h3>
                <div id="enhanced-metrics" class="loading">Loading...</div>
            </div>
            
            <div class="card">
                <h3>笞｡ NetworkQuality Status</h3>
                <div id="networkquality-status" class="loading">Loading...</div>
            </div>
            
            <div class="card">
                <h3>識 Latest NetworkQuality Metrics</h3>
                <div id="networkquality-metrics" class="loading">Loading...</div>
            </div>
            
            <div class="card">
                <h3>搭 Recent Recommendations</h3>
                <div id="recommendations" class="loading">Loading...</div>
            </div>
            
            <div class="card">
                <h3>肌 Actions</h3>
                <button class="button" onclick="runNetworkQualityTest()">Run NetworkQuality Test</button>
                <button class="button" onclick="refreshData()">Refresh All Data</button>
                <a href="/api/networkquality/metrics/history" class="button">View Full History</a>
            </div>
        </div>
    </div>

    <script>
        async function fetchData(url) {
            try {
                const response = await fetch(url);
                return await response.json();
            } catch (error) {
                console.error('Fetch error:', error);
                return { error: error.message };
            }
        }
        
        function formatTimestamp(timestamp) {
            return new Date(timestamp * 1000).toLocaleString();
        }
        
        function formatMetric(label, value, unit = '') {
            if (value === null || value === undefined) return '';
            const formattedValue = typeof value === 'number' ? value.toFixed(2) : value;
            return `<div class="metric"><span class="metric-label">${label}:</span><span class="metric-value">${formattedValue}${unit}</span></div>`;
        }
        
        function getQualityClass(rating) {
            return `quality-${rating}`;
        }
        
        async function loadSystemStatus() {
            const data = await fetchData('/api/status');
            const container = document.getElementById('system-status');
            
            if (data.error) {
                container.innerHTML = `<div class="status-danger">Error: ${data.error}</div>`;
                return;
            }
            
            const services = data.data.config;
            container.innerHTML = `
                <div class="metric"><span class="metric-label">Uptime:</span><span class="metric-value">${Math.round(data.data.uptime_seconds / 60)} minutes</span></div>
                <div class="metric"><span class="metric-label">Enhanced Monitoring:</span><span class="metric-value ${services.monitoring_enabled ? 'status-healthy' : 'status-danger'}">${services.monitoring_enabled ? 'Enabled' : 'Disabled'}</span></div>
                <div class="metric"><span class="metric-label">NetworkQuality:</span><span class="metric-value ${services.networkquality_enabled ? 'status-healthy' : 'status-danger'}">${services.networkquality_enabled ? 'Enabled' : 'Disabled'}</span></div>
                <div class="metric"><span class="metric-label">AI Detection:</span><span class="metric-value ${services.ai_enabled ? 'status-healthy' : 'status-danger'}">${services.ai_enabled ? 'Enabled' : 'Disabled'}</span></div>
                <div class="metric"><span class="metric-label">Targets:</span><span class="metric-value">${data.data.targets.join(', ')}</span></div>
            `;
        }
        
        async function loadEnhancedMetrics() {
            const data = await fetchData('/api/metrics/latest');
            const container = document.getElementById('enhanced-metrics');
            
            if (data.error) {
                container.innerHTML = `<div class="status-danger">Error: ${data.error}</div>`;
                return;
            }
            
            const metrics = data.data;
            container.innerHTML = `
                <div class="metric"><span class="metric-label">Target:</span><span class="metric-value">${metrics.target_host}</span></div>
                <div class="metric"><span class="metric-label">Last Update:</span><span class="metric-value">${formatTimestamp(metrics.timestamp)}</span></div>
                ${formatMetric('Ping Time', metrics.icmp_ping_time, 'ms')}
                ${formatMetric('TCP Handshake', metrics.tcp_handshake_time, 'ms')}
                ${formatMetric('DNS Resolve', metrics.dns_resolve_time, 'ms')}
                ${formatMetric('Packet Loss', metrics.packet_loss, '%')}
                ${formatMetric('Jitter', metrics.jitter, 'ms')}
                ${formatMetric('MOS Score', metrics.mos_score)}
            `;
        }
        
        async function loadNetworkQualityStatus() {
            const data = await fetchData('/api/networkquality/status');
            const container = document.getElementById('networkquality-status');
            
            if (data.error) {
                container.innerHTML = `<div class="status-danger">Error: ${data.error}</div>`;
                return;
            }
            
            const status = data.data;
            const healthClass = status.service_health === 'healthy' ? 'status-healthy' : 
                               status.service_health === 'degraded' ? 'status-warning' : 'status-danger';
            
            container.innerHTML = `
                <div class="metric"><span class="metric-label">Service Health:</span><span class="metric-value ${healthClass}">${status.service_health}</span></div>
                <div class="metric"><span class="metric-label">Collector:</span><span class="metric-value ${status.collector_available ? 'status-healthy' : 'status-danger'}">${status.collector_available ? 'Available' : 'Unavailable'}</span></div>
                <div class="metric"><span class="metric-label">Database:</span><span class="metric-value ${status.database_available ? 'status-healthy' : 'status-danger'}">${status.database_available ? 'Available' : 'Unavailable'}</span></div>
                ${status.last_measurement ? `<div class="metric"><span class="metric-label">Last Measurement:</span><span class="metric-value">${formatTimestamp(status.last_measurement)}</span></div>` : ''}
                ${status.last_measurement_ago_seconds ? `<div class="metric"><span class="metric-label">Time Since Last:</span><span class="metric-value">${Math.round(status.last_measurement_ago_seconds / 60)} minutes ago</span></div>` : ''}
            `;
        }
        
        async function loadNetworkQualityMetrics() {
            const data = await fetchData('/api/networkquality/metrics/latest');
            const container = document.getElementById('networkquality-metrics');
            
            if (data.error) {
                container.innerHTML = `<div class="status-danger">Error: ${data.error}</div>`;
                return;
            }
            
            const metrics = data.data;
            container.innerHTML = `
                <div class="metric"><span class="metric-label">Target:</span><span class="metric-value">${metrics.target_host}</span></div>
                <div class="metric"><span class="metric-label">Quality Rating:</span><span class="metric-value nq-quality ${getQualityClass(metrics.quality_rating)}">${metrics.quality_rating.toUpperCase()}</span></div>
                ${formatMetric('RPM Average', metrics.rpm_average)}
                ${formatMetric('Download RPM', metrics.rpm_download)}
                ${formatMetric('Upload RPM', metrics.rpm_upload)}
                ${formatMetric('Max Bufferbloat', metrics.max_bufferbloat_ms, 'ms')}
                ${formatMetric('Bufferbloat Severity', metrics.bufferbloat_severity)}
                ${formatMetric('Download Throughput', metrics.download_throughput_mbps, ' Mbps')}
                ${formatMetric('Upload Throughput', metrics.upload_throughput_mbps, ' Mbps')}
                ${formatMetric('Quality Score', metrics.overall_quality_score)}
                <div class="metric"><span class="metric-label">Last Update:</span><span class="metric-value">${formatTimestamp(metrics.timestamp)}</span></div>
            `;
        }
        
        async function loadRecommendations() {
            const data = await fetchData('/api/networkquality/recommendations?hours=6');
            const container = document.getElementById('recommendations');
            
            if (data.error) {
                container.innerHTML = `<div class="status-danger">Error: ${data.error}</div>`;
                return;
            }
            
            if (data.data.length === 0) {
                container.innerHTML = '<div>No recent recommendations</div>';
                return;
            }
            
            const recentRecs = data.data.slice(0, 3);
            container.innerHTML = recentRecs.map(rec => `
                <div style="margin-bottom: 15px; padding: 10px; background: #f8f9fa; border-radius: 5px;">
                    <div style="font-weight: bold; color: #666; font-size: 0.9em;">${formatTimestamp(rec.timestamp)} - ${rec.quality_rating.toUpperCase()}</div>
                    <ul style="margin: 5px 0; padding-left: 20px;">
                        ${rec.recommendations.map(r => `<li style="margin: 2px 0;">${r}</li>`).join('')}
                    </ul>
                </div>
            `).join('');
        }
        
        async function runNetworkQualityTest() {
            const button = event.target;
            button.disabled = true;
            button.textContent = 'Running Test...';
            
            try {
                const response = await fetch('/api/networkquality/test/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ force: true })
                });
                
                const result = await response.json();
                
                if (result.status === 'success') {
                    alert(`Test completed successfully!\\nDuration: ${result.duration_seconds}s\\nQuality: ${result.data.quality_rating}`);
                    refreshData();
                } else {
                    alert(`Test failed: ${result.error}`);
                }
            } catch (error) {
                alert(`Test error: ${error.message}`);
            } finally {
                button.disabled = false;
                button.textContent = 'Run NetworkQuality Test';
            }
        }
        
        async function refreshData() {
            await Promise.all([
                loadSystemStatus(),
                loadEnhancedMetrics(),
                loadNetworkQualityStatus(),
                loadNetworkQualityMetrics(),
                loadRecommendations()
            ]);
        }
        
        // Initial load
        refreshData();
        
        // Auto-refresh every 30 seconds
        setInterval(refreshData, 30000);
    </script>
</body>
</html>
        """
    
    def run(self):
        """Run the API server, ensuring the reloader is disabled."""
        self.start_time = time.time()
        
        # When running inside a thread via run_in_executor, the reloader must be disabled
        # to avoid the "signal only works in main thread" error.
        use_reloader = False
        
        self.app.run(
            host=self.config.api.host,
            port=self.config.api.port,
            debug=self.config.api.debug,
            use_reloader=use_reloader, # Explicitly disable the reloader
            threaded=True
        )

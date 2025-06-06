#!/usr/bin/env python3
# src/api/networkquality_routes.py
"""
API routes for NetworkQuality-RS (Cloudflare responsiveness) metrics
"""

import json
import time
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

def create_networkquality_routes(database, nq_collector=None):
    """Create NetworkQuality API routes"""
    
    networkquality_bp = Blueprint('networkquality', __name__, url_prefix='/api/networkquality')
    
    @networkquality_bp.route('/metrics/latest', methods=['GET'])
    async def get_latest_metrics():
        """Get the latest NetworkQuality metrics"""
        try:
            if not database or not database.db:
                return jsonify({'error': 'Database not available'}), 500
            
            query = """
                SELECT * FROM network_quality_rs_metrics 
                ORDER BY timestamp DESC 
                LIMIT 1
            """
            
            cursor = await database.db.execute(query)
            row = await cursor.fetchone()
            
            if not row:
                return jsonify({'error': 'No NetworkQuality metrics found'}), 404
            
            # Convert row to dict
            columns = [description[0] for description in cursor.description]
            result = dict(zip(columns, row))
            
            # Parse JSON fields
            if result.get('recommendations'):
                try:
                    result['recommendations'] = json.loads(result['recommendations'])
                except json.JSONDecodeError:
                    result['recommendations'] = []
            
            return jsonify({
                'status': 'success',
                'data': result,
                'timestamp': time.time()
            })
            
        except Exception as e:
            logger.error(f"Error fetching latest NetworkQuality metrics: {e}")
            return jsonify({'error': str(e)}), 500
    
    @networkquality_bp.route('/metrics/history', methods=['GET'])
    async def get_metrics_history():
        """Get NetworkQuality metrics history with optional filtering"""
        try:
            if not database or not database.db:
                return jsonify({'error': 'Database not available'}), 500
            
            # Parse query parameters
            hours = int(request.args.get('hours', 24))
            limit = int(request.args.get('limit', 100))
            target_host = request.args.get('target_host')
            
            # Build query
            where_conditions = []
            params = []
            
            # Time filter
            start_time = time.time() - (hours * 3600)
            where_conditions.append("timestamp >= ?")
            params.append(start_time)
            
            # Target filter
            if target_host:
                where_conditions.append("target_host = ?")
                params.append(target_host)
            
            where_clause = " AND ".join(where_conditions)
            
            query = f"""
                SELECT * FROM network_quality_rs_metrics 
                WHERE {where_clause}
                ORDER BY timestamp DESC 
                LIMIT ?
            """
            params.append(limit)
            
            cursor = await database.db.execute(query, params)
            rows = await cursor.fetchall()
            
            # Convert rows to list of dicts
            columns = [description[0] for description in cursor.description]
            results = []
            
            for row in rows:
                result = dict(zip(columns, row))
                
                # Parse JSON fields
                if result.get('recommendations'):
                    try:
                        result['recommendations'] = json.loads(result['recommendations'])
                    except json.JSONDecodeError:
                        result['recommendations'] = []
                
                results.append(result)
            
            return jsonify({
                'status': 'success',
                'data': results,
                'count': len(results),
                'filters': {
                    'hours': hours,
                    'limit': limit,
                    'target_host': target_host
                },
                'timestamp': time.time()
            })
            
        except Exception as e:
            logger.error(f"Error fetching NetworkQuality metrics history: {e}")
            return jsonify({'error': str(e)}), 500
    
    @networkquality_bp.route('/metrics/summary', methods=['GET'])
    async def get_metrics_summary():
        """Get NetworkQuality metrics summary statistics"""
        try:
            if not database or not database.db:
                return jsonify({'error': 'Database not available'}), 500
            
            hours = int(request.args.get('hours', 24))
            start_time = time.time() - (hours * 3600)
            
            # Summary query
            query = """
                SELECT 
                    COUNT(*) as total_measurements,
                    AVG(rpm_average) as avg_rpm,
                    MIN(rpm_average) as min_rpm,
                    MAX(rpm_average) as max_rpm,
                    AVG(max_bufferbloat_ms) as avg_bufferbloat,
                    MAX(max_bufferbloat_ms) as max_bufferbloat,
                    AVG(download_throughput_mbps) as avg_download_mbps,
                    AVG(upload_throughput_mbps) as avg_upload_mbps,
                    AVG(overall_quality_score) as avg_quality_score,
                    COUNT(CASE WHEN quality_rating = 'excellent' THEN 1 END) as excellent_count,
                    COUNT(CASE WHEN quality_rating = 'good' THEN 1 END) as good_count,
                    COUNT(CASE WHEN quality_rating = 'fair' THEN 1 END) as fair_count,
                    COUNT(CASE WHEN quality_rating = 'poor' THEN 1 END) as poor_count,
                    COUNT(CASE WHEN quality_rating = 'error' THEN 1 END) as error_count,
                    COUNT(CASE WHEN bufferbloat_severity = 'severe' THEN 1 END) as severe_bufferbloat_count,
                    COUNT(CASE WHEN bufferbloat_severity = 'moderate' THEN 1 END) as moderate_bufferbloat_count,
                    COUNT(CASE WHEN congestion_detected = 1 THEN 1 END) as congestion_detected_count
                FROM network_quality_rs_metrics 
                WHERE timestamp >= ? AND error IS NULL
            """
            
            cursor = await database.db.execute(query, (start_time,))
            row = await cursor.fetchone()
            
            if not row or row[0] == 0:
                return jsonify({
                    'status': 'success',
                    'data': {
                        'message': 'No NetworkQuality metrics found for the specified period',
                        'total_measurements': 0
                    },
                    'period_hours': hours,
                    'timestamp': time.time()
                })
            
            columns = [description[0] for description in cursor.description]
            summary = dict(zip(columns, row))
            
            # Calculate percentages
            total = summary['total_measurements']
            if total > 0:
                summary['quality_distribution'] = {
                    'excellent': round((summary['excellent_count'] / total) * 100, 1),
                    'good': round((summary['good_count'] / total) * 100, 1),
                    'fair': round((summary['fair_count'] / total) * 100, 1),
                    'poor': round((summary['poor_count'] / total) * 100, 1),
                    'error': round((summary['error_count'] / total) * 100, 1)
                }
                
                summary['bufferbloat_distribution'] = {
                    'severe': round((summary['severe_bufferbloat_count'] / total) * 100, 1),
                    'moderate': round((summary['moderate_bufferbloat_count'] / total) * 100, 1),
                    'mild_or_none': round((total - summary['severe_bufferbloat_count'] - summary['moderate_bufferbloat_count']) / total * 100, 1)
                }
                
                summary['congestion_percentage'] = round((summary['congestion_detected_count'] / total) * 100, 1)
            
            # Round numerical values
            for key in ['avg_rpm', 'min_rpm', 'max_rpm', 'avg_bufferbloat', 'max_bufferbloat',
                       'avg_download_mbps', 'avg_upload_mbps', 'avg_quality_score']:
                if summary.get(key) is not None:
                    summary[key] = round(summary[key], 2)
            
            return jsonify({
                'status': 'success',
                'data': summary,
                'period_hours': hours,
                'timestamp': time.time()
            })
            
        except Exception as e:
            logger.error(f"Error generating NetworkQuality metrics summary: {e}")
            return jsonify({'error': str(e)}), 500
    
    @networkquality_bp.route('/test/run', methods=['POST'])
    async def run_test():
        """Trigger a manual NetworkQuality test"""
        try:
            if not nq_collector:
                return jsonify({'error': 'NetworkQuality collector not available'}), 503
            
            # Parse request parameters
            data = request.get_json() or {}
            force = data.get('force', False)
            
            logger.info("Manual NetworkQuality test triggered via API")
            
            # Run the test
            start_time = time.time()
            metrics = await nq_collector.collect_network_quality(force=force)
            duration = time.time() - start_time
            
            if not metrics:
                return jsonify({
                    'status': 'error',
                    'error': 'Test failed to produce metrics',
                    'duration_seconds': round(duration, 2)
                }), 500
            
            result = {
                'status': 'success',
                'data': metrics.to_dict(),
                'duration_seconds': round(duration, 2),
                'triggered_at': start_time,
                'completed_at': time.time()
            }
            
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Error running manual NetworkQuality test: {e}")
            return jsonify({
                'status': 'error',
                'error': str(e),
                'duration_seconds': time.time() - start_time if 'start_time' in locals() else 0
            }), 500
    
    @networkquality_bp.route('/status', methods=['GET'])
    async def get_status():
        """Get NetworkQuality service status"""
        try:
            status = {
                'collector_available': nq_collector is not None,
                'database_available': database is not None and database.db is not None,
                'last_measurement': None,
                'service_health': 'unknown'
            }
            
            # Get last measurement time
            if database and database.db:
                query = "SELECT timestamp FROM network_quality_rs_metrics ORDER BY timestamp DESC LIMIT 1"
                cursor = await database.db.execute(query)
                row = await cursor.fetchone()
                if row:
                    status['last_measurement'] = row[0]
                    status['last_measurement_ago_seconds'] = time.time() - row[0]
            
            # Determine service health
            if status['collector_available'] and status['database_available']:
                if status['last_measurement']:
                    age = time.time() - status['last_measurement']
                    if age < 3600:  # Less than 1 hour
                        status['service_health'] = 'healthy'
                    elif age < 7200:  # Less than 2 hours
                        status['service_health'] = 'degraded'
                    else:
                        status['service_health'] = 'stale'
                else:
                    status['service_health'] = 'no_data'
            else:
                status['service_health'] = 'unavailable'
            
            return jsonify({
                'status': 'success',
                'data': status,
                'timestamp': time.time()
            })
            
        except Exception as e:
            logger.error(f"Error getting NetworkQuality status: {e}")
            return jsonify({'error': str(e)}), 500
    
    @networkquality_bp.route('/recommendations', methods=['GET'])
    async def get_recommendations():
        """Get recent NetworkQuality recommendations"""
        try:
            if not database or not database.db:
                return jsonify({'error': 'Database not available'}), 500
            
            hours = int(request.args.get('hours', 24))
            start_time = time.time() - (hours * 3600)
            
            query = """
                SELECT timestamp, target_host, quality_rating, recommendations 
                FROM network_quality_rs_metrics 
                WHERE timestamp >= ? 
                AND recommendations IS NOT NULL 
                AND recommendations != '[]'
                ORDER BY timestamp DESC 
                LIMIT 50
            """
            
            cursor = await database.db.execute(query, (start_time,))
            rows = await cursor.fetchall()
            
            recommendations = []
            for row in rows:
                try:
                    recs = json.loads(row[3]) if row[3] else []
                    if recs:  # Only include non-empty recommendations
                        recommendations.append({
                            'timestamp': row[0],
                            'target_host': row[1],
                            'quality_rating': row[2],
                            'recommendations': recs
                        })
                except json.JSONDecodeError:
                    continue
            
            return jsonify({
                'status': 'success',
                'data': recommendations,
                'count': len(recommendations),
                'period_hours': hours,
                'timestamp': time.time()
            })
            
        except Exception as e:
            logger.error(f"Error fetching NetworkQuality recommendations: {e}")
            return jsonify({'error': str(e)}), 500
    
    return networkquality_bp

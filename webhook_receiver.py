#!/usr/bin/env python3

from flask import Flask, request, jsonify
import json
import logging
from datetime import datetime
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('webhook_alerts.log')
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', 'your-secret-token-here')
ALERT_LOG_FILE = 'alerts.json'

def save_alert_to_file(alert_data):
    try:
        alerts = []
        if os.path.exists(ALERT_LOG_FILE):
            with open(ALERT_LOG_FILE, 'r') as f:
                alerts = json.load(f)
        
        alert_data['received_at'] = datetime.utcnow().isoformat()
        alerts.append(alert_data)
        
        alerts = alerts[-1000:]
        
        with open(ALERT_LOG_FILE, 'w') as f:
            json.dump(alerts, f, indent=2)
            
        logger.info(f"Alert saved to {ALERT_LOG_FILE}")
    except Exception as e:
        logger.error(f"Failed to save alert to file: {e}")

def process_model_anomaly(alert_data):
    details = alert_data.get('details', {})
    enhanced_diagnosis = alert_data.get('enhanced_diagnosis', {})
    
    device = details.get('device', 'Unknown')
    domain = details.get('domain', 'Unknown')
    primary_issue = enhanced_diagnosis.get('primary_issue', 'Unknown')
    severity = enhanced_diagnosis.get('severity', 'Low')
    
    logger.info(f"🚨 MODEL ANOMALY: {device} -> {domain}")
    logger.info(f"   Issue: {primary_issue} (Severity: {severity})")
    logger.info(f"   Primary Metric: {details.get('primary_metric')} = {details.get('primary_value')}")
    
    insights = enhanced_diagnosis.get('insights', [])
    if insights:
        logger.info(f"   AI Insights:")
        for insight in insights:
            logger.info(f"     • {insight}")
    
    recommendations = enhanced_diagnosis.get('recommendations', [])
    if recommendations:
        logger.info(f"   Recommendations:")
        for rec in recommendations:
            logger.info(f"     • {rec}")

def process_intelligent_anomaly(alert_data):
    details = alert_data.get('details', {})
    enhanced_diagnosis = alert_data.get('enhanced_diagnosis', {})
    
    device = details.get('device', 'Unknown')
    domain = details.get('domain', 'Unknown')
    primary_issue = enhanced_diagnosis.get('primary_issue', 'Unknown')
    severity = enhanced_diagnosis.get('severity', 'Low')
    confidence = enhanced_diagnosis.get('confidence', 0.0)
    
    logger.info(f"🧠 INTELLIGENT ANOMALY: {device} -> {domain}")
    logger.info(f"   Issue: {primary_issue} (Severity: {severity}, Confidence: {confidence:.0%})")
    logger.info(f"   Current Value: {details.get('primary_value')}")
    
    if 'baseline_comparison' in alert_data:
        baseline = alert_data['baseline_comparison']
        logger.info(f"   Baseline: {baseline.get('baseline_value')}")
        logger.info(f"   Deviation: {baseline.get('deviation_factor'):.1f}x")
    
    if 'active_test_results' in alert_data:
        tests = alert_data['active_test_results']
        logger.info(f"   Active Tests:")
        if tests.get('tcp_connect_time'):
            logger.info(f"     TCP: {tests['tcp_connect_time']:.1f}ms")
        if tests.get('ping_avg_time'):
            logger.info(f"     Ping: {tests['ping_avg_time']:.1f}ms")
        if tests.get('ping_packet_loss', 0) > 0:
            logger.info(f"     Loss: {tests['ping_packet_loss']:.1f}%")

def process_data_alert(alert_data):
    alert_type = alert_data.get('alert_type')
    details = alert_data.get('details', {})
    
    actual_points = details.get('actual_points', 0)
    expected_points = details.get('expected_points', 0)
    
    if alert_type == "blank_data":
        logger.warning(f"📉 BLANK DATA: No data received for monitoring window")
    elif alert_type == "patchy_data":
        logger.warning(f"📊 PATCHY DATA: Received {actual_points}/{expected_points} expected points")

@app.route('/webhook/alerts', methods=['POST'])
def receive_alert():
    try:
        if request.content_type != 'application/json':
            logger.error(f"Invalid content type: {request.content_type}")
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        try:
            alert_data = request.get_json()
            if not alert_data:
                return jsonify({'error': 'Empty or invalid JSON payload'}), 400
        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")
            return jsonify({'error': 'Invalid JSON format'}), 400
        
        auth_header = request.headers.get('Authorization')
        if auth_header:
            if auth_header != f"Bearer {WEBHOOK_SECRET}":
                logger.error("Invalid authorization token")
                return jsonify({'error': 'Unauthorized'}), 401
        
        alert_type = alert_data.get('alert_type', 'unknown')
        logger.info(f"📩 Received webhook alert: {alert_type}")
        
        save_alert_to_file(alert_data)
        
        if alert_type == "model_anomaly":
            process_model_anomaly(alert_data)
        elif alert_type == "intelligent_anomaly":
            process_intelligent_anomaly(alert_data)
        elif alert_type in ["patchy_data", "blank_data"]:
            process_data_alert(alert_data)
        elif alert_type == "model_resolved":
            details = alert_data.get('details', {})
            logger.info(f"✅ RESOLVED: {details.get('device', 'Unknown')} -> {details.get('domain', 'Unknown')}")
        else:
            logger.warning(f"Unknown alert type: {alert_type}")
        
        return jsonify({
            'status': 'success',
            'message': f'Alert {alert_type} processed successfully',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@app.route('/webhook/test', methods=['GET'])
def test_endpoint():
    return jsonify({
        'status': 'healthy',
        'message': 'Webhook receiver is running',
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/alerts/recent', methods=['GET'])
def get_recent_alerts():
    try:
        if os.path.exists(ALERT_LOG_FILE):
            with open(ALERT_LOG_FILE, 'r') as f:
                alerts = json.load(f)
            
            limit = int(request.args.get('limit', 10))
            recent_alerts = alerts[-limit:]
            
            return jsonify({
                'alerts': recent_alerts,
                'total_count': len(alerts),
                'returned_count': len(recent_alerts)
            })
        else:
            return jsonify({'alerts': [], 'total_count': 0, 'returned_count': 0})
    except Exception as e:
        logger.error(f"Error retrieving alerts: {e}")
        return jsonify({'error': 'Failed to retrieve alerts'}), 500

@app.route('/alerts/stats', methods=['GET'])
def get_alert_stats():
    try:
        if os.path.exists(ALERT_LOG_FILE):
            with open(ALERT_LOG_FILE, 'r') as f:
                alerts = json.load(f)
            
            total_alerts = len(alerts)
            alert_types = {}
            severity_counts = {}
            
            for alert in alerts:
                alert_type = alert.get('alert_type', 'unknown')
                alert_types[alert_type] = alert_types.get(alert_type, 0) + 1
                
                if alert_type in ["model_anomaly", "intelligent_anomaly"]:
                    severity = alert.get('enhanced_diagnosis', {}).get('severity', 'Unknown')
                    severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            return jsonify({
                'total_alerts': total_alerts,
                'alert_types': alert_types,
                'severity_counts': severity_counts
            })
        else:
            return jsonify({
                'total_alerts': 0,
                'alert_types': {},
                'severity_counts': {}
            })
    except Exception as e:
        logger.error(f"Error calculating stats: {e}")
        return jsonify({'error': 'Failed to calculate stats'}), 500

if __name__ == '__main__':
    logger.info("Starting webhook receiver...")
    logger.info(f"Webhook endpoint will be: http://localhost:11450/webhook/alerts")
    logger.info(f"Test endpoint: http://localhost:5000/webhook/test")
    logger.info(f"Recent alerts API: http://localhost:5000/alerts/recent")
    logger.info(f"Alert stats API: http://localhost:5000/alerts/stats")
    
    app.run(
        host='0.0.0.0',
        port=11500,
        debug=False
    )

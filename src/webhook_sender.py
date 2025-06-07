import requests
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Any
import numpy as np
logger = logging.getLogger(__name__)

class WebhookSender:
    def __init__(self, webhook_url: str, headers: Dict[str, str] = None, 
                 timeout: int = 15, retry_attempts: int = 3, retry_delay: int = 5):
        self.webhook_url = webhook_url
        self.headers = headers or {'Content-Type': 'application/json'}
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay

    def _convert_to_json_serializable(self, obj):
        """Convert numpy types to Python native types for JSON serialization"""
        if isinstance(obj, np.float32) or isinstance(obj, np.float64):
            return float(obj)
        elif isinstance(obj, np.int32) or isinstance(obj, np.int64):
            return int(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: self._convert_to_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_json_serializable(v) for v in obj]
        else:
            return obj

    def send_model_anomaly_alert(self, device: str, domain: str, metric: str, 
                                value: float, severity: str, confidence: float = None,
                                baseline_value: float = None, deviation_factor: float = None,
                                insights: list = None, recommendations: list = None,
                                test_results: Dict = None) -> bool:
        
        payload = {
            'alert_type': 'model_anomaly',
            'timestamp': datetime.now().isoformat(),
            'details': {
                'device': device,
                'domain': domain,
                'primary_metric': metric,
                'primary_value': self._convert_to_json_serializable(value)
            },
            'enhanced_diagnosis': {
                'primary_issue': f'High {metric.replace("_", " ").title()}',
                'severity': severity,
                'confidence': self._convert_to_json_serializable(confidence) if confidence else 0.0,
                'baseline_value': self._convert_to_json_serializable(baseline_value) if baseline_value else 0.0,
                'deviation_factor': self._convert_to_json_serializable(deviation_factor) if deviation_factor else 1.0,
                'insights': insights or [],
                'recommendations': recommendations or []
            }
        }
        
        if test_results:
            payload['active_test_results'] = self._convert_to_json_serializable(test_results)
        
        return self._send_webhook(payload)

    def send_model_anomaly_alert(self, device: str, domain: str, metric: str, 
                                value: float, severity: str, confidence: float = None,
                                baseline_value: float = None, deviation_factor: float = None,
                                insights: list = None, recommendations: list = None,
                                test_results: Dict = None) -> bool:
        
        payload = {
            'alert_type': 'model_anomaly',
            'timestamp': datetime.now().isoformat(),
            'details': {
                'device': device,
                'domain': domain,
                'primary_metric': metric,
                'primary_value': value
            },
            'enhanced_diagnosis': {
                'primary_issue': f'High {metric.replace("_", " ").title()}',
                'severity': severity,
                'confidence': confidence or 0.0,
                'baseline_value': baseline_value or 0.0,
                'deviation_factor': deviation_factor or 1.0,
                'insights': insights or [],
                'recommendations': recommendations or []
            }
        }
        
        if test_results:
            payload['active_test_results'] = test_results
        
        return self._send_webhook(payload)
    
    def send_intelligent_anomaly_alert(self, anomaly_data: Dict, validation_data: Dict = None) -> bool:
        payload = {
            'alert_type': 'intelligent_anomaly',
            'timestamp': anomaly_data.get('timestamp', datetime.now().isoformat()),
            'details': {
                'device': anomaly_data.get('device'),
                'domain': anomaly_data.get('domain'),
                'primary_metric': 'response_time',
                'primary_value': anomaly_data.get('current_value', 0)
            },
            'enhanced_diagnosis': {
                'primary_issue': anomaly_data.get('issue_type', 'unknown').replace('_', ' ').title(),
                'severity': anomaly_data.get('severity', 'Medium'),
                'confidence': anomaly_data.get('confidence', 0.0),
                'baseline_value': anomaly_data.get('baseline_value', 0),
                'deviation_factor': anomaly_data.get('deviation_factor', 1.0),
                'insights': [],
                'recommendations': []
            }
        }
        
        if validation_data:
            root_causes = validation_data.get('root_cause_analysis', [])
            payload['enhanced_diagnosis']['insights'].extend(root_causes)
            
            recommendations = validation_data.get('recommendations', [])
            payload['enhanced_diagnosis']['recommendations'].extend(recommendations)
            
            test_results = validation_data.get('test_results', {})
            if test_results:
                payload['active_test_results'] = {
                    'tcp_connect_time': test_results.get('tcp_connect_time'),
                    'dns_resolution_time': test_results.get('dns_resolution_time'),
                    'three_way_handshake_success': test_results.get('three_way_handshake_success', False),
                    'ping_avg_time': test_results.get('ping_avg_time'),
                    'ping_packet_loss': test_results.get('ping_packet_loss', 0),
                    'traceroute_hops': test_results.get('traceroute_hops', 0),
                    'traceroute_success': test_results.get('traceroute_success', False)
                }
            
            payload['baseline_comparison'] = {
                'current_value': anomaly_data.get('current_value', 0),
                'baseline_value': anomaly_data.get('baseline_value', 0),
                'deviation_factor': anomaly_data.get('deviation_factor', 1.0),
                'z_score': anomaly_data.get('additional_context', {}).get('z_score', 0)
            }
        
        return self._send_webhook(payload)
    
    def send_system_alert(self, alert_type: str, message: str, severity: str = 'Medium') -> bool:
        payload = {
            'alert_type': alert_type,
            'timestamp': datetime.now().isoformat(),
            'details': {
                'message': message,
                'severity': severity
            }
        }
        return self._send_webhook(payload)
    
    def send_data_quality_alert(self, alert_type: str, actual_points: int, 
                               expected_points: int, missing_percentage: float) -> bool:
        payload = {
            'alert_type': alert_type,
            'timestamp': datetime.now().isoformat(),
            'details': {
                'actual_points': actual_points,
                'expected_points': expected_points,
                'missing_percentage': missing_percentage
            }
        }
        return self._send_webhook(payload)
    
    def send_custom_alert(self, payload: Dict[str, Any]) -> bool:
        return self._send_webhook(payload)
    
    def _send_webhook(self, payload: Dict[str, Any]) -> bool:
        import time
        
        for attempt in range(self.retry_attempts):
            try:
                response = requests.post(
                    self.webhook_url,
                    json=payload,
                    headers=self.headers,
                    timeout=self.timeout
                )
                
                if 200 <= response.status_code < 300:
                    logger.debug(f"Webhook sent successfully: {response.status_code}")
                    return True
                else:
                    logger.warning(f"Webhook returned status {response.status_code}: {response.text}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Webhook timeout (attempt {attempt + 1}/{self.retry_attempts})")
            except requests.exceptions.ConnectionError:
                logger.warning(f"Webhook connection error (attempt {attempt + 1}/{self.retry_attempts})")
            except Exception as e:
                logger.error(f"Webhook error (attempt {attempt + 1}/{self.retry_attempts}): {e}")
            
            if attempt < self.retry_attempts - 1:
                time.sleep(self.retry_delay)
        
        logger.error(f"Failed to send webhook after {self.retry_attempts} attempts")
        return False

def create_webhook_sender(config: dict) -> Optional[WebhookSender]:
    webhook_config = config.get('webhook_alerting', {})
    
    if not webhook_config.get('enabled', False):
        return None
    
    webhook_url = webhook_config.get('url')
    if not webhook_url:
        return None
    
    headers = webhook_config.get('headers', {})
    timeout = webhook_config.get('timeout_seconds', 15)
    retry_attempts = webhook_config.get('retry_attempts', 3)
    retry_delay = webhook_config.get('retry_delay_seconds', 5)
    
    return WebhookSender(
        webhook_url=webhook_url,
        headers=headers,
        timeout=timeout,
        retry_attempts=retry_attempts,
        retry_delay=retry_delay
    )

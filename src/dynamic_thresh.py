#!/usr/bin/env python3
"""
Dynamic Threshold Adjustment System
===================================

Intelligent threshold management that adapts to network behavior patterns:
- Statistical analysis for threshold optimization
- Seasonal pattern recognition
- Alert fatigue reduction
- Multi-factor scoring
- Confidence-based adjustments
"""

import logging
import time
import numpy as np
import statistics
from collections import deque, defaultdict
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import json
import threading

logger = logging.getLogger(__name__)

@dataclass
class ThresholdConfig:
    """Configuration for a specific threshold"""
    metric_name: str
    current_value: float
    base_value: float
    confidence: float
    last_updated: float
    adjustment_count: int
    false_positive_rate: float
    false_negative_rate: float
    auto_adjust: bool = True
    min_value: Optional[float] = None
    max_value: Optional[float] = None

@dataclass
class AlertEvent:
    """Alert event for threshold analysis"""
    timestamp: float
    metric_name: str
    value: float
    threshold: float
    is_true_positive: Optional[bool] = None
    severity: str = "medium"
    acknowledged: bool = False
    resolved: bool = False
    resolution_time: Optional[float] = None

class StatisticalAnalyzer:
    """Statistical analysis for threshold optimization"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.data_windows = {}
        
    def add_sample(self, metric_name: str, value: float, timestamp: float):
        """Add a sample to the statistical window"""
        
        if metric_name not in self.data_windows:
            self.data_windows[metric_name] = deque(maxlen=self.window_size)
        
        self.data_windows[metric_name].append((timestamp, value))
    
    def calculate_optimal_threshold(self, metric_name: str, 
                                  percentile: float = 95.0,
                                  seasonal_adjust: bool = True) -> Optional[float]:
        """Calculate optimal threshold using statistical analysis"""
        
        if metric_name not in self.data_windows:
            return None
        
        data = list(self.data_windows[metric_name])
        if len(data) < 30:  # Need minimum samples
            return None
        
        values = [point[1] for point in data]
        
        # Basic statistical threshold
        threshold = np.percentile(values, percentile)
        
        if seasonal_adjust:
            # Adjust for seasonal patterns
            seasonal_factor = self._calculate_seasonal_factor(data)
            threshold *= seasonal_factor
        
        return threshold
    
    def _calculate_seasonal_factor(self, data: List[Tuple[float, float]]) -> float:
        """Calculate seasonal adjustment factor"""
        
        if len(data) < 144:  # Less than 24 hours of data
            return 1.0
        
        try:
            # Group by hour of day
            hourly_data = defaultdict(list)
            
            for timestamp, value in data:
                hour = datetime.fromtimestamp(timestamp).hour
                hourly_data[hour].append(value)
            
            # Calculate current hour average vs overall average
            current_hour = datetime.now().hour
            overall_avg = statistics.mean([v for v in data])
            
            if current_hour in hourly_data and hourly_data[current_hour]:
                current_hour_avg = statistics.mean(hourly_data[current_hour])
                seasonal_factor = current_hour_avg / overall_avg
                
                # Limit adjustment to reasonable range
                return max(0.5, min(2.0, seasonal_factor))
            
        except Exception as e:
            logger.debug(f"Error calculating seasonal factor: {e}")
        
        return 1.0
    
    def detect_anomalies_in_data(self, metric_name: str, 
                                method: str = "iqr") -> List[Tuple[float, float]]:
        """Detect anomalies in historical data"""
        
        if metric_name not in self.data_windows:
            return []
        
        data = list(self.data_windows[metric_name])
        if len(data) < 50:
            return []
        
        values = [point[1] for point in data]
        anomalies = []
        
        if method == "iqr":
            # Interquartile Range method
            q1 = np.percentile(values, 25)
            q3 = np.percentile(values, 75)
            iqr = q3 - q1
            
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            for timestamp, value in data:
                if value < lower_bound or value > upper_bound:
                    anomalies.append((timestamp, value))
        
        elif method == "zscore":
            # Z-score method
            mean_val = statistics.mean(values)
            std_val = statistics.stdev(values) if len(values) > 1 else 1
            
            for timestamp, value in data:
                zscore = abs((value - mean_val) / std_val) if std_val > 0 else 0
                if zscore > 3:  # 3 standard deviations
                    anomalies.append((timestamp, value))
        
        return anomalies

class AlertAnalyzer:
    """Analyze alert patterns for threshold optimization"""
    
    def __init__(self, retention_hours: int = 168):  # 1 week
        self.retention_hours = retention_hours
        self.alert_history = deque(maxlen=10000)
        self.feedback_data = {}  # metric_name -> List[feedback]
        
    def record_alert(self, alert: AlertEvent):
        """Record an alert event"""
        self.alert_history.append(alert)
        
        # Clean old alerts
        cutoff_time = time.time() - (self.retention_hours * 3600)
        while self.alert_history and self.alert_history[0].timestamp < cutoff_time:
            self.alert_history.popleft()
    
    def record_feedback(self, metric_name: str, threshold: float, 
                       is_true_positive: bool, value: float):
        """Record feedback on alert accuracy"""
        
        if metric_name not in self.feedback_data:
            self.feedback_data[metric_name] = []
        
        self.feedback_data[metric_name].append({
            'timestamp': time.time(),
            'threshold': threshold,
            'value': value,
            'is_true_positive': is_true_positive
        })
        
        # Keep only recent feedback
        cutoff_time = time.time() - (self.retention_hours * 3600)
        self.feedback_data[metric_name] = [
            fb for fb in self.feedback_data[metric_name] 
            if fb['timestamp'] > cutoff_time
        ]
    
    def calculate_alert_metrics(self, metric_name: str) -> Dict[str, float]:
        """Calculate alert performance metrics"""
        
        # Get recent alerts for this metric
        recent_alerts = [
            alert for alert in self.alert_history 
            if alert.metric_name == metric_name and 
            alert.is_true_positive is not None
        ]
        
        if not recent_alerts:
            return {
                'false_positive_rate': 0.0,
                'false_negative_rate': 0.0,
                'precision': 1.0,
                'recall': 1.0,
                'alert_frequency': 0.0
            }
        
        # Calculate metrics
        true_positives = sum(1 for alert in recent_alerts if alert.is_true_positive)
        false_positives = sum(1 for alert in recent_alerts if not alert.is_true_positive)
        
        total_alerts = len(recent_alerts)
        
        false_positive_rate = false_positives / total_alerts if total_alerts > 0 else 0
        precision = true_positives / total_alerts if total_alerts > 0 else 0
        
        # Alert frequency (alerts per hour)
        time_span = max(24, (time.time() - recent_alerts[0].timestamp) / 3600)
        alert_frequency = total_alerts / time_span
        
        # Estimate recall from feedback data
        recall = self._estimate_recall(metric_name)
        
        return {
            'false_positive_rate': false_positive_rate,
            'false_negative_rate': 1 - recall,
            'precision': precision,
            'recall': recall,
            'alert_frequency': alert_frequency
        }
    
    def _estimate_recall(self, metric_name: str) -> float:
        """Estimate recall from feedback data"""
        
        if metric_name not in self.feedback_data:
            return 1.0
        
        feedback = self.feedback_data[metric_name]
        if not feedback:
            return 1.0
        
        # Simple estimation: ratio of true positives to total positive feedback
        true_positives = sum(1 for fb in feedback if fb['is_true_positive'])
        total_positives = len(feedback)
        
        return true_positives / total_positives if total_positives > 0 else 1.0

class DynamicThresholdManager:
    """Main dynamic threshold management system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.thresholds = {}  # metric_name -> ThresholdConfig
        self.analyzer = StatisticalAnalyzer(
            window_size=config.get('analysis_window_size', 1000)
        )
        self.alert_analyzer = AlertAnalyzer(
            retention_hours=config.get('alert_retention_hours', 168)
        )
        
        # Adjustment parameters
        self.adjustment_interval = config.get('adjustment_interval_seconds', 3600)
        self.min_confidence = config.get('min_confidence', 0.3)
        self.max_adjustment_factor = config.get('max_adjustment_factor', 0.2)
        
        # Threading
        self._lock = threading.Lock()
        self._adjustment_thread = None
        self._running = False
        
        # Performance tracking
        self.adjustment_history = deque(maxlen=1000)
        
    def initialize(self, initial_thresholds: Dict[str, float]):
        """Initialize with base thresholds"""
        
        for metric_name, threshold_value in initial_thresholds.items():
            self.thresholds[metric_name] = ThresholdConfig(
                metric_name=metric_name,
                current_value=threshold_value,
                base_value=threshold_value,
                confidence=1.0,
                last_updated=time.time(),
                adjustment_count=0,
                false_positive_rate=0.0,
                false_negative_rate=0.0
            )
        
        logger.info(f"Initialized dynamic thresholds for {len(initial_thresholds)} metrics")
    
    def start(self):
        """Start the dynamic threshold adjustment process"""
        
        self._running = True
        self._adjustment_thread = threading.Thread(
            target=self._adjustment_loop, daemon=True
        )
        self._adjustment_thread.start()
        
        logger.info("Dynamic threshold adjustment started")
    
    def stop(self):
        """Stop the dynamic threshold adjustment process"""
        
        self._running = False
        if self._adjustment_thread and self._adjustment_thread.is_alive():
            self._adjustment_thread.join(timeout=5)
        
        logger.info("Dynamic threshold adjustment stopped")
    
    def add_measurement(self, metric_name: str, value: float, timestamp: float = None):
        """Add a measurement for threshold analysis"""
        
        if timestamp is None:
            timestamp = time.time()
        
        # Add to statistical analyzer
        self.analyzer.add_sample(metric_name, value, timestamp)
        
        # Initialize threshold if needed
        if metric_name not in self.thresholds:
            self._initialize_threshold(metric_name, value)
    
    def record_alert(self, metric_name: str, value: float, threshold: float,
                    is_true_positive: Optional[bool] = None, severity: str = "medium"):
        """Record an alert for analysis"""
        
        alert = AlertEvent(
            timestamp=time.time(),
            metric_name=metric_name,
            value=value,
            threshold=threshold,
            is_true_positive=is_true_positive,
            severity=severity
        )
        
        self.alert_analyzer.record_alert(alert)
    
    def provide_feedback(self, metric_name: str, threshold: float, 
                        value: float, is_true_positive: bool):
        """Provide feedback on alert accuracy"""
        
        self.alert_analyzer.record_feedback(
            metric_name, threshold, is_true_positive, value
        )
        
        # Trigger immediate adjustment if feedback indicates poor performance
        if not is_true_positive:
            self._adjust_threshold_immediately(metric_name)
    
    def get_threshold(self, metric_name: str) -> Optional[float]:
        """Get current threshold for a metric"""
        
        with self._lock:
            if metric_name in self.thresholds:
                return self.thresholds[metric_name].current_value
            return None
    
    def get_threshold_config(self, metric_name: str) -> Optional[ThresholdConfig]:
        """Get full threshold configuration"""
        
        with self._lock:
            return self.thresholds.get(metric_name)
    
    def set_threshold(self, metric_name: str, value: float, confidence: float = 1.0):
        """Manually set a threshold"""
        
        with self._lock:
            if metric_name in self.thresholds:
                config = self.thresholds[metric_name]
                config.current_value = value
                config.confidence = confidence
                config.last_updated = time.time()
                config.adjustment_count += 1
            else:
                self.thresholds[metric_name] = ThresholdConfig(
                    metric_name=metric_name,
                    current_value=value,
                    base_value=value,
                    confidence=confidence,
                    last_updated=time.time(),
                    adjustment_count=1,
                    false_positive_rate=0.0,
                    false_negative_rate=0.0
                )
        
        logger.info(f"Manual threshold set for {metric_name}: {value}")
    
    def _initialize_threshold(self, metric_name: str, initial_value: float):
        """Initialize threshold for new metric"""
        
        # Use a reasonable default based on the initial value
        threshold_value = max(initial_value * 1.5, initial_value + 10)
        
        self.thresholds[metric_name] = ThresholdConfig(
            metric_name=metric_name,
            current_value=threshold_value,
            base_value=threshold_value,
            confidence=0.5,  # Low confidence for new metric
            last_updated=time.time(),
            adjustment_count=0,
            false_positive_rate=0.0,
            false_negative_rate=0.0
        )
        
        logger.info(f"Initialized threshold for new metric {metric_name}: {threshold_value}")
    
    def _adjustment_loop(self):
        """Main adjustment loop"""
        
        while self._running:
            try:
                self._perform_adjustments()
                time.sleep(self.adjustment_interval)
            except Exception as e:
                logger.error(f"Error in threshold adjustment loop: {e}")
                time.sleep(60)
    
    def _perform_adjustments(self):
        """Perform threshold adjustments"""
        
        with self._lock:
            adjustments_made = 0
            
            for metric_name, config in self.thresholds.items():
                if not config.auto_adjust:
                    continue
                
                adjustment = self._calculate_adjustment(metric_name, config)
                
                if adjustment is not None:
                    old_value = config.current_value
                    config.current_value = adjustment['new_threshold']
                    config.confidence = adjustment['confidence']
                    config.last_updated = time.time()
                    config.adjustment_count += 1
                    config.false_positive_rate = adjustment['false_positive_rate']
                    config.false_negative_rate = adjustment['false_negative_rate']
                    
                    # Record adjustment
                    self.adjustment_history.append({
                        'timestamp': time.time(),
                        'metric_name': metric_name,
                        'old_threshold': old_value,
                        'new_threshold': config.current_value,
                        'reason': adjustment['reason'],
                        'confidence': config.confidence
                    })
                    
                    logger.info(
                        f"Adjusted threshold for {metric_name}: "
                        f"{old_value:.3f} → {config.current_value:.3f} "
                        f"(reason: {adjustment['reason']}, confidence: {config.confidence:.2f})"
                    )
                    
                    adjustments_made += 1
            
            if adjustments_made > 0:
                logger.info(f"Made {adjustments_made} threshold adjustments")
    
    def _calculate_adjustment(self, metric_name: str, 
                            config: ThresholdConfig) -> Optional[Dict[str, Any]]:
        """Calculate threshold adjustment for a metric"""
        
        # Get statistical optimal threshold
        optimal_threshold = self.analyzer.calculate_optimal_threshold(
            metric_name, percentile=95.0, seasonal_adjust=True
        )
        
        if optimal_threshold is None:
            return None
        
        # Get alert performance metrics
        alert_metrics = self.alert_analyzer.calculate_alert_metrics(metric_name)
        
        # Determine if adjustment is needed
        adjustment_needed, reason = self._should_adjust_threshold(
            config, optimal_threshold, alert_metrics
        )
        
        if not adjustment_needed:
            return None
        
        # Calculate new threshold
        new_threshold = self._calculate_new_threshold(
            config, optimal_threshold, alert_metrics
        )
        
        # Calculate confidence in adjustment
        confidence = self._calculate_adjustment_confidence(
            config, optimal_threshold, alert_metrics
        )
        
        if confidence < self.min_confidence:
            return None
        
        return {
            'new_threshold': new_threshold,
            'confidence': confidence,
            'reason': reason,
            'false_positive_rate': alert_metrics['false_positive_rate'],
            'false_negative_rate': alert_metrics['false_negative_rate']
        }
    
    def _should_adjust_threshold(self, config: ThresholdConfig, 
                               optimal_threshold: float,
                               alert_metrics: Dict[str, float]) -> Tuple[bool, str]:
        """Determine if threshold should be adjusted"""
        
        current_threshold = config.current_value
        
        # Check for high false positive rate
        if alert_metrics['false_positive_rate'] > 0.3:
            return True, "high_false_positive_rate"
        
        # Check for very low false positive rate (might be missing real issues)
        if alert_metrics['false_positive_rate'] < 0.05 and alert_metrics['alert_frequency'] < 0.1:
            return True, "possibly_too_conservative"
        
        # Check if optimal threshold significantly differs from current
        threshold_diff_ratio = abs(optimal_threshold - current_threshold) / current_threshold
        if threshold_diff_ratio > 0.2:  # 20% difference
            return True, "statistical_optimization"
        
        # Check alert frequency
        if alert_metrics['alert_frequency'] > 5:  # More than 5 alerts per hour
            return True, "high_alert_frequency"
        
        # Check if threshold hasn't been updated in a long time
        time_since_update = time.time() - config.last_updated
        if time_since_update > 86400:  # 24 hours
            return True, "periodic_update"
        
        return False, "no_adjustment_needed"
    
    def _calculate_new_threshold(self, config: ThresholdConfig,
                               optimal_threshold: float,
                               alert_metrics: Dict[str, float]) -> float:
        """Calculate new threshold value"""
        
        current_threshold = config.current_value
        
        # Start with statistical optimal
        new_threshold = optimal_threshold
        
        # Adjust based on alert metrics
        if alert_metrics['false_positive_rate'] > 0.2:
            # Increase threshold to reduce false positives
            adjustment_factor = 1 + (alert_metrics['false_positive_rate'] - 0.2) * 0.5
            new_threshold *= adjustment_factor
        
        elif alert_metrics['false_positive_rate'] < 0.05:
            # Decrease threshold to catch more issues
            adjustment_factor = 0.9
            new_threshold *= adjustment_factor
        
        # Limit adjustment to prevent drastic changes
        max_change = current_threshold * self.max_adjustment_factor
        
        if new_threshold > current_threshold + max_change:
            new_threshold = current_threshold + max_change
        elif new_threshold < current_threshold - max_change:
            new_threshold = current_threshold - max_change
        
        # Apply bounds if configured
        if config.min_value is not None:
            new_threshold = max(new_threshold, config.min_value)
        if config.max_value is not None:
            new_threshold = min(new_threshold, config.max_value)
        
        return new_threshold
    
    def _calculate_adjustment_confidence(self, config: ThresholdConfig,
                                       optimal_threshold: float,
                                       alert_metrics: Dict[str, float]) -> float:
        """Calculate confidence in threshold adjustment"""
        
        confidence = 0.5  # Base confidence
        
        # Increase confidence with more historical data
        if len(self.analyzer.data_windows.get(config.metric_name, [])) > 500:
            confidence += 0.2
        
        # Increase confidence with clear alert patterns
        if alert_metrics['false_positive_rate'] > 0.3 or alert_metrics['false_positive_rate'] < 0.05:
            confidence += 0.2
        
        # Increase confidence if threshold hasn't been adjusted recently
        time_since_last_adjustment = time.time() - config.last_updated
        if time_since_last_adjustment > 3600:  # 1 hour
            confidence += 0.1
        
        # Decrease confidence for frequent adjustments
        if config.adjustment_count > 10:
            confidence -= 0.1
        
        return max(0.0, min(1.0, confidence))
    
    def _adjust_threshold_immediately(self, metric_name: str):
        """Immediately adjust threshold based on negative feedback"""
        
        with self._lock:
            if metric_name not in self.thresholds:
                return
            
            config = self.thresholds[metric_name]
            
            # Increase threshold by 10% to reduce false positives
            new_threshold = config.current_value * 1.1
            
            # Apply bounds
            if config.max_value is not None:
                new_threshold = min(new_threshold, config.max_value)
            
            old_value = config.current_value
            config.current_value = new_threshold
            config.last_updated = time.time()
            config.adjustment_count += 1
            config.confidence = max(0.3, config.confidence - 0.1)
            
            logger.info(
                f"Immediate threshold adjustment for {metric_name}: "
                f"{old_value:.3f} → {new_threshold:.3f} (feedback-based)"
            )
    
    def get_adjustment_statistics(self) -> Dict[str, Any]:
        """Get statistics about threshold adjustments"""
        
        recent_adjustments = [
            adj for adj in self.adjustment_history
            if time.time() - adj['timestamp'] < 86400  # Last 24 hours
        ]
        
        stats = {
            'total_adjustments_24h': len(recent_adjustments),
            'metrics_with_adjustments': len(set(adj['metric_name'] for adj in recent_adjustments)),
            'adjustment_reasons': {},
            'average_confidence': 0.0,
            'threshold_stability': {}
        }
        
        if recent_adjustments:
            # Count reasons
            for adj in recent_adjustments:
                reason = adj['reason']
                stats['adjustment_reasons'][reason] = stats['adjustment_reasons'].get(reason, 0) + 1
            
            # Average confidence
            stats['average_confidence'] = statistics.mean(
                adj['confidence'] for adj in recent_adjustments
            )
        
        # Threshold stability (how often each metric is adjusted)
        for metric_name, config in self.thresholds.items():
            recent_adjustments_for_metric = sum(
                1 for adj in recent_adjustments if adj['metric_name'] == metric_name
            )
            stats['threshold_stability'][metric_name] = {
                'adjustments_24h': recent_adjustments_for_metric,
                'current_confidence': config.confidence,
                'last_updated': config.last_updated
            }
        
        return stats
    
    def export_thresholds(self) -> Dict[str, Any]:
        """Export current threshold configuration"""
        
        export_data = {
            'export_timestamp': time.time(),
            'thresholds': {},
            'statistics': self.get_adjustment_statistics()
        }
        
        for metric_name, config in self.thresholds.items():
            export_data['thresholds'][metric_name] = asdict(config)
        
        return export_data
    
    def import_thresholds(self, import_data: Dict[str, Any]) -> bool:
        """Import threshold configuration"""
        
        try:
            with self._lock:
                for metric_name, config_data in import_data.get('thresholds', {}).items():
                    self.thresholds[metric_name] = ThresholdConfig(**config_data)
            
            logger.info(f"Imported thresholds for {len(import_data.get('thresholds', {}))} metrics")
            return True
            
        except Exception as e:
            logger.error(f"Error importing thresholds: {e}")
            return False

# Utility functions

def create_default_thresholds() -> Dict[str, float]:
    """Create default threshold values for common network metrics"""
    
    return {
        'icmp_ping_time': 100.0,  # ms
        'tcp_handshake_time': 200.0,  # ms
        'dns_resolve_time': 50.0,  # ms
        'packet_loss': 5.0,  # percentage
        'jitter': 20.0,  # ms
        'http_response_time': 2000.0,  # ms
        'bandwidth_download': 10.0,  # Mbps (minimum)
        'mos_score': 3.0,  # MOS score (minimum)
        'interface_errors': 10,  # errors per minute
        'connection_errors': 3  # errors per measurement cycle
    }

def setup_dynamic_thresholds(config: Dict[str, Any]) -> DynamicThresholdManager:
    """Setup dynamic threshold manager with configuration"""
    
    threshold_config = config.get('dynamic_thresholds', {})
    
    manager = DynamicThresholdManager(threshold_config)
    
    # Initialize with default or configured thresholds
    initial_thresholds = config.get('initial_thresholds', create_default_thresholds())
    manager.initialize(initial_thresholds)
    
    return manager

# Integration function for existing monitor
def integrate_dynamic_thresholds(monitor, threshold_manager: DynamicThresholdManager):
    """Integrate dynamic thresholds with existing monitor"""
    
    # Override the anomaly detection to use dynamic thresholds
    original_detect_anomaly = monitor.detector.detect_anomaly
    
    async def enhanced_detect_anomaly(metrics):
        # Get current thresholds
        dynamic_thresholds = {}
        
        for metric_name in ['icmp_ping_time', 'tcp_handshake_time', 'dns_resolve_time']:
            threshold = threshold_manager.get_threshold(metric_name)
            if threshold is not None:
                dynamic_thresholds[metric_name] = threshold
        
        # Update detector thresholds
        if hasattr(monitor.detector, 'thresholds'):
            monitor.detector.thresholds.update(dynamic_thresholds)
        
        # Add measurement to threshold manager
        if hasattr(metrics, 'to_dict'):
            metrics_dict = metrics.to_dict()
            for metric_name, value in metrics_dict.items():
                if isinstance(value, (int, float)) and value >= 0:
                    threshold_manager.add_measurement(metric_name, value)
        
        # Perform original anomaly detection
        result = await original_detect_anomaly(metrics)
        
        # Record alert if anomaly detected
        if result.is_anomaly:
            for metric_name, contribution in result.feature_contributions.items():
                if contribution > 0.5:  # Significant contributor
                    threshold = threshold_manager.get_threshold(metric_name)
                    if threshold is not None:
                        threshold_manager.record_alert(
                            metric_name=metric_name,
                            value=metrics_dict.get(metric_name, 0),
                            threshold=threshold,
                            severity=result.severity
                        )
        
        return result
    
    # Replace the method
    monitor.detector.detect_anomaly = enhanced_detect_anomaly
    
    logger.info("Dynamic thresholds integrated with monitor")

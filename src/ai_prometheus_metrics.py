#!/usr/bin/env python3
"""
AI Model Prometheus Metrics
===========================

Export AI/ML model statistics and performance metrics for Prometheus.
"""

import time
import logging
from prometheus_client import Gauge, Counter, Histogram, Info
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class AIModelPrometheusMetrics:
    """Prometheus metrics for AI model monitoring"""
    
    def __init__(self, registry=None):
        self.registry = registry
        self._setup_metrics()
        
    def _setup_metrics(self):
        """Setup AI model specific Prometheus metrics"""
        
        # Model information
        self.model_info = Info(
            'ai_model_info',
            'Information about the AI model',
            registry=self.registry
        )
        
        # Training metrics
        self.model_training_count = Counter(
            'ai_model_training_total',
            'Total number of model training sessions',
            ['model_type', 'training_type'],
            registry=self.registry
        )
        
        self.model_training_duration = Histogram(
            'ai_model_training_duration_seconds',
            'Model training duration in seconds',
            ['model_type'],
            buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600],
            registry=self.registry
        )
        
        self.model_training_samples = Gauge(
            'ai_model_training_samples_total',
            'Total number of training samples used',
            ['model_type'],
            registry=self.registry
        )
        
        self.model_loss = Gauge(
            'ai_model_loss',
            'Current model loss value',
            ['model_type', 'loss_type'],
            registry=self.registry
        )
        
        # Inference metrics
        self.model_inference_count = Counter(
            'ai_model_inference_total',
            'Total number of model inferences',
            ['model_type'],
            registry=self.registry
        )
        
        self.model_inference_duration = Histogram(
            'ai_model_inference_duration_seconds',
            'Model inference duration in seconds',
            ['model_type'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=self.registry
        )
        
        # Anomaly detection metrics
        self.anomalies_detected_total = Counter(
            'ai_anomalies_detected_total',
            'Total number of anomalies detected',
            ['severity', 'target'],
            registry=self.registry
        )
        
        self.anomaly_score_distribution = Histogram(
            'ai_anomaly_score',
            'Distribution of anomaly scores',
            ['model_type'],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            registry=self.registry
        )
        
        self.anomaly_confidence = Gauge(
            'ai_anomaly_confidence_current',
            'Current anomaly detection confidence',
            ['model_type', 'target'],
            registry=self.registry
        )
        
        # Model performance metrics
        self.model_accuracy = Gauge(
            'ai_model_accuracy',
            'Model accuracy score',
            ['model_type', 'metric_type'],
            registry=self.registry
        )
        
        self.model_parameters = Gauge(
            'ai_model_parameters_total',
            'Total number of model parameters',
            ['model_type'],
            registry=self.registry
        )
        
        self.model_size_bytes = Gauge(
            'ai_model_size_bytes',
            'Model size in bytes',
            ['model_type'],
            registry=self.registry
        )
        
        # Baseline metrics
        self.baseline_updates_total = Counter(
            'ai_baseline_updates_total',
            'Total number of baseline updates',
            ['baseline_type', 'source'],
            registry=self.registry
        )
        
        self.baseline_deviation = Gauge(
            'ai_baseline_deviation_current',
            'Current deviation from baseline',
            ['metric_name', 'target'],
            registry=self.registry
        )
        
        # Online learning metrics
        self.online_learning_updates = Counter(
            'ai_online_learning_updates_total',
            'Total number of online learning updates',
            ['model_type'],
            registry=self.registry
        )
        
        self.online_learning_rate = Gauge(
            'ai_online_learning_rate_current',
            'Current online learning rate',
            ['model_type'],
            registry=self.registry
        )
        
        # Threshold adaptation metrics
        self.adaptive_threshold_adjustments = Counter(
            'ai_adaptive_threshold_adjustments_total',
            'Total number of adaptive threshold adjustments',
            ['metric_name', 'adjustment_reason'],
            registry=self.registry
        )
        
        self.adaptive_threshold_value = Gauge(
            'ai_adaptive_threshold_value_current',
            'Current adaptive threshold value',
            ['metric_name'],
            registry=self.registry
        )
        
        # Model health metrics
        self.model_health_score = Gauge(
            'ai_model_health_score',
            'Overall model health score (0-100)',
            ['model_type'],
            registry=self.registry
        )
        
        self.model_last_trained = Gauge(
            'ai_model_last_trained_timestamp',
            'Timestamp of last model training',
            ['model_type'],
            registry=self.registry
        )
        
        self.model_age_seconds = Gauge(
            'ai_model_age_seconds',
            'Age of the model in seconds',
            ['model_type'],
            registry=self.registry
        )
    
    def update_training_metrics(self, model_type: str, training_type: str, 
                               duration: float, samples: int, loss: float):
        """Update model training metrics"""
        
        self.model_training_count.labels(
            model_type=model_type,
            training_type=training_type
        ).inc()
        
        self.model_training_duration.labels(
            model_type=model_type
        ).observe(duration)
        
        self.model_training_samples.labels(
            model_type=model_type
        ).set(samples)
        
        self.model_loss.labels(
            model_type=model_type,
            loss_type='mse'
        ).set(loss)
        
        self.model_last_trained.labels(
            model_type=model_type
        ).set(time.time())
    
    def update_inference_metrics(self, model_type: str, duration: float):
        """Update model inference metrics"""
        
        self.model_inference_count.labels(
            model_type=model_type
        ).inc()
        
        self.model_inference_duration.labels(
            model_type=model_type
        ).observe(duration)
    
    def update_anomaly_metrics(self, model_type: str, target: str, 
                              score: float, confidence: float, severity: str):
        """Update anomaly detection metrics"""
        
        self.anomalies_detected_total.labels(
            severity=severity,
            target=target
        ).inc()
        
        self.anomaly_score_distribution.labels(
            model_type=model_type
        ).observe(score)
        
        self.anomaly_confidence.labels(
            model_type=model_type,
            target=target
        ).set(confidence)
    
    def update_model_info(self, model_type: str, info: Dict[str, Any]):
        """Update model information"""
        
        self.model_info.info({
            'model_type': model_type,
            'version': info.get('version', '1.0.0'),
            'architecture': info.get('architecture', 'lstm_autoencoder'),
            'input_size': str(info.get('input_size', 14)),
            'hidden_size': str(info.get('hidden_size', 64)),
            'num_layers': str(info.get('num_layers', 2)),
            'quantized': str(info.get('quantized', False))
        })
        
        if 'parameters' in info:
            self.model_parameters.labels(
                model_type=model_type
            ).set(info['parameters'])
        
        if 'size_bytes' in info:
            self.model_size_bytes.labels(
                model_type=model_type
            ).set(info['size_bytes'])
    
    def update_baseline_metrics(self, baseline_type: str, source: str,
                               metric_deviations: Dict[str, float]):
        """Update baseline metrics"""
        
        self.baseline_updates_total.labels(
            baseline_type=baseline_type,
            source=source
        ).inc()
        
        for metric_name, deviation in metric_deviations.items():
            self.baseline_deviation.labels(
                metric_name=metric_name,
                target='aggregate'
            ).set(deviation)
    
    def update_online_learning_metrics(self, model_type: str, learning_rate: float):
        """Update online learning metrics"""
        
        self.online_learning_updates.labels(
            model_type=model_type
        ).inc()
        
        self.online_learning_rate.labels(
            model_type=model_type
        ).set(learning_rate)
    
    def update_threshold_metrics(self, metric_name: str, threshold_value: float,
                                adjustment_reason: str = 'adaptive'):
        """Update adaptive threshold metrics"""
        
        self.adaptive_threshold_adjustments.labels(
            metric_name=metric_name,
            adjustment_reason=adjustment_reason
        ).inc()
        
        self.adaptive_threshold_value.labels(
            metric_name=metric_name
        ).set(threshold_value)
    
    def update_model_health(self, model_type: str, health_score: float, 
                           model_age_seconds: float):
        """Update model health metrics"""
        
        self.model_health_score.labels(
            model_type=model_type
        ).set(health_score)
        
        self.model_age_seconds.labels(
            model_type=model_type
        ).set(model_age_seconds)

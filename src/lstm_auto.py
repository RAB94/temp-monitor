#!/usr/bin/env python3
"""
Enhanced LSTM Autoencoder Anomaly Detector
==========================================

Advanced PyTorch-based anomaly detection using LSTM autoencoders with:
- Temporal sequence modeling
- Attention mechanisms
- Online learning capabilities
- Edge device optimization (quantization ready)
- Seasonal pattern detection
"""

import logging
import numpy as np
import time
import torch
import torch.nn as nn
import torch.optim as optim
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from sklearn.preprocessing import RobustScaler
from typing import Dict, List, Optional, Any, Tuple
import pickle
import json
import math

logger = logging.getLogger(__name__)

@dataclass
class SequenceAnomalyResult:
    """Enhanced anomaly detection result with sequence analysis"""
    is_anomaly: bool
    anomaly_score: float
    confidence: float
    sequence_score: float
    attention_weights: Dict[str, float]
    baseline_values: Dict[str, float]
    thresholds: Dict[str, float]
    feature_contributions: Dict[str, float]
    temporal_pattern: str
    recommendation: str
    severity: str

class PositionalEncoding(nn.Module):
    """Positional encoding for temporal awareness"""
    
    def __init__(self, d_model: int, max_len: int = 5000):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len).unsqueeze(1).float()
        
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * 
                           -(math.log(10000.0) / d_model))
        
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        
        self.register_buffer('pe', pe.unsqueeze(0))
    
    def forward(self, x):
        return x + self.pe[:, :x.size(1)]

class AttentionMechanism(nn.Module):
    """Attention mechanism for feature importance"""
    
    def __init__(self, hidden_size: int):
        super().__init__()
        self.attention = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, 1),
            nn.Softmax(dim=1)
        )
    
    def forward(self, x):
        # x shape: (batch, seq_len, hidden_size)
        weights = self.attention(x)  # (batch, seq_len, 1)
        weighted = x * weights
        return weighted.sum(dim=1), weights.squeeze(-1)

class LSTMAutoEncoder(nn.Module):
    """Advanced LSTM Autoencoder with attention and positional encoding"""
    
    def __init__(self, input_size: int = 10, hidden_size: int = 64, 
                 num_layers: int = 2, sequence_length: int = 20):
        super().__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.sequence_length = sequence_length
        
        # Positional encoding
        self.pos_encoding = PositionalEncoding(input_size)
        
        # Encoder LSTM
        self.encoder_lstm = nn.LSTM(
            input_size, hidden_size, num_layers,
            batch_first=True, dropout=0.2 if num_layers > 1 else 0
        )
        
        # Attention mechanism
        self.attention = AttentionMechanism(hidden_size)
        
        # Bottleneck layer
        self.bottleneck = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 4),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_size // 4, hidden_size)
        )
        
        # Decoder LSTM
        self.decoder_lstm = nn.LSTM(
            hidden_size, hidden_size, num_layers,
            batch_first=True, dropout=0.2 if num_layers > 1 else 0
        )
        
        # Output projection
        self.output_projection = nn.Linear(hidden_size, input_size)
        
        # Initialize weights
        self.apply(self._init_weights)
    
    def _init_weights(self, module):
        """Initialize weights with Xavier uniform"""
        if isinstance(module, nn.Linear):
            nn.init.xavier_uniform_(module.weight)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.LSTM):
            for name, param in module.named_parameters():
                if 'weight' in name:
                    nn.init.xavier_uniform_(param)
                elif 'bias' in name:
                    nn.init.zeros_(param)
    
    def forward(self, x):
        batch_size, seq_len, _ = x.shape
        
        # Add positional encoding
        x_pos = self.pos_encoding(x)
        
        # Encode
        encoded, (hidden, cell) = self.encoder_lstm(x_pos)
        
        # Apply attention
        attended, attention_weights = self.attention(encoded)
        
        # Bottleneck
        bottleneck_out = self.bottleneck(attended)
        
        # Prepare for decoding
        decoder_input = bottleneck_out.unsqueeze(1).repeat(1, seq_len, 1)
        
        # Decode
        decoded, _ = self.decoder_lstm(decoder_input, (hidden, cell))
        
        # Project to output
        output = self.output_projection(decoded)
        
        return output, attention_weights

class TemporalPatternDetector:
    """Detect temporal patterns in network metrics"""
    
    def __init__(self, window_size: int = 144):  # 24 hours with 10-min intervals
        self.window_size = window_size
        self.patterns = {
            'daily': {'period': 144, 'confidence': 0.0},
            'weekly': {'period': 1008, 'confidence': 0.0},  # 7 days
            'hourly': {'period': 6, 'confidence': 0.0}      # 1 hour
        }
        
    def detect_patterns(self, data: np.ndarray) -> Dict[str, float]:
        """Detect periodic patterns using FFT"""
        if len(data) < self.window_size:
            return {}
        
        # Normalize data
        data_norm = (data - np.mean(data)) / (np.std(data) + 1e-8)
        
        # Apply FFT
        fft = np.fft.fft(data_norm)
        freqs = np.fft.fftfreq(len(data_norm))
        
        # Find dominant frequencies
        power = np.abs(fft) ** 2
        dominant_freqs = np.argsort(power)[-10:]  # Top 10 frequencies
        
        pattern_scores = {}
        
        for pattern_name, pattern_info in self.patterns.items():
            expected_freq = 1.0 / pattern_info['period']
            
            # Find closest frequency
            freq_diffs = np.abs(freqs[dominant_freqs] - expected_freq)
            closest_idx = np.argmin(freq_diffs)
            
            if freq_diffs[closest_idx] < 0.01:  # Threshold for match
                pattern_scores[pattern_name] = float(power[dominant_freqs[closest_idx]])
            else:
                pattern_scores[pattern_name] = 0.0
        
        return pattern_scores

class EnhancedLSTMAnomalyDetector:
    """Enhanced LSTM-based anomaly detector with advanced features"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Model parameters
        self.sequence_length = config.get('sequence_length', 20)
        self.input_size = config.get('input_size', 14)
        self.hidden_size = config.get('hidden_size', 64)
        self.num_layers = config.get('num_layers', 2)
        
        # Validate input size
        logger.info(f"🔧 Initializing AI model with input_size={self.input_size}, "
                    f"sequence_length={self.sequence_length}, hidden_size={self.hidden_size}")
               
        # Model components
        self.model = None
        self.optimizer = None
        self.scaler = RobustScaler()  # More robust to outliers
        self.pattern_detector = TemporalPatternDetector()
        
        # Training state
        self.is_trained = False
        self.sequence_buffer = deque(maxlen=self.sequence_length)
        self.training_sequences = deque(maxlen=1000)
        self.anomaly_scores = deque(maxlen=500)
        
        # Adaptive thresholds
        self.thresholds = {
            'reconstruction_error': 0.05,
            'sequence_score': 0.1,
            'attention_threshold': 0.8,
            'confidence_threshold': 0.7
        }
        
        # Model paths
        self.model_dir = Path(config.get('model_dir', 'data/models'))
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Seasonal baselines
        self.seasonal_baselines = {
            'hourly': deque(maxlen=24),     # 24 hours
            'daily': deque(maxlen=7),      # 7 days
            'weekly': deque(maxlen=4)      # 4 weeks
        }
    
    async def initialize(self):
        """Initialize the enhanced detector"""
        
        # Initialize LSTM autoencoder
        self.model = LSTMAutoEncoder(
            input_size=self.input_size,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers,
            sequence_length=self.sequence_length
        )
        self.model.to(self.device)
        
        self.optimizer = optim.AdamW(
            self.model.parameters(), 
            lr=0.001, 
            weight_decay=1e-5
        )
        
        logger.info("Enhanced LSTM anomaly detector initialized")
    
    def _extract_enhanced_features(self, metrics) -> np.ndarray:
        """Extract enhanced features including derived metrics"""
        
        # Handle both NetworkMetrics objects and dictionaries
        if hasattr(metrics, 'to_dict'):
            metrics_dict = metrics.to_dict()
        else:
            metrics_dict = metrics
        
        # Base features (7)
        base_features = [
            metrics_dict.get('tcp_handshake_time', 0),
            metrics_dict.get('icmp_ping_time', 0),
            metrics_dict.get('dns_resolve_time', 0),
            metrics_dict.get('packet_loss', 0),
            metrics_dict.get('jitter', 0),
            metrics_dict.get('bandwidth_download', 0),  # Changed from 'bandwidth_test'
            metrics_dict.get('connection_errors', 0)
        ]
        
        # Enhanced features (4) - to match the expected 14 total
        enhanced_features = [
            metrics_dict.get('http_response_time', 0),
            metrics_dict.get('interface_errors', 0),
            metrics_dict.get('mos_score', 0),
            metrics_dict.get('r_factor', 0)
        ]
        
        # Time-based features (3)
        timestamp = metrics_dict.get('timestamp', time.time())
        time_features = [
            (timestamp % 86400) / 86400,  # Time of day (0-1)
            (timestamp % 604800) / 604800,  # Day of week (0-1)
            math.sin(2 * math.pi * (timestamp % 86400) / 86400)  # Sine of time
        ]
        
        # Combine all features (7 + 4 + 3 = 14)
        features = base_features + enhanced_features + time_features
        
        # Handle invalid values
        features = [f if f >= 0 and not math.isnan(f) and not math.isinf(f) else 0 for f in features]
        
        # Ensure we have exactly 14 features
        if len(features) != 14:
            logger.error(f"Feature extraction error: expected 14 features, got {len(features)}")
            # Pad or truncate to 14 features
            if len(features) < 14:
                features.extend([0] * (14 - len(features)))
            else:
                features = features[:14]
        
        return np.array(features, dtype=np.float32)

    def _update_sequence_buffer(self, features: np.ndarray):
        """Update sequence buffer for temporal analysis"""
        self.sequence_buffer.append(features)
        
        # Create training sequence when buffer is full
        if len(self.sequence_buffer) == self.sequence_length:
            sequence = np.array(list(self.sequence_buffer))
            self.training_sequences.append(sequence)
            
            # Log the actual count
            logger.debug(f"📝 AI: Added training sequence. Total sequences: {len(self.training_sequences)}")

    async def detect_anomaly(self, metrics) -> SequenceAnomalyResult:
        """Enhanced anomaly detection with comprehensive activity logging"""
        self.samples_processed += 1
        # Track inference timing
        inference_start_time = time.time()
        
        # Extract features with logging
        features = self._extract_enhanced_features(metrics)
        timestamp = getattr(metrics, 'timestamp', time.time())
        target_host = getattr(metrics, 'target_host', 'unknown')
        
        # Log feature extraction details
        logger.debug(f"🔍 AI: Extracted {len(features)} features from metrics for {target_host}")
        logger.debug(f"📊 AI: Feature values - TCP: {features[0]:.2f}ms, ICMP: {features[1]:.2f}ms, "
                    f"DNS: {features[2]:.2f}ms, Loss: {features[3]:.2f}%, Jitter: {features[4]:.2f}ms")
        
        # Update sequence buffer
        self._update_sequence_buffer(features)
        buffer_size = len(self.sequence_buffer)
        logger.debug(f"📝 AI: Sequence buffer updated - current size: {buffer_size}/{self.sequence_length}")
        
         # In detect_anomaly method, fix the training trigger:
        if not self.is_trained or buffer_size < self.sequence_length:
            logger.info(f"🧠 AI: Model status - trained: {self.is_trained}, "
                       f"buffer: {buffer_size}/{self.sequence_length}")
            
            # Check if we should train
            if len(self.training_sequences) >= 50 and not self.is_trained:
                logger.info("📚 AI: Sufficient training data collected, initiating initial training...")
                await self.train_initial_model()
                
                # After training, continue with normal detection
                if self.is_trained:
                    logger.info("✅ AI: Initial training complete, switching to detection mode")
                    # Don't return early - continue with detection
                else:
                    # Only return if training failed
                    return SequenceAnomalyResult(...)           
            # Update last inference time for health monitoring
            self.last_inference_time = time.time()
            
            return SequenceAnomalyResult(
                is_anomaly=False,
                anomaly_score=0.0,
                confidence=0.0,
                sequence_score=0.0,
                attention_weights={},
                baseline_values={
                    'status': 'collecting_baseline',
                    'sequences_collected': len(self.training_sequences),
                    'buffer_size': buffer_size
                },
                thresholds=self.thresholds.copy(),
                feature_contributions={},
                temporal_pattern="learning",
                recommendation=f"Building baseline - {len(self.training_sequences)}/50 sequences collected",
                severity="info"
            )
        if is_anomaly and confidence < self.min_confidence:
            logger.debug(f"🤔 Anomaly detected but confidence too low: {confidence:.2f} < {self.min_confidence}")
            is_anomaly = False
            severity = "info"        
        # Prepare sequence for inference
        logger.debug(f"🔄 AI: Preparing sequence for inference - shape: ({self.sequence_length}, {self.input_size})")
        sequence = np.array(list(self.sequence_buffer))
        
        # Scale the sequence
        try:
            sequence_scaled = self.scaler.transform(sequence.reshape(-1, self.input_size))
            sequence_scaled = sequence_scaled.reshape(1, self.sequence_length, self.input_size)
            sequence_tensor = torch.FloatTensor(sequence_scaled).to(self.device)
            logger.debug(f"✅ AI: Sequence scaled and converted to tensor on {self.device}")
        except Exception as e:
            logger.error(f"❌ AI: Error scaling sequence: {e}")
            raise
        
        # Model inference with detailed tracking
        logger.debug(f"🤖 AI: Starting model inference for {target_host}")
        self.model.eval()
        
        with torch.no_grad():
            inference_model_start = time.time()
            
            # Forward pass through model
            reconstructed, attention_weights = self.model(sequence_tensor)
            
            model_inference_time = time.time() - inference_model_start
            logger.debug(f"⚡ AI: Model forward pass completed in {model_inference_time*1000:.2f}ms")
            
            # Calculate reconstruction error
            mse = nn.MSELoss(reduction='none')
            errors = mse(reconstructed, sequence_tensor)
            
            # Overall reconstruction error
            reconstruction_error = torch.mean(errors).item()
            logger.debug(f"📏 AI: Reconstruction error: {reconstruction_error:.6f}")
            
            # Sequence-level score (variability in errors across time steps)
            sequence_score = torch.mean(torch.std(errors, dim=1)).item()
            logger.debug(f"📈 AI: Sequence score (temporal variability): {sequence_score:.6f}")
            
            # Feature-wise contributions (which features have highest errors)
            feature_errors = torch.mean(errors, dim=(0, 1)).cpu().numpy()
            
            # Log top contributing features
            feature_names = [
                'tcp_handshake_time', 'icmp_ping_time', 'dns_resolve_time',
                'packet_loss', 'jitter', 'bandwidth_download', 'connection_errors',
                'http_response_time', 'interface_errors', 'mos_score', 'r_factor',
                'time_of_day', 'day_of_week', 'sine_time'
            ]


            top_features = sorted(
                zip(feature_names[:len(feature_errors)], feature_errors),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            
            logger.debug(f"🎯 AI: Top error contributors: " + 
                        ", ".join([f"{name}: {error:.4f}" for name, error in top_features]))
            
            # Attention analysis
            attention_np = attention_weights.cpu().numpy()[0]
            attention_variance = np.var(attention_np)
            max_attention_idx = np.argmax(attention_np)
            logger.debug(f"👁️ AI: Attention variance: {attention_variance:.4f}, "
                        f"peak attention at timestep {max_attention_idx}")
        
        # Pattern detection
        recent_scores = list(self.anomaly_scores)[-50:] if self.anomaly_scores else [0]
        pattern_scores = self.pattern_detector.detect_patterns(np.array(recent_scores))
        
        # Log pattern detection results
        if pattern_scores:
            logger.debug(f"🔄 AI: Temporal patterns detected: " + 
                        ", ".join([f"{p}: {s:.2f}" for p, s in pattern_scores.items() if s > 0]))
        
        # Determine temporal pattern
        dominant_pattern = max(pattern_scores.keys(), 
                             key=lambda k: pattern_scores[k]) if pattern_scores else "unknown"
        
        # Calculate combined anomaly score
        anomaly_score = (reconstruction_error * 0.6 + 
                        sequence_score * 0.3 + 
                        attention_variance * 0.1)
        
        logger.debug(f"🧮 AI: Combined anomaly score: {anomaly_score:.6f} "
                    f"(recon: {reconstruction_error:.4f}, seq: {sequence_score:.4f}, "
                    f"attn: {attention_variance:.4f})")
        
        # Update adaptive thresholds
        old_recon_threshold = self.thresholds['reconstruction_error']
        old_seq_threshold = self.thresholds['sequence_score']
        self._update_adaptive_thresholds(anomaly_score, sequence_score)
        
        if (abs(self.thresholds['reconstruction_error'] - old_recon_threshold) > 0.001 or
            abs(self.thresholds['sequence_score'] - old_seq_threshold) > 0.001):
            logger.debug(f"📊 AI: Thresholds updated - reconstruction: {old_recon_threshold:.4f} → "
                        f"{self.thresholds['reconstruction_error']:.4f}, "
                        f"sequence: {old_seq_threshold:.4f} → {self.thresholds['sequence_score']:.4f}")
        
        # Determine if anomaly with detailed criteria logging
        is_anomaly = self._is_sequence_anomaly(reconstruction_error, sequence_score, attention_variance)
        
        logger.debug(f"🎲 AI: Anomaly criteria - "
                    f"Recon error ({reconstruction_error:.4f}) > threshold ({self.thresholds['reconstruction_error']:.4f}): "
                    f"{reconstruction_error > self.thresholds['reconstruction_error']}, "
                    f"Seq score ({sequence_score:.4f}) > threshold ({self.thresholds['sequence_score']:.4f}): "
                    f"{sequence_score > self.thresholds['sequence_score']}, "
                    f"Attention variance ({attention_variance:.4f}) < threshold ({self.thresholds['attention_threshold']:.4f}): "
                    f"{attention_variance < self.thresholds['attention_threshold']}")
        
        # Calculate confidence
        confidence = self._calculate_enhanced_confidence(
            reconstruction_error, sequence_score, attention_variance, pattern_scores
        )
        
        logger.debug(f"🎯 AI: Detection confidence: {confidence:.2%}")
        
        # Generate enhanced recommendation
        recommendation, severity = self._generate_enhanced_recommendation(
            reconstruction_error, sequence_score, feature_errors, dominant_pattern, is_anomaly
        )
        
        # Feature contributions dictionary
        feature_contributions = {
            name: float(error) for name, error in zip(feature_names, feature_errors)
        }
        
        # Attention weights dictionary
        attention_dict = {
            f"timestep_{i}": float(weight) for i, weight in enumerate(attention_np)
        }
        
        # Store anomaly score for pattern analysis
        self.anomaly_scores.append(anomaly_score)
        
        # Get seasonal baseline
        seasonal_baseline = self._get_seasonal_baseline(timestamp)
        
        # Update last inference time
        self.last_inference_time = time.time()
        total_inference_time = self.last_inference_time - inference_start_time
        
        # Final logging based on result
        if is_anomaly:
            logger.info(f"🚨 AI ANOMALY DETECTED for {target_host}: "
                       f"score={anomaly_score:.3f}, confidence={confidence:.2f}, "
                       f"severity={severity}, pattern={dominant_pattern}")
            logger.info(f"💡 AI Recommendation: {recommendation}")
            logger.debug(f"🔍 AI Details - Top contributors: {', '.join([f[0] for f in top_features[:3]])}, "
                        f"Inference time: {total_inference_time*1000:.2f}ms")
        else:
            logger.debug(f"✅ AI: Normal behavior detected for {target_host} "
                        f"(score={anomaly_score:.3f}, confidence={confidence:.2f})")
            if anomaly_score > self.thresholds['reconstruction_error'] * 0.8:
                logger.debug(f"⚠️ AI: Score approaching threshold - monitor closely")
        
        # Log performance stats periodically
        if len(self.anomaly_scores) % 100 == 0:
            recent_scores_array = np.array(list(self.anomaly_scores)[-100:])
            logger.info(f"📊 AI Performance Stats (last 100 inferences): "
                       f"Mean score: {np.mean(recent_scores_array):.4f}, "
                       f"Std: {np.std(recent_scores_array):.4f}, "
                       f"Max: {np.max(recent_scores_array):.4f}, "
                       f"Anomalies: {sum(s > self.thresholds['reconstruction_error'] for s in recent_scores_array)}")
        
        return SequenceAnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            confidence=confidence,
            sequence_score=sequence_score,
            attention_weights=attention_dict,
            baseline_values={
                **seasonal_baseline,
                'reconstruction_threshold': self.thresholds['reconstruction_error'],
                'sequence_threshold': self.thresholds['sequence_score'],
                'historical_mean': float(np.mean(recent_scores)) if recent_scores else 0.0,
                'historical_std': float(np.std(recent_scores)) if len(recent_scores) > 1 else 0.0
            },
            thresholds=self.thresholds.copy(),
            feature_contributions=feature_contributions,
            temporal_pattern=dominant_pattern,
            recommendation=recommendation,
            severity=severity
        )   

    def _is_sequence_anomaly(self, reconstruction_error: float, 
                           sequence_score: float, attention_variance: float) -> bool:
        """Determine if sequence represents an anomaly"""
        
        # During warmup period, be less sensitive
        if self.samples_processed < self.warmup_samples:
            threshold_multiplier = self.threshold_multiplier * 2  # Double threshold during warmup
        else:
            threshold_multiplier = self.threshold_multiplier
        
        # Apply multiplier to thresholds for less sensitivity
        adjusted_recon_threshold = self.thresholds['reconstruction_error'] * threshold_multiplier
        adjusted_seq_threshold = self.thresholds['sequence_score'] * threshold_multiplier
        
        # Multiple criteria for anomaly detection
        criteria = [
            reconstruction_error > adjusted_recon_threshold,
            sequence_score > adjusted_seq_threshold,
            attention_variance < self.thresholds['attention_threshold']
        ]
        
        # Log the criteria evaluation
        logger.debug(f"🎯 Anomaly criteria (adjusted): "
                    f"recon {reconstruction_error:.4f} > {adjusted_recon_threshold:.4f}, "
                    f"seq {sequence_score:.4f} > {adjusted_seq_threshold:.4f}, "
                    f"attn_var {attention_variance:.4f} < {self.thresholds['attention_threshold']:.4f}")
        
        # Require at least 2 criteria to be met
        return sum(criteria) >= 2

    def _calculate_enhanced_confidence(self, reconstruction_error: float,
                                     sequence_score: float, attention_variance: float,
                                     pattern_scores: Dict[str, float]) -> float:
        """Calculate confidence in anomaly detection"""
        
        # Use the threshold multiplier in confidence calculation
        threshold_mult = self.threshold_multiplier if self.samples_processed >= self.warmup_samples else self.threshold_multiplier * 2
        
        # Reconstruction confidence (adjusted for multiplier)
        recon_conf = min(reconstruction_error / (self.thresholds['reconstruction_error'] * threshold_mult * 2), 1.0)
        
        # Sequence confidence (adjusted for multiplier)
        seq_conf = min(sequence_score / (self.thresholds['sequence_score'] * threshold_mult * 2), 1.0)       
        # Attention confidence
        attn_conf = 1.0 - min(attention_variance / self.thresholds['attention_threshold'], 1.0)
        
        # Pattern confidence
        pattern_conf = max(pattern_scores.values()) if pattern_scores else 0.5
        
        # Weighted combination
        confidence = min(confidence, 1.0)
        
        # Reduce confidence during warmup
        if self.samples_processed < self.warmup_samples:
            confidence *= 0.7  # Reduce confidence by 30% during warmup
        
        return confidence

    def _generate_enhanced_recommendation(self, reconstruction_error: float,
                                        sequence_score: float, feature_errors: np.ndarray,
                                        pattern: str, is_anomaly: bool) -> Tuple[str, str]:
        """Generate enhanced recommendation with severity"""
        
        if not is_anomaly:
            return "Network metrics are within expected patterns", "info"
        
        # Calculate severity based on how much the score exceeds threshold
        score_ratio = reconstruction_error / self.thresholds['reconstruction_error']
        
        # Use configured severity thresholds
        if score_ratio >= self.severity_thresholds['critical']:
            severity = "critical"
        elif score_ratio >= self.severity_thresholds['high']:
            severity = "high"
        elif score_ratio >= self.severity_thresholds['medium']:
            severity = "medium"
        else:
            severity = "low"
        
            # Identify primary issue
        feature_names = [
            'tcp_handshake_time', 'icmp_ping_time', 'dns_resolve_time',
            'packet_loss', 'jitter', 'bandwidth_test', 'connection_errors',
            'time_of_day', 'day_of_week', 'sine_time'
        ]
        
        max_error_idx = np.argmax(feature_errors[:7])  # Only consider network metrics
        primary_metric = feature_names[max_error_idx]
        error_magnitude = feature_errors[max_error_idx]
        
        # Determine severity
        if error_magnitude > 0.5:
            severity = "critical"
        elif error_magnitude > 0.2:
            severity = "high"
        elif error_magnitude > 0.1:
            severity = "medium"
        else:
            severity = "low"
        
        # Generate specific recommendation
        recommendations = {
            'tcp_handshake_time': f"High TCP connection delays detected ({pattern} pattern) - investigate server performance and network congestion",
            'icmp_ping_time': f"Elevated latency observed ({pattern} pattern) - check network routing and infrastructure",
            'dns_resolve_time': f"DNS resolution issues detected ({pattern} pattern) - verify DNS server performance",
            'packet_loss': f"Packet loss detected ({pattern} pattern) - investigate network path and hardware",
            'jitter': f"Network instability detected ({pattern} pattern) - check for congestion or faulty equipment",
            'bandwidth_test': f"Bandwidth degradation detected ({pattern} pattern) - investigate capacity constraints",
            'connection_errors': f"Connection failures detected ({pattern} pattern) - verify service availability"
        }
        
        recommendation = recommendations.get(
            primary_metric,
            f"Network anomaly detected in {primary_metric} with {pattern} pattern - investigate system behavior"
        )
        
        return recommendation, severity
    
    def _update_adaptive_thresholds(self, anomaly_score: float, sequence_score: float):
        """Update adaptive thresholds based on recent performance"""
        
        if len(self.anomaly_scores) >= 100:
            scores = list(self.anomaly_scores)
            
            # Update reconstruction threshold (95th percentile)
            new_recon_threshold = np.percentile(scores, 95)
            self.thresholds['reconstruction_error'] = (
                self.thresholds['reconstruction_error'] * 0.9 + new_recon_threshold * 0.1
            )
            
            # Update sequence threshold
            self.thresholds['sequence_score'] = max(
                np.percentile(scores, 90) * 1.5,
                self.thresholds['sequence_score'] * 0.95
            )
    
    def _get_seasonal_baseline(self, timestamp: float) -> Dict[str, float]:
        """Get seasonal baseline values"""
        
        # Simple implementation - can be enhanced with actual seasonal data
        hour_of_day = (timestamp % 86400) / 3600
        day_of_week = (timestamp % 604800) / 86400
        
        return {
            'hourly_baseline': float(hour_of_day / 24),
            'daily_baseline': float(day_of_week / 7),
            'expected_pattern': 'normal'
        }
    
    async def train_initial_model(self):
        """Train initial LSTM model on collected sequences"""
        
        if len(self.training_sequences) < 50:
            logger.warning("Insufficient training sequences")
            return
        
        logger.info(f"Training initial LSTM model on {len(self.training_sequences)} sequences")
        
        # Prepare training data
        sequences = np.array(list(self.training_sequences))
        
        # Fit scaler on all data
        all_data = sequences.reshape(-1, self.input_size)
        self.scaler.fit(all_data)
        
        # Scale sequences
        sequences_scaled = self.scaler.transform(all_data)
        sequences_scaled = sequences_scaled.reshape(-1, self.sequence_length, self.input_size)
        
        # Convert to tensor
        sequences_tensor = torch.FloatTensor(sequences_scaled).to(self.device)
        
        # Training loop
        self.model.train()
        criterion = nn.MSELoss()
        
        epochs = self.config.get('initial_epochs', 100)
        
        for epoch in range(epochs):
            self.optimizer.zero_grad()
            
            reconstructed, _ = self.model(sequences_tensor)
            loss = criterion(reconstructed, sequences_tensor)
            
            loss.backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            
            self.optimizer.step()
            
            if epoch % 20 == 0:
                logger.debug(f"Epoch {epoch}, Loss: {loss.item():.6f}")
        
        self.is_trained = True
        logger.info("Initial LSTM model training completed")
    
    async def train_online(self, recent_data: List[Dict[str, Any]]):
        """Online training with recent sequence data"""
        
        # Validate input data
        if not recent_data:
            logger.warning("No data provided for online training")
            return
        
        if len(recent_data) < self.sequence_length:
            logger.warning(f"Insufficient data for online training: {len(recent_data)} samples "
                          f"(need at least {self.sequence_length})")
            return
        
        logger.info(f"📚 Starting online training with {len(recent_data)} data points")
        training_start_time = time.time()
        
        try:
            # Extract features from recent data
            features_list = []
            skipped_samples = 0
            
            for i, data_point in enumerate(recent_data):
                try:
                    features = self._extract_enhanced_features(data_point)
                    features_list.append(features)
                except Exception as e:
                    logger.debug(f"Skipped sample {i} due to feature extraction error: {e}")
                    skipped_samples += 1
                    continue
            
            if skipped_samples > 0:
                logger.info(f"⚠️ Skipped {skipped_samples} samples during feature extraction")
            
            # Create overlapping sequences for training
            sequences = []
            for i in range(len(features_list) - self.sequence_length + 1):
                sequence = np.array(features_list[i:i + self.sequence_length])
                sequences.append(sequence)
            
            if len(sequences) < 5:
                logger.warning(f"Too few sequences for training: {len(sequences)} (need at least 5)")
                return
            
            logger.info(f"📊 Created {len(sequences)} training sequences from {len(features_list)} features")
            
            # Convert sequences to numpy array
            sequences = np.array(sequences)
            
            # If scaler hasn't been fitted yet, fit it now
            if not hasattr(self.scaler, 'scale_'):
                logger.info("🔧 Fitting scaler on training data...")
                all_features = sequences.reshape(-1, self.input_size)
                self.scaler.fit(all_features)
            
            # Scale sequences
            sequences_scaled = self.scaler.transform(sequences.reshape(-1, self.input_size))
            sequences_scaled = sequences_scaled.reshape(-1, self.sequence_length, self.input_size)
            
            # Split data for validation (80/20 split)
            n_train = int(0.8 * len(sequences_scaled))
            train_sequences = sequences_scaled[:n_train]
            val_sequences = sequences_scaled[n_train:]
            
            # Convert to PyTorch tensors
            train_tensor = torch.FloatTensor(train_sequences).to(self.device)
            val_tensor = torch.FloatTensor(val_sequences).to(self.device) if len(val_sequences) > 0 else None
            
            # Training configuration for online learning
            online_epochs = 10  # Fewer epochs for online learning
            batch_size = min(32, len(train_sequences))
            
            # Store original learning rate
            original_lr = self.optimizer.param_groups[0]['lr']
            
            # Reduce learning rate for online training to prevent catastrophic forgetting
            online_lr = original_lr * 0.1
            self.optimizer.param_groups[0]['lr'] = online_lr
            
            logger.info(f"🎯 Online training config: epochs={online_epochs}, batch_size={batch_size}, "
                       f"lr={online_lr:.6f}, train_samples={len(train_sequences)}, "
                       f"val_samples={len(val_sequences) if val_sequences is not None else 0}")
            
            # Track training metrics
            train_losses = []
            val_losses = []
            best_val_loss = float('inf')
            patience_counter = 0
            early_stop_patience = 3
            
            # Training loop
            self.model.train()
            criterion = nn.MSELoss()
            
            for epoch in range(online_epochs):
                epoch_losses = []
                
                # Shuffle indices for each epoch
                indices = torch.randperm(len(train_tensor))
                
                # Mini-batch training
                for batch_start in range(0, len(train_tensor), batch_size):
                    batch_end = min(batch_start + batch_size, len(train_tensor))
                    batch_indices = indices[batch_start:batch_end]
                    batch_data = train_tensor[batch_indices]
                    
                    # Forward pass
                    self.optimizer.zero_grad()
                    reconstructed, _ = self.model(batch_data)
                    loss = criterion(reconstructed, batch_data)
                    
                    # Backward pass
                    loss.backward()
                    
                    # Gradient clipping to prevent explosion
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=0.5)
                    
                    # Optimizer step
                    self.optimizer.step()
                    
                    epoch_losses.append(loss.item())
                
                # Calculate epoch training loss
                avg_train_loss = np.mean(epoch_losses)
                train_losses.append(avg_train_loss)
                
                # Validation
                if val_tensor is not None and len(val_tensor) > 0:
                    self.model.eval()
                    with torch.no_grad():
                        val_reconstructed, _ = self.model(val_tensor)
                        val_loss = criterion(val_reconstructed, val_tensor).item()
                        val_losses.append(val_loss)
                    
                    # Early stopping check
                    if val_loss < best_val_loss:
                        best_val_loss = val_loss
                        patience_counter = 0
                        # Save best model state
                        best_model_state = self.model.state_dict().copy()
                    else:
                        patience_counter += 1
                    
                    self.model.train()
                    
                    # Log progress
                    logger.debug(f"📈 Epoch {epoch + 1}/{online_epochs} - "
                               f"Train Loss: {avg_train_loss:.6f}, Val Loss: {val_loss:.6f}")
                    
                    # Early stopping
                    if patience_counter >= early_stop_patience:
                        logger.info(f"⏹️ Early stopping triggered at epoch {epoch + 1}")
                        # Restore best model
                        self.model.load_state_dict(best_model_state)
                        break
                else:
                    logger.debug(f"📈 Epoch {epoch + 1}/{online_epochs} - Train Loss: {avg_train_loss:.6f}")
            
            # Restore original learning rate
            self.optimizer.param_groups[0]['lr'] = original_lr
            
            # Calculate improvement metrics
            initial_loss = train_losses[0] if train_losses else 0
            final_loss = train_losses[-1] if train_losses else 0
            improvement_percent = ((initial_loss - final_loss) / initial_loss * 100) if initial_loss > 0 else 0
            
            # Update model state
            self.is_trained = True
            self.model_creation_time = getattr(self, 'model_creation_time', time.time())
            
            # Update anomaly score history with recent training performance
            if val_losses:
                # Use validation loss as a proxy for expected reconstruction error
                expected_anomaly_score = np.mean(val_losses[-3:]) if len(val_losses) >= 3 else val_losses[-1]
                # Update thresholds based on training results
                self.thresholds['reconstruction_error'] = expected_anomaly_score * 3.0  # 2x validation loss
                logger.info(f"📊 Updated reconstruction threshold to {self.thresholds['reconstruction_error']:.6f}")
            
            # Training summary
            training_duration = time.time() - training_start_time
            logger.info(f"✅ Online training completed in {training_duration:.2f}s")
            logger.info(f"📊 Training summary: {len(sequences)} sequences, {epoch + 1} epochs")
            logger.info(f"📈 Loss improvement: {improvement_percent:.1f}% "
                       f"(initial: {initial_loss:.6f} → final: {final_loss:.6f})")
            
            if val_losses:
                # Use 99th percentile of validation losses as base threshold
                val_loss_array = np.array(val_losses)
                base_threshold = np.percentile(val_loss_array, 99)
                
                # Apply multiplier for initial threshold
                self.thresholds['reconstruction_error'] = base_threshold * self.threshold_multiplier
                self.thresholds['sequence_score'] = base_threshold * self.threshold_multiplier * 0.5
                
                logger.info(f"📊 Set thresholds - reconstruction: {self.thresholds['reconstruction_error']:.6f}, "
                           f"sequence: {self.thresholds['sequence_score']:.6f}")           
            # Return training metrics for external tracking
            return {
                'success': True,
                'sequences_trained': len(sequences),
                'epochs_completed': epoch + 1,
                'initial_loss': initial_loss,
                'final_loss': final_loss,
                'best_val_loss': best_val_loss if val_losses else None,
                'improvement_percent': improvement_percent,
                'training_duration': training_duration
            }
            
        except Exception as e:
            logger.error(f"❌ Error during online training: {e}", exc_info=True)
            
            # Restore original learning rate if error occurred
            if 'original_lr' in locals():
                self.optimizer.param_groups[0]['lr'] = original_lr
            
            return {
                'success': False,
                'error': str(e),
                'training_duration': time.time() - training_start_time
            }   

    def save_models(self):
        """Save enhanced models"""
        
        if not self.is_trained:
            logger.warning("Attempting to save untrained model")
        
        try:
            # Save PyTorch model with all necessary state
            model_path = self.model_dir / 'lstm_autoencoder.pt'
            
            # Include training sequences count for debugging
            checkpoint = {
                'model_state_dict': self.model.state_dict(),
                'optimizer_state_dict': self.optimizer.state_dict(),
                'scaler': self.scaler,
                'thresholds': self.thresholds,
                'config': {
                    'sequence_length': self.sequence_length,
                    'input_size': self.input_size,
                    'hidden_size': self.hidden_size,
                    'num_layers': self.num_layers
                },
                'is_trained': self.is_trained,
                'training_sequences_count': len(self.training_sequences),
                'model_creation_time': getattr(self, 'model_creation_time', time.time())
            }
            
            torch.save(checkpoint, model_path)
            logger.info(f"Enhanced LSTM models saved successfully (trained: {self.is_trained}, "
                       f"sequences: {len(self.training_sequences)})")
            
        except Exception as e:
            logger.error(f"Error saving enhanced models: {e}")   

    def load_models(self):
        """Load enhanced models"""
        
        try:
            model_path = self.model_dir / 'lstm_autoencoder.pt'
            if model_path.exists():
                checkpoint = torch.load(model_path, map_location=self.device)
                
                # Load configuration
                config = checkpoint['config']
                self.sequence_length = config['sequence_length']
                self.input_size = config['input_size']
                self.hidden_size = config['hidden_size']
                self.num_layers = config['num_layers']
                
                # Recreate model with loaded config
                self.model = LSTMAutoEncoder(
                    input_size=self.input_size,
                    hidden_size=self.hidden_size,
                    num_layers=self.num_layers,
                    sequence_length=self.sequence_length
                )
                self.model.to(self.device)
                self.model.load_state_dict(checkpoint['model_state_dict'])
                
                # Load optimizer
                self.optimizer = optim.AdamW(self.model.parameters(), lr=0.001, weight_decay=1e-5)
                self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
                
                # Load other components
                self.scaler = checkpoint['scaler']
                self.thresholds = checkpoint['thresholds']
                self.is_trained = checkpoint['is_trained']
                
                logger.info("Enhanced LSTM models loaded successfully")
            
        except Exception as e:
            logger.warning(f"Could not load enhanced models: {e}")
            raise FileNotFoundError("No trained enhanced models found")
    
    def quantize_for_edge(self):
        """Quantize model for edge deployment"""
        
        if not self.is_trained:
            logger.warning("Cannot quantize untrained model")
            return
        
        try:
            # Dynamic quantization for immediate deployment
            self.model.eval()
            quantized_model = torch.quantization.quantize_dynamic(
                self.model,
                {nn.Linear, nn.LSTM},
                dtype=torch.qint8
            )
            
            # Save quantized model
            quantized_path = self.model_dir / 'lstm_autoencoder_quantized.pt'
            torch.save(quantized_model, quantized_path)
            
            # Test quantized model performance
            original_size = model_path.stat().st_size if (model_path := self.model_dir / 'lstm_autoencoder.pt').exists() else 0
            quantized_size = quantized_path.stat().st_size
            
            compression_ratio = original_size / quantized_size if quantized_size > 0 else 1
            
            logger.info(f"Model quantized successfully. Compression ratio: {compression_ratio:.2f}x")
            
            return quantized_model
            
        except Exception as e:
            logger.error(f"Error quantizing model: {e}")
            return None

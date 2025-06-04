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
        self.input_size = config.get('input_size', 10)
        self.hidden_size = config.get('hidden_size', 64)
        self.num_layers = config.get('num_layers', 2)
        
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
        
        # Base features
        base_features = [
            metrics_dict.get('tcp_handshake_time', 0),
            metrics_dict.get('icmp_ping_time', 0),
            metrics_dict.get('dns_resolve_time', 0),
            metrics_dict.get('packet_loss', 0),
            metrics_dict.get('jitter', 0),
            metrics_dict.get('bandwidth_test', 0),
            metrics_dict.get('connection_errors', 0)
        ]
        
        # Derived features
        timestamp = metrics_dict.get('timestamp', time.time())
        
        # Time-based features
        time_features = [
            (timestamp % 86400) / 86400,  # Time of day (0-1)
            (timestamp % 604800) / 604800,  # Day of week (0-1)
            math.sin(2 * math.pi * (timestamp % 86400) / 86400)  # Sine of time
        ]
        
        # Handle invalid values
        features = base_features + time_features
        features = [f if f >= 0 and not math.isnan(f) else 0 for f in features]
        
        return np.array(features, dtype=np.float32)
    
    def _update_sequence_buffer(self, features: np.ndarray):
        """Update sequence buffer for temporal analysis"""
        self.sequence_buffer.append(features)
        
        # Create training sequence when buffer is full
        if len(self.sequence_buffer) == self.sequence_length:
            sequence = np.array(list(self.sequence_buffer))
            self.training_sequences.append(sequence)
    
    async def detect_anomaly(self, metrics) -> SequenceAnomalyResult:
        """Enhanced anomaly detection with sequence analysis"""
        
        features = self._extract_enhanced_features(metrics)
        timestamp = getattr(metrics, 'timestamp', time.time())
        
        # Update sequence buffer
        self._update_sequence_buffer(features)
        
        if not self.is_trained or len(self.sequence_buffer) < self.sequence_length:
            # Store for training and return normal result
            if len(self.training_sequences) >= 50:
                await self.train_initial_model()
            
            return SequenceAnomalyResult(
                is_anomaly=False,
                anomaly_score=0.0,
                confidence=0.0,
                sequence_score=0.0,
                attention_weights={},
                baseline_values={},
                thresholds=self.thresholds.copy(),
                feature_contributions={},
                temporal_pattern="learning",
                recommendation="Building baseline - collecting training data",
                severity="info"
            )
        
        # Prepare sequence for inference
        sequence = np.array(list(self.sequence_buffer))
        sequence_scaled = self.scaler.transform(sequence.reshape(-1, self.input_size))
        sequence_scaled = sequence_scaled.reshape(1, self.sequence_length, self.input_size)
        sequence_tensor = torch.FloatTensor(sequence_scaled).to(self.device)
        
        # Model inference
        self.model.eval()
        with torch.no_grad():
            reconstructed, attention_weights = self.model(sequence_tensor)
            
            # Calculate reconstruction error
            mse = nn.MSELoss(reduction='none')
            errors = mse(reconstructed, sequence_tensor)
            
            # Overall reconstruction error
            reconstruction_error = torch.mean(errors).item()
            
            # Sequence-level score
            sequence_score = torch.mean(torch.std(errors, dim=1)).item()
            
            # Feature-wise contributions
            feature_errors = torch.mean(errors, dim=(0, 1)).cpu().numpy()
            
            # Attention analysis
            attention_np = attention_weights.cpu().numpy()[0]  # First batch
            attention_variance = np.var(attention_np)
        
        # Pattern detection
        recent_scores = list(self.anomaly_scores)[-50:] if self.anomaly_scores else [0]
        pattern_scores = self.pattern_detector.detect_patterns(np.array(recent_scores))
        
        # Determine temporal pattern
        dominant_pattern = max(pattern_scores.keys(), 
                             key=lambda k: pattern_scores[k]) if pattern_scores else "unknown"
        
        # Calculate combined anomaly score
        anomaly_score = (reconstruction_error * 0.6 + 
                        sequence_score * 0.3 + 
                        attention_variance * 0.1)
        
        # Update adaptive thresholds
        self._update_adaptive_thresholds(anomaly_score, sequence_score)
        
        # Determine if anomaly
        is_anomaly = self._is_sequence_anomaly(reconstruction_error, sequence_score, attention_variance)
        
        # Calculate confidence
        confidence = self._calculate_enhanced_confidence(
            reconstruction_error, sequence_score, attention_variance, pattern_scores
        )
        
        # Generate enhanced recommendation
        recommendation, severity = self._generate_enhanced_recommendation(
            reconstruction_error, sequence_score, feature_errors, dominant_pattern, is_anomaly
        )
        
        # Feature contributions
        feature_names = [
            'tcp_handshake_time', 'icmp_ping_time', 'dns_resolve_time',
            'packet_loss', 'jitter', 'bandwidth_test', 'connection_errors',
            'time_of_day', 'day_of_week', 'sine_time'
        ]
        
        feature_contributions = {
            name: float(error) for name, error in zip(feature_names, feature_errors)
        }
        
        attention_dict = {
            f"timestep_{i}": float(weight) for i, weight in enumerate(attention_np)
        }
        
        # Store anomaly score for pattern analysis
        self.anomaly_scores.append(anomaly_score)
        
        return SequenceAnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            confidence=confidence,
            sequence_score=sequence_score,
            attention_weights=attention_dict,
            baseline_values=self._get_seasonal_baseline(timestamp),
            thresholds=self.thresholds.copy(),
            feature_contributions=feature_contributions,
            temporal_pattern=dominant_pattern,
            recommendation=recommendation,
            severity=severity
        )
    
    def _is_sequence_anomaly(self, reconstruction_error: float, 
                           sequence_score: float, attention_variance: float) -> bool:
        """Determine if sequence represents an anomaly"""
        
        # Multiple criteria for anomaly detection
        criteria = [
            reconstruction_error > self.thresholds['reconstruction_error'],
            sequence_score > self.thresholds['sequence_score'],
            attention_variance < self.thresholds['attention_threshold']  # Low variance = focused attention
        ]
        
        # Anomaly if 2+ criteria are met
        return sum(criteria) >= 2
    
    def _calculate_enhanced_confidence(self, reconstruction_error: float,
                                     sequence_score: float, attention_variance: float,
                                     pattern_scores: Dict[str, float]) -> float:
        """Calculate confidence in anomaly detection"""
        
        # Reconstruction confidence
        recon_conf = min(reconstruction_error / (self.thresholds['reconstruction_error'] * 2), 1.0)
        
        # Sequence confidence
        seq_conf = min(sequence_score / (self.thresholds['sequence_score'] * 2), 1.0)
        
        # Attention confidence
        attn_conf = 1.0 - min(attention_variance / self.thresholds['attention_threshold'], 1.0)
        
        # Pattern confidence
        pattern_conf = max(pattern_scores.values()) if pattern_scores else 0.5
        
        # Weighted combination
        confidence = (recon_conf * 0.4 + seq_conf * 0.3 + 
                     attn_conf * 0.2 + pattern_conf * 0.1)
        
        return min(confidence, 1.0)
    
    def _generate_enhanced_recommendation(self, reconstruction_error: float,
                                        sequence_score: float, feature_errors: np.ndarray,
                                        pattern: str, is_anomaly: bool) -> Tuple[str, str]:
        """Generate enhanced recommendation with severity"""
        
        if not is_anomaly:
            return "Network metrics are within expected patterns", "info"
        
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
        
        if not self.is_trained or len(recent_data) < 20:
            return
        
        logger.info(f"Online training with {len(recent_data)} data points")
        
        # Create sequences from recent data
        features_list = []
        for data_point in recent_data:
            features = self._extract_enhanced_features(data_point)
            features_list.append(features)
        
        # Create overlapping sequences
        sequences = []
        for i in range(len(features_list) - self.sequence_length + 1):
            sequence = np.array(features_list[i:i + self.sequence_length])
            sequences.append(sequence)
        
        if len(sequences) < 5:
            return
        
        sequences = np.array(sequences)
        
        # Scale and convert to tensor
        sequences_scaled = self.scaler.transform(sequences.reshape(-1, self.input_size))
        sequences_scaled = sequences_scaled.reshape(-1, self.sequence_length, self.input_size)
        sequences_tensor = torch.FloatTensor(sequences_scaled).to(self.device)
        
        # Online training with lower learning rate
        old_lr = self.optimizer.param_groups[0]['lr']
        self.optimizer.param_groups[0]['lr'] = old_lr * 0.1
        
        self.model.train()
        criterion = nn.MSELoss()
        
        for _ in range(10):  # Few epochs for online learning
            self.optimizer.zero_grad()
            
            reconstructed, _ = self.model(sequences_tensor)
            loss = criterion(reconstructed, sequences_tensor)
            
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=0.5)
            self.optimizer.step()
        
        # Restore learning rate
        self.optimizer.param_groups[0]['lr'] = old_lr
        
        logger.info("Online LSTM training completed")
    
    def save_models(self):
        """Save enhanced models"""
        
        if not self.is_trained:
            return
        
        try:
            # Save PyTorch model
            model_path = self.model_dir / 'lstm_autoencoder.pt'
            torch.save({
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
                'is_trained': self.is_trained
            }, model_path)
            
            logger.info("Enhanced LSTM models saved successfully")
            
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

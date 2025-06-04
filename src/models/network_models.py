#!/usr/bin/env python3
"""
AI Model Definitions
===================

PyTorch model definitions for network intelligence monitoring.
Includes LSTM autoencoders, attention mechanisms, and optimization utilities.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math
import logging
from typing import Tuple, Optional, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)

class MultiHeadAttention(nn.Module):
    """Multi-head attention mechanism for sequence modeling"""
    
    def __init__(self, d_model: int, num_heads: int = 8, dropout: float = 0.1):
        super().__init__()
        assert d_model % num_heads == 0
        
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads
        
        self.w_q = nn.Linear(d_model, d_model)
        self.w_k = nn.Linear(d_model, d_model)
        self.w_v = nn.Linear(d_model, d_model)
        self.w_o = nn.Linear(d_model, d_model)
        
        self.dropout = nn.Dropout(dropout)
        self.scale = math.sqrt(self.d_k)
        
    def forward(self, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor,
                mask: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, torch.Tensor]:
        batch_size = query.size(0)
        
        # Linear transformations and reshape
        Q = self.w_q(query).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        K = self.w_k(key).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        V = self.w_v(value).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        
        # Scaled dot-product attention
        attention, attention_weights = self._scaled_dot_product_attention(Q, K, V, mask)
        
        # Concatenate heads
        attention = attention.transpose(1, 2).contiguous().view(
            batch_size, -1, self.d_model
        )
        
        # Final linear transformation
        output = self.w_o(attention)
        
        return output, attention_weights
    
    def _scaled_dot_product_attention(self, Q: torch.Tensor, K: torch.Tensor, 
                                    V: torch.Tensor, mask: Optional[torch.Tensor] = None):
        # Compute attention scores
        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale
        
        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)
        
        attention_weights = F.softmax(scores, dim=-1)
        attention_weights = self.dropout(attention_weights)
        
        attention = torch.matmul(attention_weights, V)
        
        return attention, attention_weights

class PositionalEncoding(nn.Module):
    """Positional encoding for transformer-like models"""
    
    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(dropout)
        
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len).unsqueeze(1).float()
        
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * 
                           -(math.log(10000.0) / d_model))
        
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        
        self.register_buffer('pe', pe.unsqueeze(0))
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.pe[:, :x.size(1)]
        return self.dropout(x)

class FeatureEmbedding(nn.Module):
    """Feature embedding layer for network metrics"""
    
    def __init__(self, input_size: int, embedding_size: int, dropout: float = 0.1):
        super().__init__()
        self.input_size = input_size
        self.embedding_size = embedding_size
        
        # Metric-specific embeddings
        self.latency_embedding = nn.Linear(3, embedding_size // 4)  # tcp, icmp, dns
        self.quality_embedding = nn.Linear(3, embedding_size // 4)  # loss, jitter, mos
        self.throughput_embedding = nn.Linear(2, embedding_size // 4)  # download, upload
        self.error_embedding = nn.Linear(3, embedding_size // 4)  # connection, dns, timeout
        
        # Temporal features
        self.temporal_embedding = nn.Linear(3, embedding_size // 4)  # time features
        
        self.output_projection = nn.Linear(embedding_size + embedding_size // 4, embedding_size)
        self.dropout = nn.Dropout(dropout)
        self.layer_norm = nn.LayerNorm(embedding_size)
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch_size, seq_len, _ = x.shape
        
        # Split features into categories
        latency_features = x[:, :, :3]  # tcp_handshake, icmp_ping, dns_resolve
        quality_features = x[:, :, 3:6]  # packet_loss, jitter, mos_score
        throughput_features = x[:, :, 6:8]  # bandwidth_down, bandwidth_up
        error_features = x[:, :, 8:11]  # connection_errors, dns_errors, timeout_errors
        temporal_features = x[:, :, -3:]  # time-based features
        
        # Create embeddings
        latency_emb = self.latency_embedding(latency_features)
        quality_emb = self.quality_embedding(quality_features)
        throughput_emb = self.throughput_embedding(throughput_features)
        error_emb = self.error_embedding(error_features)
        temporal_emb = self.temporal_embedding(temporal_features)
        
        # Concatenate embeddings
        combined = torch.cat([
            latency_emb, quality_emb, throughput_emb, error_emb, temporal_emb
        ], dim=-1)
        
        # Project to final embedding size
        embedded = self.output_projection(combined)
        embedded = self.dropout(embedded)
        embedded = self.layer_norm(embedded)
        
        return embedded

class EnhancedLSTMEncoder(nn.Module):
    """Enhanced LSTM encoder with attention and residual connections"""
    
    def __init__(self, input_size: int, hidden_size: int, num_layers: int = 2, 
                 dropout: float = 0.1, bidirectional: bool = True):
        super().__init__()
        
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.bidirectional = bidirectional
        
        # Feature embedding
        self.feature_embedding = FeatureEmbedding(input_size, hidden_size, dropout)
        
        # LSTM layers
        self.lstm = nn.LSTM(
            hidden_size, hidden_size, num_layers,
            batch_first=True, dropout=dropout if num_layers > 1 else 0,
            bidirectional=bidirectional
        )
        
        # Attention mechanism
        attention_size = hidden_size * 2 if bidirectional else hidden_size
        self.attention = MultiHeadAttention(attention_size, num_heads=8, dropout=dropout)
        
        # Layer normalization and dropout
        self.layer_norm = nn.LayerNorm(attention_size)
        self.dropout = nn.Dropout(dropout)
        
        # Output projection
        self.output_projection = nn.Linear(attention_size, hidden_size)
        
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        batch_size, seq_len, _ = x.shape
        
        # Feature embedding
        embedded = self.feature_embedding(x)
        
        # LSTM encoding
        lstm_out, (hidden, cell) = self.lstm(embedded)
        
        # Apply attention
        attended, attention_weights = self.attention(lstm_out, lstm_out, lstm_out)
        
        # Residual connection and layer norm
        lstm_out = self.layer_norm(lstm_out + attended)
        lstm_out = self.dropout(lstm_out)
        
        # Project to desired output size
        encoded = self.output_projection(lstm_out)
        
        return encoded, hidden, attention_weights

class AdaptiveDecoder(nn.Module):
    """Adaptive decoder with dynamic attention"""
    
    def __init__(self, hidden_size: int, output_size: int, num_layers: int = 2,
                 dropout: float = 0.1):
        super().__init__()
        
        self.hidden_size = hidden_size
        self.output_size = output_size
        
        # Decoder LSTM
        self.lstm = nn.LSTM(
            hidden_size, hidden_size, num_layers,
            batch_first=True, dropout=dropout if num_layers > 1 else 0
        )
        
        # Attention for decoder
        self.attention = MultiHeadAttention(hidden_size, num_heads=4, dropout=dropout)
        
        # Output layers
        self.output_layers = nn.ModuleList([
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, output_size)
        ])
        
        self.layer_norm = nn.LayerNorm(hidden_size)
        
    def forward(self, encoded: torch.Tensor, encoder_hidden: torch.Tensor) -> torch.Tensor:
        batch_size, seq_len, _ = encoded.shape
        
        # Initialize decoder with encoder context
        decoder_input = encoded
        
        # Decode with attention
        decoded, _ = self.lstm(decoder_input, encoder_hidden)
        
        # Apply self-attention
        attended, _ = self.attention(decoded, decoded, decoded)
        decoded = self.layer_norm(decoded + attended)
        
        # Generate output
        output = decoded
        for layer in self.output_layers:
            output = layer(output)
        
        return output

class NetworkAnomalyAutoEncoder(nn.Module):
    """Advanced autoencoder for network anomaly detection"""
    
    def __init__(self, input_size: int = 14, hidden_size: int = 128, 
                 num_layers: int = 2, sequence_length: int = 20,
                 dropout: float = 0.1, enable_attention: bool = True):
        super().__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.sequence_length = sequence_length
        self.enable_attention = enable_attention
        
        # Encoder
        self.encoder = EnhancedLSTMEncoder(
            input_size, hidden_size, num_layers, dropout, bidirectional=True
        )
        
        # Bottleneck
        encoder_output_size = hidden_size
        self.bottleneck = nn.Sequential(
            nn.Linear(encoder_output_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, hidden_size // 4),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 4, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, encoder_output_size)
        )
        
        # Decoder
        self.decoder = AdaptiveDecoder(hidden_size, input_size, num_layers, dropout)
        
        # Initialize weights
        self.apply(self._init_weights)
        
    def _init_weights(self, module):
        """Initialize model weights"""
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
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        batch_size, seq_len, _ = x.shape
        
        # Encode
        encoded, encoder_hidden, attention_weights = self.encoder(x)
        
        # Bottleneck - compress and decompress
        compressed = self.bottleneck(encoded)
        
        # Decode
        reconstructed = self.decoder(compressed, encoder_hidden)
        
        # Calculate reconstruction error per feature
        reconstruction_errors = torch.mean((x - reconstructed) ** 2, dim=1)  # [batch, features]
        
        outputs = {
            'reconstructed': reconstructed,
            'encoded': encoded,
            'compressed': compressed,
            'reconstruction_errors': reconstruction_errors,
            'attention_weights': attention_weights
        }
        
        return reconstructed, outputs
    
    def get_anomaly_score(self, x: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """Calculate anomaly scores"""
        
        with torch.no_grad():
            reconstructed, outputs = self.forward(x)
            
            # Overall reconstruction error
            mse = F.mse_loss(reconstructed, x, reduction='none')
            reconstruction_error = torch.mean(mse, dim=(1, 2))  # [batch]
            
            # Feature-wise errors
            feature_errors = torch.mean(mse, dim=1)  # [batch, features]
            
            # Sequence-wise errors
            sequence_errors = torch.mean(mse, dim=2)  # [batch, sequence]
            
            # Attention-based anomaly detection
            attention_variance = torch.var(outputs['attention_weights'], dim=-1)
            attention_score = torch.mean(attention_variance, dim=(1, 2))
            
            # Combined anomaly score
            anomaly_score = (
                reconstruction_error * 0.6 + 
                attention_score * 0.4
            )
            
            scores = {
                'anomaly_score': anomaly_score,
                'reconstruction_error': reconstruction_error,
                'feature_errors': feature_errors,
                'sequence_errors': sequence_errors,
                'attention_score': attention_score,
                'attention_weights': outputs['attention_weights']
            }
            
            return anomaly_score, scores

class LightweightNetworkAutoEncoder(nn.Module):
    """Lightweight autoencoder for edge devices"""
    
    def __init__(self, input_size: int = 10, hidden_size: int = 32, 
                 sequence_length: int = 20, dropout: float = 0.1):
        super().__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.sequence_length = sequence_length
        
        # Simple encoder
        self.encoder = nn.LSTM(
            input_size, hidden_size, 1,
            batch_first=True, dropout=0
        )
        
        # Bottleneck
        self.bottleneck = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, hidden_size)
        )
        
        # Simple decoder
        self.decoder = nn.LSTM(
            hidden_size, hidden_size, 1,
            batch_first=True, dropout=0
        )
        
        self.output_projection = nn.Linear(hidden_size, input_size)
        
        # Initialize weights
        self.apply(self._init_weights)
    
    def _init_weights(self, module):
        """Initialize model weights"""
        if isinstance(module, nn.Linear):
            nn.init.xavier_uniform_(module.weight)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch_size, seq_len, _ = x.shape
        
        # Encode
        encoded, (hidden, cell) = self.encoder(x)
        
        # Apply bottleneck to the last hidden state
        compressed = self.bottleneck(hidden[-1])  # Use last hidden state
        
        # Prepare decoder input
        decoder_input = compressed.unsqueeze(1).repeat(1, seq_len, 1)
        
        # Decode
        decoded, _ = self.decoder(decoder_input, (hidden, cell))
        
        # Project to output
        reconstructed = self.output_projection(decoded)
        
        return reconstructed

class EnsembleAnomalyDetector(nn.Module):
    """Ensemble of multiple anomaly detection models"""
    
    def __init__(self, input_size: int, hidden_size: int, num_models: int = 3):
        super().__init__()
        
        self.num_models = num_models
        
        # Create ensemble of models
        self.models = nn.ModuleList([
            NetworkAnomalyAutoEncoder(
                input_size=input_size,
                hidden_size=hidden_size + i * 16,  # Vary architecture
                num_layers=2 + i % 2,  # Vary depth
                dropout=0.1 + i * 0.05  # Vary regularization
            )
            for i in range(num_models)
        ])
        
        # Ensemble weights
        self.ensemble_weights = nn.Parameter(torch.ones(num_models) / num_models)
        
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        batch_size = x.size(0)
        
        # Get predictions from all models
        reconstructions = []
        all_outputs = []
        
        for model in self.models:
            recon, outputs = model(x)
            reconstructions.append(recon)
            all_outputs.append(outputs)
        
        # Weighted ensemble
        weights = F.softmax(self.ensemble_weights, dim=0)
        ensemble_reconstruction = sum(
            w * recon for w, recon in zip(weights, reconstructions)
        )
        
        # Combine outputs
        ensemble_outputs = {
            'reconstructed': ensemble_reconstruction,
            'individual_reconstructions': reconstructions,
            'ensemble_weights': weights.detach()
        }
        
        return ensemble_reconstruction, ensemble_outputs
    
    def get_ensemble_anomaly_score(self, x: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """Get ensemble anomaly scores"""
        
        with torch.no_grad():
            individual_scores = []
            
            for model in self.models:
                score, _ = model.get_anomaly_score(x)
                individual_scores.append(score)
            
            # Combine scores
            weights = F.softmax(self.ensemble_weights, dim=0)
            ensemble_score = sum(
                w * score for w, score in zip(weights, individual_scores)
            )
            
            # Calculate uncertainty (variance across models)
            score_tensor = torch.stack(individual_scores, dim=1)
            uncertainty = torch.var(score_tensor, dim=1)
            
            scores = {
                'ensemble_score': ensemble_score,
                'individual_scores': individual_scores,
                'uncertainty': uncertainty,
                'confidence': 1.0 - uncertainty / (torch.mean(ensemble_score) + 1e-8)
            }
            
            return ensemble_score, scores

# Utility functions for model management

def create_model_for_deployment(config: Dict[str, Any]) -> nn.Module:
    """Create appropriate model based on deployment configuration"""
    
    deployment_type = config.get('deployment_type', 'standard')
    input_size = config.get('input_size', 14)
    hidden_size = config.get('hidden_size', 64)
    
    if deployment_type == 'edge' or config.get('lightweight', False):
        model = LightweightNetworkAutoEncoder(
            input_size=input_size,
            hidden_size=min(hidden_size, 32),
            sequence_length=config.get('sequence_length', 20)
        )
    elif deployment_type == 'ensemble':
        model = EnsembleAnomalyDetector(
            input_size=input_size,
            hidden_size=hidden_size,
            num_models=config.get('num_ensemble_models', 3)
        )
    else:
        model = NetworkAnomalyAutoEncoder(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=config.get('num_layers', 2),
            sequence_length=config.get('sequence_length', 20),
            dropout=config.get('dropout', 0.1)
        )
    
    return model

def count_parameters(model: nn.Module) -> Dict[str, int]:
    """Count model parameters"""
    
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    
    return {
        'total_parameters': total_params,
        'trainable_parameters': trainable_params,
        'non_trainable_parameters': total_params - trainable_params
    }

def model_summary(model: nn.Module, input_shape: Tuple[int, ...]) -> str:
    """Generate model summary"""
    
    param_info = count_parameters(model)
    
    # Calculate model size
    total_params = param_info['total_parameters']
    model_size_mb = (total_params * 4) / (1024 ** 2)  # Assuming float32
    
    summary = f"""
Model Summary:
==============
Model Type: {model.__class__.__name__}
Total Parameters: {total_params:,}
Trainable Parameters: {param_info['trainable_parameters']:,}
Model Size: {model_size_mb:.2f} MB
Input Shape: {input_shape}
"""
    
    return summary

def optimize_model_for_inference(model: nn.Module) -> nn.Module:
    """Optimize model for inference"""
    
    model.eval()
    
    # Disable gradient computation
    for param in model.parameters():
        param.requires_grad = False
    
    # Try to use torch.jit.script for optimization
    try:
        # Create example input
        example_input = torch.randn(1, 20, 14)  # Adjust based on your input size
        traced_model = torch.jit.trace(model, example_input)
        traced_model = torch.jit.optimize_for_inference(traced_model)
        return traced_model
    except Exception as e:
        logger.warning(f"Could not optimize model with TorchScript: {e}")
        return model

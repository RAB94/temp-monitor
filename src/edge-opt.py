#!/usr/bin/env python3
"""
Edge Device Optimization Utilities
==================================

Utilities for optimizing the Network Intelligence Monitor for edge devices:
- Model quantization and pruning
- Memory management
- CPU optimization
- Storage optimization
- Power management
- Network efficiency
"""

import logging
import os
import sys
import time
import threading
import gc
import psutil
import torch
import torch.nn as nn
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import json
import subprocess
import mmap
import tempfile

logger = logging.getLogger(__name__)

class ModelOptimizer:
    """Optimize PyTorch models for edge deployment"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.compression_stats = {}
        
    def quantize_model(self, model: nn.Module, calibration_data: Optional[torch.Tensor] = None) -> nn.Module:
        """Quantize model for edge deployment"""
        
        logger.info("Quantizing model for edge deployment...")
        
        original_size = self._get_model_size(model)
        
        try:
            # Dynamic quantization (fastest to apply)
            if self.config.get('quantization_method', 'dynamic') == 'dynamic':
                quantized_model = torch.quantization.quantize_dynamic(
                    model, 
                    {nn.Linear, nn.LSTM, nn.GRU}, 
                    dtype=torch.qint8
                )
            
            # Static quantization (better compression, needs calibration)
            elif self.config.get('quantization_method') == 'static':
                if calibration_data is None:
                    logger.warning("No calibration data provided for static quantization, using dynamic")
                    return self.quantize_model(model, None)
                
                # Prepare model for quantization
                model.qconfig = torch.quantization.get_default_qconfig('fbgemm')
                torch.quantization.prepare(model, inplace=True)
                
                # Calibrate with sample data
                model.eval()
                with torch.no_grad():
                    model(calibration_data)
                
                # Convert to quantized model
                quantized_model = torch.quantization.convert(model, inplace=False)
            
            else:
                logger.error(f"Unknown quantization method: {self.config.get('quantization_method')}")
                return model
            
            quantized_size = self._get_model_size(quantized_model)
            compression_ratio = original_size / quantized_size if quantized_size > 0 else 1
            
            self.compression_stats['quantization'] = {
                'original_size_mb': original_size / (1024**2),
                'quantized_size_mb': quantized_size / (1024**2),
                'compression_ratio': compression_ratio,
                'size_reduction_percent': (1 - quantized_size/original_size) * 100
            }
            
            logger.info(f"Model quantized: {compression_ratio:.2f}x compression, "
                       f"{self.compression_stats['quantization']['size_reduction_percent']:.1f}% size reduction")
            
            return quantized_model
            
        except Exception as e:
            logger.error(f"Error quantizing model: {e}")
            return model
    
    def prune_model(self, model: nn.Module, sparsity: float = 0.3) -> nn.Module:
        """Prune model weights for edge deployment"""
        
        logger.info(f"Pruning model with {sparsity:.1%} sparsity...")
        
        try:
            import torch.nn.utils.prune as prune
            
            original_params = sum(p.numel() for p in model.parameters())
            
            # Apply magnitude-based pruning to linear and convolution layers
            for module in model.modules():
                if isinstance(module, (nn.Linear, nn.Conv1d, nn.Conv2d)):
                    prune.l1_unstructured(module, name='weight', amount=sparsity)
                    prune.remove(module, 'weight')  # Make pruning permanent
            
            # Calculate pruning statistics
            pruned_params = sum(p.numel() for p in model.parameters())
            actual_sparsity = 1 - (pruned_params / original_params)
            
            self.compression_stats['pruning'] = {
                'original_parameters': original_params,
                'pruned_parameters': pruned_params,
                'actual_sparsity': actual_sparsity,
                'target_sparsity': sparsity
            }
            
            logger.info(f"Model pruned: {actual_sparsity:.1%} actual sparsity, "
                       f"{original_params - pruned_params} parameters removed")
            
            return model
            
        except ImportError:
            logger.warning("torch.nn.utils.prune not available, skipping pruning")
            return model
        except Exception as e:
            logger.error(f"Error pruning model: {e}")
            return model
    
    def optimize_for_inference(self, model: nn.Module) -> nn.Module:
        """Optimize model for inference performance"""
        
        logger.info("Optimizing model for inference...")
        
        try:
            # Set to evaluation mode
            model.eval()
            
            # Disable gradient computation
            for param in model.parameters():
                param.requires_grad = False
            
            # Try to compile with TorchScript for optimization
            if self.config.get('use_torchscript', True):
                try:
                    # Create example input for tracing
                    example_input = torch.randn(1, 20, 10)  # Adjust based on model
                    traced_model = torch.jit.trace(model, example_input)
                    
                    # Optimize the traced model
                    traced_model = torch.jit.optimize_for_inference(traced_model)
                    
                    logger.info("Model optimized with TorchScript")
                    return traced_model
                    
                except Exception as e:
                    logger.warning(f"TorchScript optimization failed: {e}")
            
            # Fuse operations if possible
            if hasattr(model, 'fuse_model'):
                model.fuse_model()
                logger.info("Model operations fused")
            
            return model
            
        except Exception as e:
            logger.error(f"Error optimizing model for inference: {e}")
            return model
    
    def _get_model_size(self, model: nn.Module) -> int:
        """Get model size in bytes"""
        
        total_size = 0
        for param in model.parameters():
            total_size += param.numel() * param.element_size()
        
        for buffer in model.buffers():
            total_size += buffer.numel() * buffer.element_size()
        
        return total_size
    
    def save_optimized_model(self, model: nn.Module, save_path: str):
        """Save optimized model with metadata"""
        
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save model
        torch.save(model, save_path)
        
        # Save optimization metadata
        metadata_path = save_path.with_suffix('.metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump({
                'optimization_stats': self.compression_stats,
                'optimization_config': self.config,
                'model_size_bytes': save_path.stat().st_size,
                'optimization_timestamp': time.time()
            }, f, indent=2)
        
        logger.info(f"Optimized model saved to {save_path}")

class MemoryManager:
    """Manage memory usage for edge devices"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.memory_limit_mb = config.get('memory_limit_mb', 512)
        self.gc_threshold = config.get('gc_threshold_mb', 400)
        self.monitoring_enabled = config.get('enable_monitoring', True)
        
        # Memory tracking
        self.peak_memory_mb = 0
        self.gc_count = 0
        self.oom_warnings = 0
        
        # Background monitoring
        self._monitor_thread = None
        self._running = False
        
    def start_monitoring(self):
        """Start memory monitoring"""
        
        if not self.monitoring_enabled:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._memory_monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        logger.info(f"Memory monitoring started (limit: {self.memory_limit_mb}MB)")
    
    def stop_monitoring(self):
        """Stop memory monitoring"""
        
        self._running = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
        
        logger.info("Memory monitoring stopped")
    
    def _memory_monitor_loop(self):
        """Background memory monitoring loop"""
        
        while self._running:
            try:
                current_memory = self.get_memory_usage_mb()
                
                # Update peak memory
                if current_memory > self.peak_memory_mb:
                    self.peak_memory_mb = current_memory
                
                # Check for high memory usage
                if current_memory > self.gc_threshold:
                    logger.info(f"High memory usage detected: {current_memory:.1f}MB, triggering GC")
                    self.force_garbage_collection()
                
                # Check for approaching memory limit
                if current_memory > self.memory_limit_mb * 0.9:
                    logger.warning(f"Memory usage approaching limit: {current_memory:.1f}MB / {self.memory_limit_mb}MB")
                    self.oom_warnings += 1
                    
                    # Aggressive cleanup
                    self.aggressive_cleanup()
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in memory monitor: {e}")
                time.sleep(60)
    
    def get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB"""
        
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            return memory_info.rss / (1024 * 1024)  # Convert to MB
        except Exception:
            return 0.0
    
    def get_system_memory_info(self) -> Dict[str, float]:
        """Get system memory information"""
        
        try:
            memory = psutil.virtual_memory()
            return {
                'total_mb': memory.total / (1024 * 1024),
                'available_mb': memory.available / (1024 * 1024),
                'used_mb': memory.used / (1024 * 1024),
                'percent_used': memory.percent,
                'process_mb': self.get_memory_usage_mb()
            }
        except Exception as e:
            logger.error(f"Error getting system memory info: {e}")
            return {}
    
    def force_garbage_collection(self):
        """Force garbage collection"""
        
        before_mb = self.get_memory_usage_mb()
        
        # Clear PyTorch cache
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        # Force Python GC
        collected = gc.collect()
        
        after_mb = self.get_memory_usage_mb()
        freed_mb = before_mb - after_mb
        
        self.gc_count += 1
        
        logger.debug(f"Garbage collection: freed {freed_mb:.1f}MB, collected {collected} objects")
    
    def aggressive_cleanup(self):
        """Aggressive memory cleanup for low-memory situations"""
        
        logger.info("Performing aggressive memory cleanup...")
        
        # Force multiple GC cycles
        for _ in range(3):
            gc.collect()
        
        # Clear PyTorch cache
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        # Set aggressive GC thresholds
        gc.set_threshold(100, 5, 5)
        
        logger.info("Aggressive cleanup completed")
    
    def optimize_for_memory(self):
        """Optimize Python runtime for memory usage"""
        
        # Enable memory optimizations
        try:
            # Set lower GC thresholds for frequent cleanup
            gc.set_threshold(500, 10, 10)
            
            # Enable generation-based GC
            if hasattr(gc, 'set_threshold'):
                gc.enable()
            
            logger.info("Memory optimizations applied")
            
        except Exception as e:
            logger.error(f"Error applying memory optimizations: {e}")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory management statistics"""
        
        system_info = self.get_system_memory_info()
        
        return {
            'current_usage_mb': system_info.get('process_mb', 0),
            'peak_usage_mb': self.peak_memory_mb,
            'memory_limit_mb': self.memory_limit_mb,
            'gc_count': self.gc_count,
            'oom_warnings': self.oom_warnings,
            'system_memory': system_info,
            'gc_stats': {
                'counts': gc.get_count(),
                'stats': gc.get_stats() if hasattr(gc, 'get_stats') else None
            }
        }

class CPUOptimizer:
    """Optimize CPU usage for edge devices"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_cpu_percent = config.get('max_cpu_percent', 80)
        self.thread_count = config.get('thread_count', 'auto')
        
        # CPU tracking
        self.cpu_usage_history = []
        self.throttle_count = 0
        
    def optimize_cpu_settings(self):
        """Optimize CPU settings for edge deployment"""
        
        logger.info("Optimizing CPU settings for edge deployment...")
        
        # Set thread count
        if self.thread_count == 'auto':
            cpu_count = psutil.cpu_count(logical=False) or 1
            thread_count = max(1, min(4, cpu_count))  # Limit to 4 threads max
        else:
            thread_count = self.thread_count
        
        # Set PyTorch thread count
        torch.set_num_threads(thread_count)
        
        # Set OpenMP threads if available
        os.environ['OMP_NUM_THREADS'] = str(thread_count)
        os.environ['MKL_NUM_THREADS'] = str(thread_count)
        
        # Disable PyTorch JIT for memory savings
        if self.config.get('disable_jit', True):
            torch.jit.set_fusion_enabled(False)
            os.environ['PYTORCH_JIT'] = '0'
        
        # Set CPU affinity if on Raspberry Pi
        if self._is_raspberry_pi():
            try:
                # Use CPU cores efficiently
                psutil.Process().cpu_affinity(list(range(thread_count)))
                logger.info(f"CPU affinity set to {thread_count} cores")
            except Exception as e:
                logger.debug(f"Could not set CPU affinity: {e}")
        
        logger.info(f"CPU optimization applied: {thread_count} threads")
    
    def monitor_cpu_usage(self) -> float:
        """Monitor current CPU usage"""
        
        cpu_percent = psutil.cpu_percent(interval=1)
        self.cpu_usage_history.append((time.time(), cpu_percent))
        
        # Keep only recent history
        cutoff_time = time.time() - 300  # 5 minutes
        self.cpu_usage_history = [
            (t, cpu) for t, cpu in self.cpu_usage_history if t > cutoff_time
        ]
        
        return cpu_percent
    
    def should_throttle(self) -> bool:
        """Check if processing should be throttled due to high CPU"""
        
        if len(self.cpu_usage_history) < 3:
            return False
        
        # Check average CPU over last minute
        minute_ago = time.time() - 60
        recent_usage = [cpu for t, cpu in self.cpu_usage_history if t > minute_ago]
        
        if recent_usage:
            avg_cpu = sum(recent_usage) / len(recent_usage)
            return avg_cpu > self.max_cpu_percent
        
        return False
    
    def apply_throttling(self, delay_seconds: float = 1.0):
        """Apply CPU throttling by adding delays"""
        
        self.throttle_count += 1
        time.sleep(delay_seconds)
        logger.debug(f"Applied CPU throttling: {delay_seconds}s delay")
    
    def _is_raspberry_pi(self) -> bool:
        """Check if running on Raspberry Pi"""
        
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
                return 'BCM' in cpuinfo or 'ARM' in cpuinfo or 'Raspberry' in cpuinfo
        except FileNotFoundError:
            return False
    
    def get_cpu_stats(self) -> Dict[str, Any]:
        """Get CPU optimization statistics"""
        
        recent_usage = [cpu for t, cpu in self.cpu_usage_history if t > time.time() - 300]
        
        return {
            'current_cpu_percent': psutil.cpu_percent(),
            'average_cpu_5min': sum(recent_usage) / len(recent_usage) if recent_usage else 0,
            'max_cpu_percent': self.max_cpu_percent,
            'thread_count': torch.get_num_threads(),
            'throttle_count': self.throttle_count,
            'cpu_count_physical': psutil.cpu_count(logical=False),
            'cpu_count_logical': psutil.cpu_count(logical=True),
            'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
        }

class StorageOptimizer:
    """Optimize storage usage for edge devices"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_storage_percent = config.get('max_storage_percent', 80)
        self.data_retention_days = config.get('data_retention_days', 7)
        
    def optimize_storage(self, data_dir: Path):
        """Optimize storage usage"""
        
        logger.info("Optimizing storage usage...")
        
        # Get current storage usage
        usage = self.get_storage_usage(data_dir)
        
        if usage['percent_used'] > self.max_storage_percent:
            logger.warning(f"Storage usage high: {usage['percent_used']:.1f}%")
            
            # Clean old data
            self.cleanup_old_data(data_dir)
            
            # Compress logs
            self.compress_log_files(data_dir / 'logs')
            
            # Clean temporary files
            self.cleanup_temp_files()
    
    def get_storage_usage(self, path: Path) -> Dict[str, float]:
        """Get storage usage information"""
        
        try:
            usage = psutil.disk_usage(str(path))
            
            return {
                'total_gb': usage.total / (1024**3),
                'used_gb': usage.used / (1024**3),
                'free_gb': usage.free / (1024**3),
                'percent_used': (usage.used / usage.total) * 100
            }
        except Exception as e:
            logger.error(f"Error getting storage usage: {e}")
            return {}
    
    def cleanup_old_data(self, data_dir: Path):
        """Clean up old data files"""
        
        cutoff_time = time.time() - (self.data_retention_days * 24 * 3600)
        cleaned_files = 0
        cleaned_size = 0
        
        # Clean database files
        db_dir = data_dir / 'database'
        if db_dir.exists():
            for db_file in db_dir.glob('*.db-*'):  # Backup files
                if db_file.stat().st_mtime < cutoff_time:
                    cleaned_size += db_file.stat().st_size
                    db_file.unlink()
                    cleaned_files += 1
        
        # Clean model checkpoints
        model_dir = data_dir / 'models'
        if model_dir.exists():
            for model_file in model_dir.glob('*.backup'):
                if model_file.stat().st_mtime < cutoff_time:
                    cleaned_size += model_file.stat().st_size
                    model_file.unlink()
                    cleaned_files += 1
        
        if cleaned_files > 0:
            logger.info(f"Cleaned {cleaned_files} old files, freed {cleaned_size / (1024**2):.1f}MB")
    
    def compress_log_files(self, log_dir: Path):
        """Compress old log files"""
        
        if not log_dir.exists():
            return
        
        import gzip
        cutoff_time = time.time() - (24 * 3600)  # Compress logs older than 1 day
        
        for log_file in log_dir.glob('*.log'):
            if log_file.stat().st_mtime < cutoff_time:
                compressed_file = log_file.with_suffix('.log.gz')
                
                if not compressed_file.exists():
                    try:
                        with open(log_file, 'rb') as f_in:
                            with gzip.open(compressed_file, 'wb') as f_out:
                                f_out.writelines(f_in)
                        
                        log_file.unlink()
                        logger.debug(f"Compressed log file: {log_file.name}")
                        
                    except Exception as e:
                        logger.error(f"Error compressing log file {log_file}: {e}")
    
    def cleanup_temp_files(self):
        """Clean up temporary files"""
        
        temp_dir = Path(tempfile.gettempdir())
        pattern = 'network_monitor_*'
        
        for temp_file in temp_dir.glob(pattern):
            try:
                if temp_file.is_file():
                    temp_file.unlink()
                elif temp_file.is_dir():
                    import shutil
                    shutil.rmtree(temp_file)
            except Exception as e:
                logger.debug(f"Could not clean temp file {temp_file}: {e}")

class EdgeOptimizer:
    """Main edge device optimization manager"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Initialize components
        self.model_optimizer = ModelOptimizer(config.get('model_optimization', {}))
        self.memory_manager = MemoryManager(config.get('memory_management', {}))
        self.cpu_optimizer = CPUOptimizer(config.get('cpu_optimization', {}))
        self.storage_optimizer = StorageOptimizer(config.get('storage_optimization', {}))
        
        # Edge detection
        self.is_edge_device = self._detect_edge_device()
        
    def optimize_for_edge(self, model: Optional[nn.Module] = None, data_dir: Optional[Path] = None):
        """Apply all edge optimizations"""
        
        if not self.is_edge_device and not self.config.get('force_edge_optimization', False):
            logger.info("Not an edge device, skipping edge optimizations")
            return model
        
        logger.info("Applying edge device optimizations...")
        
        # CPU optimizations
        self.cpu_optimizer.optimize_cpu_settings()
        
        # Memory optimizations
        self.memory_manager.optimize_for_memory()
        self.memory_manager.start_monitoring()
        
        # Model optimizations
        if model is not None:
            # Quantize model
            if self.config.get('model_optimization', {}).get('enable_quantization', True):
                model = self.model_optimizer.quantize_model(model)
            
            # Prune model
            if self.config.get('model_optimization', {}).get('enable_pruning', False):
                sparsity = self.config.get('model_optimization', {}).get('pruning_sparsity', 0.3)
                model = self.model_optimizer.prune_model(model, sparsity)
            
            # Optimize for inference
            model = self.model_optimizer.optimize_for_inference(model)
        
        # Storage optimizations
        if data_dir is not None:
            self.storage_optimizer.optimize_storage(data_dir)
        
        logger.info("Edge optimizations applied successfully")
        return model
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get comprehensive optimization statistics"""
        
        return {
            'is_edge_device': self.is_edge_device,
            'model_optimization': self.model_optimizer.compression_stats,
            'memory_stats': self.memory_manager.get_memory_stats(),
            'cpu_stats': self.cpu_optimizer.get_cpu_stats(),
            'storage_stats': self.storage_optimizer.get_storage_usage(Path('.')),
            'system_info': self._get_system_info()
        }
    
    def _detect_edge_device(self) -> bool:
        """Detect if running on an edge device"""
        
        # Check for Raspberry Pi
        if self._is_raspberry_pi():
            return True
        
        # Check for low memory (< 2GB)
        try:
            memory = psutil.virtual_memory()
            if memory.total < 2 * 1024**3:  # Less than 2GB
                return True
        except Exception:
            pass
        
        # Check for ARM architecture
        try:
            import platform
            if 'arm' in platform.machine().lower():
                return True
        except Exception:
            pass
        
        # Check environment variable
        if os.getenv('DEPLOYMENT_TYPE') == 'edge':
            return True
        
        return False
    
    def _is_raspberry_pi(self) -> bool:
        """Check if running on Raspberry Pi"""
        
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
                return any(indicator in cpuinfo for indicator in 
                          ['BCM', 'ARM', 'Raspberry', 'raspberry'])
        except FileNotFoundError:
            return False
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        
        try:
            import platform
            
            return {
                'platform': platform.platform(),
                'architecture': platform.architecture(),
                'machine': platform.machine(),
                'processor': platform.processor(),
                'python_version': platform.python_version(),
                'cpu_count': psutil.cpu_count(),
                'memory_total_gb': psutil.virtual_memory().total / (1024**3),
                'is_raspberry_pi': self._is_raspberry_pi()
            }
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return {}
    
    def create_edge_config(self) -> Dict[str, Any]:
        """Create optimized configuration for edge deployment"""
        
        config = {
            'logging': {
                'level': 'INFO',  # Reduce logging for edge
                'max_size_mb': 5,  # Smaller log files
                'backup_count': 2
            },
            'monitoring': {
                'interval': 60,  # Less frequent monitoring
                'timeout': 15
            },
            'ai': {
                'baseline_window': 500,  # Smaller window
                'initial_epochs': 50,  # Fewer training epochs
                'train_interval': 7200  # Less frequent training
            },
            'database': {
                'cleanup_days': 3,  # Keep less data
                'backup_enabled': False  # Disable backups on edge
            },
            'model_optimization': {
                'enable_quantization': True,
                'enable_pruning': False,  # Can be enabled for more aggressive optimization
                'quantization_method': 'dynamic',
                'use_torchscript': True
            },
            'memory_management': {
                'memory_limit_mb': 256,
                'gc_threshold_mb': 200,
                'enable_monitoring': True
            },
            'cpu_optimization': {
                'max_cpu_percent': 70,
                'thread_count': 2,
                'disable_jit': True
            },
            'storage_optimization': {
                'max_storage_percent': 75,
                'data_retention_days': 3
            }
        }
        
        return config

# Utility functions

def create_edge_optimizer(config: Dict[str, Any]) -> EdgeOptimizer:
    """Create edge optimizer with configuration"""
    
    return EdgeOptimizer(config)

def optimize_model_for_edge(model: nn.Module, config: Dict[str, Any]) -> nn.Module:
    """Optimize a model for edge deployment"""
    
    optimizer = create_edge_optimizer(config)
    return optimizer.optimize_for_edge(model=model)

def setup_edge_environment():
    """Setup environment for edge deployment"""
    
    # Set environment variables for edge deployment
    os.environ['PYTORCH_JIT'] = '0'
    os.environ['OMP_NUM_THREADS'] = '2'
    os.environ['MKL_NUM_THREADS'] = '2'
    
    # Disable CUDA if no GPU
    if not torch.cuda.is_available():
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
    
    # Set memory allocator for better memory management
    if hasattr(torch, 'set_default_tensor_type'):
        torch.set_default_tensor_type(torch.FloatTensor)
    
    logger.info("Edge environment setup completed")

def benchmark_edge_performance(model: nn.Module, input_shape: Tuple[int, ...] = (1, 20, 10)) -> Dict[str, float]:
    """Benchmark model performance on edge device"""
    
    logger.info("Benchmarking edge performance...")
    
    model.eval()
    example_input = torch.randn(*input_shape)
    
    # Warmup
    with torch.no_grad():
        for _ in range(10):
            _ = model(example_input)
    
    # Benchmark inference time
    inference_times = []
    memory_usage = []
    
    for _ in range(100):
        start_time = time.time()
        memory_before = psutil.Process().memory_info().rss / (1024**2)
        
        with torch.no_grad():
            _ = model(example_input)
        
        memory_after = psutil.Process().memory_info().rss / (1024**2)
        end_time = time.time()
        
        inference_times.append((end_time - start_time) * 1000)  # Convert to ms
        memory_usage.append(memory_after - memory_before)
    
    return {
        'avg_inference_time_ms': sum(inference_times) / len(inference_times),
        'min_inference_time_ms': min(inference_times),
        'max_inference_time_ms': max(inference_times),
        'avg_memory_delta_mb': sum(memory_usage) / len(memory_usage),
        'model_size_mb': sum(p.numel() * p.element_size() for p in model.parameters()) / (1024**2)
    }

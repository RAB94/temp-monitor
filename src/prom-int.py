#!/usr/bin/env python3
"""
Mimir/Prometheus Integration Module
==================================

Integration with Prometheus/Mimir for historical data analysis and baseline creation.
Features:
- Optimized PromQL queries for historical baselines
- Time series aggregation and analysis
- Seasonal pattern detection from historical data
- Efficient data fetching with caching
- Multi-tenancy support for Mimir
"""

import asyncio
import aiohttp
import logging
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlencode
import json
from concurrent.futures import ThreadPoolExecutor
import math

logger = logging.getLogger(__name__)

@dataclass
class PromQueryResult:
    """Prometheus query result"""
    metric_name: str
    labels: Dict[str, str]
    values: List[Tuple[float, float]]  # (timestamp, value)
    metadata: Dict[str, Any]

@dataclass
class HistoricalBaseline:
    """Historical baseline data structure"""
    metric_name: str
    baseline_type: str  # 'mean', 'median', 'percentile'
    time_period: str    # 'hourly', 'daily', 'weekly'
    values: Dict[str, float]  # time_key -> baseline_value
    confidence_intervals: Dict[str, Tuple[float, float]]
    seasonal_patterns: Dict[str, float]
    last_updated: float

class MimirPrometheusClient:
    """Client for Mimir/Prometheus integration"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_url = config.get('prometheus_url', 'http://localhost:9090')
        self.mimir_url = config.get('mimir_url', None)
        self.tenant_id = config.get('tenant_id', 'default')
        self.timeout = config.get('timeout', 30)
        self.max_retries = config.get('max_retries', 3)
        
        # Query optimization settings
        self.max_resolution = config.get('max_resolution', '1m')
        self.chunk_size = config.get('chunk_size_hours', 24)
        
        # Caching
        self.cache = {}
        self.cache_ttl = config.get('cache_ttl_seconds', 300)  # 5 minutes
        
        # Session for connection pooling
        self.session = None
        
        # Executor for CPU-intensive operations
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def initialize(self):
        """Initialize the client"""
        
        # Create aiohttp session with optimizations
        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=20,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        # Headers for Mimir multi-tenancy
        headers = {}
        if self.mimir_url and self.tenant_id:
            headers['X-Scope-OrgID'] = self.tenant_id
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers
        )
        
        logger.info("Mimir/Prometheus client initialized")
    
    async def close(self):
        """Close the client"""
        if self.session:
            await self.session.close()
        self.executor.shutdown(wait=True)
    
    def _get_cache_key(self, query: str, start_time: float, end_time: float, step: str) -> str:
        """Generate cache key for query"""
        return f"{hash(query)}_{start_time}_{end_time}_{step}"
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid"""
        return time.time() - cache_entry['timestamp'] < self.cache_ttl
    
    async def _execute_query(self, query: str, start_time: float, 
                           end_time: float, step: str = '1m') -> List[PromQueryResult]:
        """Execute Prometheus query with retry logic"""
        
        # Check cache first
        cache_key = self._get_cache_key(query, start_time, end_time, step)
        if cache_key in self.cache and self._is_cache_valid(self.cache[cache_key]):
            logger.debug(f"Cache hit for query: {query[:50]}...")
            return self.cache[cache_key]['data']
        
        # Use Mimir URL if available, otherwise Prometheus
        base_url = self.mimir_url if self.mimir_url else self.base_url
        url = f"{base_url}/api/v1/query_range"
        
        params = {
            'query': query,
            'start': start_time,
            'end': end_time,
            'step': step
        }
        
        for attempt in range(self.max_retries):
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data['status'] == 'success':
                            results = self._parse_query_response(data['data'])
                            
                            # Cache the results
                            self.cache[cache_key] = {
                                'data': results,
                                'timestamp': time.time()
                            }
                            
                            return results
                        else:
                            logger.error(f"Prometheus query failed: {data.get('error', 'Unknown error')}")
                            
                    elif response.status == 429:  # Rate limited
                        wait_time = 2 ** attempt
                        logger.warning(f"Rate limited, waiting {wait_time}s before retry")
                        await asyncio.sleep(wait_time)
                        continue
                        
                    else:
                        logger.error(f"HTTP error {response.status}: {await response.text()}")
                        
            except Exception as e:
                logger.error(f"Query attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise
        
        raise Exception(f"Failed to execute query after {self.max_retries} attempts")
    
    def _parse_query_response(self, data: Dict[str, Any]) -> List[PromQueryResult]:
        """Parse Prometheus query response"""
        
        results = []
        
        for result in data.get('result', []):
            metric_name = result['metric'].get('__name__', 'unknown')
            labels = {k: v for k, v in result['metric'].items() if k != '__name__'}
            
            values = []
            for timestamp, value in result.get('values', []):
                try:
                    values.append((float(timestamp), float(value)))
                except (ValueError, TypeError):
                    continue  # Skip invalid values
            
            results.append(PromQueryResult(
                metric_name=metric_name,
                labels=labels,
                values=values,
                metadata={'result_type': data.get('resultType', 'matrix')}
            ))
        
        return results
    
    async def get_historical_data(self, metric_query: str, hours_back: int = 24,
                                 resolution: str = '1m') -> List[PromQueryResult]:
        """Get historical data for a metric"""
        
        end_time = time.time()
        start_time = end_time - (hours_back * 3600)
        
        return await self._execute_query(metric_query, start_time, end_time, resolution)
    
    async def create_baseline_from_history(self, metric_queries: List[str],
                                         days_back: int = 30) -> Dict[str, HistoricalBaseline]:
        """Create baselines from historical data"""
        
        logger.info(f"Creating baselines from {days_back} days of historical data")
        
        baselines = {}
        
        for query in metric_queries:
            try:
                # Get historical data in chunks to avoid memory issues
                baseline = await self._process_baseline_query(query, days_back)
                if baseline:
                    baselines[query] = baseline
                    
            except Exception as e:
                logger.error(f"Failed to create baseline for {query}: {e}")
                continue
        
        return baselines
    
    async def _process_baseline_query(self, query: str, days_back: int) -> Optional[HistoricalBaseline]:
        """Process a single baseline query"""
        
        all_data = []
        end_time = time.time()
        
        # Process in chunks to avoid memory issues and query timeouts
        for chunk in range(0, days_back * 24, self.chunk_size):
            chunk_end = end_time - (chunk * 3600)
            chunk_start = end_time - ((chunk + self.chunk_size) * 3600)
            
            try:
                chunk_data = await self._execute_query(
                    query, chunk_start, chunk_end, self.max_resolution
                )
                all_data.extend(chunk_data)
                
                # Small delay to avoid overwhelming the server
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.warning(f"Failed to fetch chunk {chunk}-{chunk + self.chunk_size}: {e}")
                continue
        
        if not all_data:
            return None
        
        # Process data in executor to avoid blocking
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, self._calculate_baseline_statistics, all_data, query
        )
    
    def _calculate_baseline_statistics(self, data: List[PromQueryResult], 
                                     query: str) -> HistoricalBaseline:
        """Calculate baseline statistics from historical data"""
        
        # Combine all time series data
        all_values = []
        timestamps = []
        
        for result in data:
            for timestamp, value in result.values:
                all_values.append(value)
                timestamps.append(timestamp)
        
        if not all_values:
            return None
        
        # Convert to numpy arrays for efficient processing
        values_array = np.array(all_values)
        timestamps_array = np.array(timestamps)
        
        # Create DataFrame for time-based analysis
        df = pd.DataFrame({
            'timestamp': pd.to_datetime(timestamps_array, unit='s'),
            'value': values_array
        })
        
        # Calculate hourly baselines
        df['hour'] = df['timestamp'].dt.hour
        hourly_baselines = df.groupby('hour')['value'].agg([
            'mean', 'median', 'std', 
            lambda x: np.percentile(x, 25),
            lambda x: np.percentile(x, 75)
        ]).to_dict('index')
        
        # Calculate daily baselines
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        daily_baselines = df.groupby('day_of_week')['value'].agg([
            'mean', 'median', 'std',
            lambda x: np.percentile(x, 25),
            lambda x: np.percentile(x, 75)
        ]).to_dict('index')
        
        # Detect seasonal patterns using FFT
        seasonal_patterns = self._detect_seasonal_patterns(values_array, timestamps_array)
        
        # Create comprehensive baseline
        baseline_values = {}
        confidence_intervals = {}
        
        # Process hourly baselines
        for hour, stats in hourly_baselines.items():
            baseline_values[f"hour_{hour}"] = stats['mean']
            confidence_intervals[f"hour_{hour}"] = (
                stats['<lambda_0>'], stats['<lambda_1>']  # Q25, Q75
            )
        
        # Process daily baselines
        for day, stats in daily_baselines.items():
            baseline_values[f"day_{day}"] = stats['mean']
            confidence_intervals[f"day_{day}"] = (
                stats['<lambda_0>'], stats['<lambda_1>']  # Q25, Q75
            )
        
        # Overall statistics
        baseline_values['overall_mean'] = float(np.mean(values_array))
        baseline_values['overall_median'] = float(np.median(values_array))
        baseline_values['overall_std'] = float(np.std(values_array))
        
        return HistoricalBaseline(
            metric_name=query,
            baseline_type='comprehensive',
            time_period='multi',
            values=baseline_values,
            confidence_intervals=confidence_intervals,
            seasonal_patterns=seasonal_patterns,
            last_updated=time.time()
        )
    
    def _detect_seasonal_patterns(self, values: np.ndarray, 
                                timestamps: np.ndarray) -> Dict[str, float]:
        """Detect seasonal patterns using FFT"""
        
        if len(values) < 48:  # Need at least 48 data points
            return {}
        
        try:
            # Sort by timestamp to ensure proper ordering
            sorted_indices = np.argsort(timestamps)
            sorted_values = values[sorted_indices]
            
            # Normalize values
            normalized_values = (sorted_values - np.mean(sorted_values)) / (np.std(sorted_values) + 1e-8)
            
            # Apply FFT
            fft_values = np.fft.fft(normalized_values)
            freqs = np.fft.fftfreq(len(normalized_values))
            
            # Calculate power spectrum
            power = np.abs(fft_values) ** 2
            
            # Find dominant frequencies
            dominant_indices = np.argsort(power)[-10:]  # Top 10 frequencies
            
            patterns = {}
            
            # Convert frequencies to periods (in hours)
            sample_rate = len(normalized_values) / (np.max(timestamps) - np.min(timestamps)) * 3600
            
            for idx in dominant_indices:
                if freqs[idx] > 0:  # Only positive frequencies
                    period_hours = 1.0 / (freqs[idx] * sample_rate)
                    
                    # Classify patterns
                    if 0.8 <= period_hours <= 1.2:  # ~1 hour
                        patterns['hourly'] = float(power[idx])
                    elif 23 <= period_hours <= 25:  # ~24 hours
                        patterns['daily'] = float(power[idx])
                    elif 167 <= period_hours <= 169:  # ~168 hours (7 days)
                        patterns['weekly'] = float(power[idx])
            
            return patterns
            
        except Exception as e:
            logger.warning(f"Failed to detect seasonal patterns: {e}")
            return {}
    
    async def get_network_metrics_baselines(self, target_hosts: List[str] = None,
                                          days_back: int = 30) -> Dict[str, HistoricalBaseline]:
        """Get network-specific metrics baselines"""
        
        if not target_hosts:
            target_hosts = ['.*']  # Match all hosts
        
        # Define network metrics queries
        network_queries = []
        
        for host_pattern in target_hosts:
            queries = [
                # ICMP metrics
                f'avg_over_time(ping_rtt_ms{{target=~"{host_pattern}"}}[5m])',
                f'avg_over_time(ping_loss_percent{{target=~"{host_pattern}"}}[5m])',
                
                # HTTP metrics
                f'avg_over_time(http_request_duration_seconds{{target=~"{host_pattern}"}}[5m])',
                f'rate(http_requests_total{{target=~"{host_pattern}"}}[5m])',
                
                # DNS metrics
                f'avg_over_time(dns_lookup_time_seconds{{target=~"{host_pattern}"}}[5m])',
                
                # Network interface metrics
                f'rate(node_network_receive_bytes_total{{instance=~"{host_pattern}"}}[5m])',
                f'rate(node_network_transmit_bytes_total{{instance=~"{host_pattern}"}}[5m])',
                f'rate(node_network_receive_errs_total{{instance=~"{host_pattern}"}}[5m])',
                
                # TCP connection metrics
                f'node_netstat_Tcp_CurrEstab{{instance=~"{host_pattern}"}}',
                f'rate(node_netstat_TcpExt_TCPTimeouts{{instance=~"{host_pattern}"}}[5m])'
            ]
            network_queries.extend(queries)
        
        return await self.create_baseline_from_history(network_queries, days_back)
    
    async def compare_current_to_baseline(self, current_metrics: Dict[str, float],
                                        baselines: Dict[str, HistoricalBaseline]) -> Dict[str, Dict[str, Any]]:
        """Compare current metrics to historical baselines"""
        
        comparisons = {}
        current_time = datetime.now()
        hour_of_day = current_time.hour
        day_of_week = current_time.weekday()
        
        for metric_name, current_value in current_metrics.items():
            # Find matching baseline
            matching_baseline = None
            for baseline_query, baseline in baselines.items():
                if metric_name in baseline_query or any(
                    keyword in baseline_query.lower() 
                    for keyword in metric_name.lower().split('_')
                ):
                    matching_baseline = baseline
                    break
            
            if not matching_baseline:
                continue
            
            # Get appropriate baseline value
            baseline_value = None
            confidence_interval = None
            
            # Try hourly baseline first
            hourly_key = f"hour_{hour_of_day}"
            if hourly_key in matching_baseline.values:
                baseline_value = matching_baseline.values[hourly_key]
                confidence_interval = matching_baseline.confidence_intervals.get(hourly_key)
            
            # Fall back to daily baseline
            if baseline_value is None:
                daily_key = f"day_{day_of_week}"
                if daily_key in matching_baseline.values:
                    baseline_value = matching_baseline.values[daily_key]
                    confidence_interval = matching_baseline.confidence_intervals.get(daily_key)
            
            # Fall back to overall baseline
            if baseline_value is None:
                baseline_value = matching_baseline.values.get('overall_mean')
                overall_std = matching_baseline.values.get('overall_std', 0)
                confidence_interval = (
                    baseline_value - 2 * overall_std,
                    baseline_value + 2 * overall_std
                ) if baseline_value else None
            
            if baseline_value is not None:
                # Calculate deviation
                deviation_percent = ((current_value - baseline_value) / baseline_value * 100) if baseline_value != 0 else 0
                
                # Determine if anomalous
                is_anomalous = False
                if confidence_interval:
                    is_anomalous = current_value < confidence_interval[0] or current_value > confidence_interval[1]
                
                # Determine severity
                abs_deviation = abs(deviation_percent)
                if abs_deviation > 50:
                    severity = "critical"
                elif abs_deviation > 25:
                    severity = "high"
                elif abs_deviation > 10:
                    severity = "medium"
                else:
                    severity = "low"
                
                comparisons[metric_name] = {
                    'current_value': current_value,
                    'baseline_value': baseline_value,
                    'deviation_percent': deviation_percent,
                    'is_anomalous': is_anomalous,
                    'severity': severity,
                    'confidence_interval': confidence_interval,
                    'seasonal_patterns': matching_baseline.seasonal_patterns,
                    'baseline_age_hours': (time.time() - matching_baseline.last_updated) / 3600
                }
        
        return comparisons
    
    async def get_recording_rules_suggestions(self, 
                                            baseline_queries: List[str]) -> List[Dict[str, str]]:
        """Generate Prometheus recording rules for efficient baseline queries"""
        
        recording_rules = []
        
        for query in baseline_queries:
            # Create recording rule name
            rule_name = f"baseline_{hash(query) % 10000:04d}"
            
            # Create aggregated versions of the query for different time windows
            time_windows = ['5m', '1h', '6h', '24h']
            
            for window in time_windows:
                # Wrap query in rate/avg_over_time if needed
                if 'rate(' not in query and 'increase(' not in query:
                    processed_query = f"avg_over_time(({query})[{window}])"
                else:
                    processed_query = query
                
                recording_rule = {
                    'name': f"{rule_name}_{window}",
                    'query': processed_query,
                    'interval': window,
                    'labels': {
                        'baseline_type': 'network_intelligence',
                        'time_window': window
                    }
                }
                
                recording_rules.append(recording_rule)
        
        return recording_rules
    
    async def test_connectivity(self) -> Dict[str, Any]:
        """Test connectivity to Prometheus/Mimir"""
        
        test_results = {}
        
        # Test Prometheus
        if self.base_url:
            try:
                url = f"{self.base_url}/api/v1/query"
                params = {'query': 'up'}
                
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        test_results['prometheus'] = {
                            'status': 'connected',
                            'response_time_ms': response.headers.get('X-Response-Time', 'unknown'),
                            'active_targets': len(data.get('data', {}).get('result', []))
                        }
                    else:
                        test_results['prometheus'] = {
                            'status': 'error',
                            'error': f"HTTP {response.status}"
                        }
                        
            except Exception as e:
                test_results['prometheus'] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        # Test Mimir if configured
        if self.mimir_url:
            try:
                url = f"{self.mimir_url}/api/v1/query"
                params = {'query': 'up'}
                
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        test_results['mimir'] = {
                            'status': 'connected',
                            'tenant_id': self.tenant_id,
                            'response_time_ms': response.headers.get('X-Response-Time', 'unknown')
                        }
                    else:
                        test_results['mimir'] = {
                            'status': 'error',
                            'error': f"HTTP {response.status}"
                        }
                        
            except Exception as e:
                test_results['mimir'] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        return test_results
    
    def get_optimized_queries(self) -> Dict[str, str]:
        """Get optimized PromQL queries for common network metrics"""
        
        return {
            # Latency metrics
            'avg_latency_5m': 'avg_over_time(ping_rtt_ms[5m])',
            'p95_latency_5m': 'histogram_quantile(0.95, avg_over_time(ping_rtt_ms[5m]))',
            
            # Packet loss
            'packet_loss_rate': 'avg_over_time(ping_loss_percent[5m])',
            
            # Bandwidth utilization
            'interface_utilization': '''
                (
                  rate(node_network_receive_bytes_total[5m]) + 
                  rate(node_network_transmit_bytes_total[5m])
                ) * 8 / 1000000  # Convert to Mbps
            ''',
            
            # Connection metrics
            'tcp_connections': 'node_netstat_Tcp_CurrEstab',
            'tcp_timeouts_rate': 'rate(node_netstat_TcpExt_TCPTimeouts[5m])',
            
            # HTTP performance
            'http_response_time_p95': 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))',
            'http_error_rate': 'rate(http_requests_total{code!~"2.."}[5m]) / rate(http_requests_total[5m])',
            
            # DNS performance
            'dns_lookup_time_avg': 'avg_over_time(dns_lookup_time_seconds[5m])',
            
            # System health indicators
            'cpu_utilization': '100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
            'memory_utilization': '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
            
            # Network errors
            'interface_errors_rate': 'rate(node_network_receive_errs_total[5m]) + rate(node_network_transmit_errs_total[5m])'
        }

# Utility functions for integration

async def create_mimir_client(config: Dict[str, Any]) -> MimirPrometheusClient:
    """Create and initialize Mimir client"""
    
    client = MimirPrometheusClient(config)
    await client.initialize()
    return client

async def integrate_with_existing_detector(detector, mimir_client: MimirPrometheusClient,
                                         target_hosts: List[str] = None, days_back: int = 30):
    """Integrate Mimir baselines with existing anomaly detector"""
    
    try:
        # Get historical baselines
        logger.info("Fetching historical baselines from Mimir/Prometheus...")
        baselines = await mimir_client.get_network_metrics_baselines(target_hosts, days_back)
        
        if not baselines:
            logger.warning("No baselines retrieved from Mimir/Prometheus")
            return
        
        # Update detector's baseline with historical data
        for query, baseline in baselines.items():
            # Convert Mimir baseline to detector's baseline format
            detector_baseline = {
                'hourly_patterns': {},
                'daily_patterns': {},
                'overall_stats': {
                    'mean': baseline.values.get('overall_mean', 0),
                    'std': baseline.values.get('overall_std', 1),
                    'median': baseline.values.get('overall_median', 0)
                }
            }
            
            # Add hourly patterns
            for hour in range(24):
                hour_key = f"hour_{hour}"
                if hour_key in baseline.values:
                    detector_baseline['hourly_patterns'][hour] = {
                        'mean': baseline.values[hour_key],
                        'confidence_interval': baseline.confidence_intervals.get(hour_key, (0, 0))
                    }
            
            # Add daily patterns
            for day in range(7):
                day_key = f"day_{day}"
                if day_key in baseline.values:
                    detector_baseline['daily_patterns'][day] = {
                        'mean': baseline.values[day_key],
                        'confidence_interval': baseline.confidence_intervals.get(day_key, (0, 0))
                    }
            
            # Store in detector (assuming detector has an enhanced baseline storage)
            if hasattr(detector, 'historical_baselines'):
                detector.historical_baselines[query] = detector_baseline
        
        logger.info(f"Integrated {len(baselines)} historical baselines with anomaly detector")
        
    except Exception as e:
        logger.error(f"Failed to integrate Mimir baselines: {e}")

def generate_prometheus_config(network_targets: List[str]) -> Dict[str, Any]:
    """Generate Prometheus configuration for network monitoring"""
    
    config = {
        'global': {
            'scrape_interval': '15s',
            'evaluation_interval': '15s'
        },
        'scrape_configs': [
            {
                'job_name': 'network-intelligence-monitor',
                'static_configs': [
                    {
                        'targets': ['localhost:5000'],  # API server
                        'labels': {
                            'service': 'network-monitor',
                            'type': 'internal'
                        }
                    }
                ],
                'scrape_interval': '30s',
                'metrics_path': '/metrics'
            },
            {
                'job_name': 'blackbox-network',
                'metrics_path': '/probe',
                'params': {
                    'module': ['icmp']
                },
                'static_configs': [
                    {
                        'targets': network_targets,
                        'labels': {
                            'type': 'network-target'
                        }
                    }
                ],
                'relabel_configs': [
                    {
                        'source_labels': ['__address__'],
                        'target_label': '__param_target'
                    },
                    {
                        'source_labels': ['__param_target'],
                        'target_label': 'instance'
                    },
                    {
                        'target_label': '__address__',
                        'replacement': 'blackbox-exporter:9115'
                    }
                ]
            }
        ],
        'rule_files': [
            'network_intelligence_rules.yml'
        ]
    }
    
    return config

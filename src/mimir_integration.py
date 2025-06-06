#!/usr/bin/env python3
"""
Fixed Mimir Integration Module
=============================

Fixed version with the missing _process_baseline_query method and proper error handling.
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
class MimirQueryResult:
    """Mimir query result"""
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

class MimirClient:
    """Client for Mimir integration with proper error handling"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.mimir_url = config.get('mimir_url')
        self.tenant_id = config.get('tenant_id', 'network-monitoring')
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
        if self.tenant_id:
            headers['X-Scope-OrgID'] = self.tenant_id
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers
        )
        
        logger.info("Mimir client initialized")
    
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
                           end_time: float, step: str = '1m') -> List[MimirQueryResult]:
        """Execute Mimir query with retry logic"""
        
        # Check cache first
        cache_key = self._get_cache_key(query, start_time, end_time, step)
        if cache_key in self.cache and self._is_cache_valid(self.cache[cache_key]):
            logger.debug(f"Cache hit for query: {query[:50]}...")
            return self.cache[cache_key]['data']
        
        if not self.mimir_url:
            logger.error("Mimir URL not configured")
            return []
        
        url = f"{self.mimir_url}/api/v1/query_range"
        
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
                            logger.error(f"Mimir query failed: {data.get('error', 'Unknown error')}")
                            
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
    
    def _parse_query_response(self, data: Dict[str, Any]) -> List[MimirQueryResult]:
        """Parse Mimir query response"""
        
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
            
            results.append(MimirQueryResult(
                metric_name=metric_name,
                labels=labels,
                values=values,
                metadata={'result_type': data.get('resultType', 'matrix')}
            ))
        
        return results
    
    async def get_historical_data(self, metric_query: str, hours_back: int = 24,
                                 resolution: str = '1m') -> List[MimirQueryResult]:
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
    
    # THIS WAS THE MISSING METHOD:
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
    
    def _calculate_baseline_statistics(self, data: List[MimirQueryResult], 
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
        """Get network-specific metrics baselines from Mimir"""
        
        if not self.mimir_url:
            logger.info("Mimir URL not configured, skipping baseline collection")
            return {}
        
        if not target_hosts:
            target_hosts = ['.*']  # Match all hosts
        
        # Define network metrics queries for data coming from our Alloy→Mimir pipeline
        network_queries = []
        
        for host_pattern in target_hosts:
            queries = [
                # Our exported network metrics
                f'avg_over_time(network_icmp_ping_duration_seconds{{target=~"{host_pattern}"}}[5m])',
                f'avg_over_time(network_packet_loss_ratio{{target=~"{host_pattern}"}}[5m])',
                f'avg_over_time(network_jitter_seconds{{target=~"{host_pattern}"}}[5m])',
                f'avg_over_time(network_mos_score{{target=~"{host_pattern}"}}[5m])',
                f'avg_over_time(network_tcp_handshake_duration_seconds{{target=~"{host_pattern}"}}[5m])',
                f'avg_over_time(network_dns_resolution_duration_seconds{{target=~"{host_pattern}"}}[5m])',
                f'avg_over_time(network_http_response_duration_seconds{{target=~"{host_pattern}"}}[5m])',
                f'rate(network_connection_errors_total{{target=~"{host_pattern}"}}[5m])',
                f'avg_over_time(network_interface_utilization_ratio{{interface=~".*"}}[5m])'
            ]
            network_queries.extend(queries)
        
        return await self.create_baseline_from_history(network_queries, days_back)
    
    async def test_connectivity(self) -> Dict[str, Any]:
        """Test connectivity to Mimir"""
        
        test_results = {}
        
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
        else:
            test_results['mimir'] = {
                'status': 'not_configured',
                'error': 'Mimir URL not provided'
            }
        
        return test_results

# Utility functions for integration

async def create_mimir_client(config: Dict[str, Any]) -> MimirClient:
    """Create and initialize Mimir client"""
    
    client = MimirClient(config)
    await client.initialize()
    return client

async def integrate_with_existing_detector(detector, mimir_client: MimirClient,
                                         target_hosts: List[str] = None, days_back: int = 30):
    """Integrate Mimir baselines with existing anomaly detector"""
    
    try:
        # Get historical baselines
        logger.info("Fetching historical baselines from Mimir...")
        baselines = await mimir_client.get_network_metrics_baselines(target_hosts, days_back)
        
        if not baselines:
            logger.warning("No baselines retrieved from Mimir")
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

#!/usr/bin/env python3
"""
Database Management
==================

SQLite database management for the Network Intelligence Monitor.
Handles metrics storage, anomaly tracking, and data lifecycle management.
"""

import aiosqlite
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Database:
    """Async SQLite database manager"""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db = None
        
        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
    async def initialize(self):
        """Initialize database connection and create tables"""
        
        try:
            self.db = await aiosqlite.connect(str(self.db_path))
            
            # Enable WAL mode for better concurrency
            await self.db.execute("PRAGMA journal_mode=WAL")
            await self.db.execute("PRAGMA synchronous=NORMAL")
            await self.db.execute("PRAGMA cache_size=10000")
            await self.db.execute("PRAGMA foreign_keys=ON")
            
            await self._create_tables()
            await self._create_indexes()
            
            logger.info(f"Database initialized: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def close(self):
        """Close database connection"""
        if self.db:
            await self.db.close()
            logger.info("Database connection closed")
    
    async def _create_tables(self):
        """Create database tables"""
        
        # Core metrics table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                target_host TEXT NOT NULL,
                tcp_handshake_time REAL,
                icmp_ping_time REAL,
                dns_resolve_time REAL,
                packet_loss REAL,
                jitter REAL,
                bandwidth_test REAL,
                connection_errors INTEGER DEFAULT 0,
                dns_errors INTEGER DEFAULT 0,
                timeout_errors INTEGER DEFAULT 0,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        
        # Enhanced metrics table (from system integration)
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS enhanced_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                target_host TEXT,
                
                -- Enhanced latency metrics
                tcp_connect_time REAL,
                tcp_ssl_handshake_time REAL,
                http_response_time REAL,
                http_first_byte_time REAL,
                
                -- Quality metrics
                burst_loss_rate REAL,
                out_of_order_packets REAL,
                duplicate_packets REAL,
                delay_variation REAL,
                
                -- Throughput metrics
                bandwidth_download REAL,
                bandwidth_upload REAL,
                concurrent_connections INTEGER,
                connection_setup_rate REAL,
                
                -- Application metrics
                http_status_code INTEGER,
                http_content_length INTEGER,
                certificate_days_remaining INTEGER,
                redirect_count INTEGER,
                
                -- Interface metrics
                interface_utilization REAL,
                interface_errors INTEGER,
                interface_drops INTEGER,
                interface_collisions INTEGER,
                
                -- Path metrics
                hop_count INTEGER,
                path_mtu INTEGER,
                route_changes INTEGER,
                
                -- Quality scores
                mos_score REAL,
                r_factor REAL,
                
                -- Metadata
                source_interface TEXT,
                network_type TEXT,
                measurement_duration REAL,
                
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        
        # Anomalies table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                target_host TEXT,
                anomaly_score REAL NOT NULL,
                confidence REAL NOT NULL,
                is_critical BOOLEAN DEFAULT 0,
                baseline_values TEXT,
                thresholds TEXT,
                feature_scores TEXT,
                recommendation TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        
        # AI model performance tracking
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS ai_model_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                model_type TEXT,
                accuracy REAL,
                precision REAL,
                recall REAL,
                f1_score REAL,
                training_samples INTEGER,
                inference_time_ms REAL,
                memory_usage_mb REAL,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        
        # Baseline tracking
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS baseline_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                metric_name TEXT,
                baseline_type TEXT,
                old_value REAL,
                new_value REAL,
                confidence REAL,
                source TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        
        # Alert history
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                alert_type TEXT,
                severity TEXT,
                target_host TEXT,
                message TEXT,
                acknowledged BOOLEAN DEFAULT 0,
                acknowledged_at REAL,
                resolved BOOLEAN DEFAULT 0,
                resolved_at REAL,
                metadata TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        
        # System health tracking
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS system_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                cpu_percent REAL,
                memory_percent REAL,
                disk_percent REAL,
                load_average REAL,
                active_connections INTEGER,
                component_status TEXT,
                health_score REAL,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        
        await self.db.commit()
        logger.info("Database tables created")
    
    async def _create_indexes(self):
        """Create database indexes for performance"""
        
        indexes = [
            # Core metrics indexes
            "CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_metrics_target ON metrics(target_host)",
            "CREATE INDEX IF NOT EXISTS idx_metrics_target_time ON metrics(target_host, timestamp)",
            
            # Enhanced metrics indexes
            "CREATE INDEX IF NOT EXISTS idx_enhanced_metrics_timestamp ON enhanced_metrics(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_enhanced_metrics_target ON enhanced_metrics(target_host)",
            
            # Anomalies indexes
            "CREATE INDEX IF NOT EXISTS idx_anomalies_timestamp ON anomalies(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_anomalies_target ON anomalies(target_host)",
            "CREATE INDEX IF NOT EXISTS idx_anomalies_critical ON anomalies(is_critical)",
            
            # AI performance indexes
            "CREATE INDEX IF NOT EXISTS idx_ai_performance_timestamp ON ai_model_performance(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_ai_performance_type ON ai_model_performance(model_type)",
            
            # Baseline indexes
            "CREATE INDEX IF NOT EXISTS idx_baseline_updates_timestamp ON baseline_updates(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_baseline_updates_metric ON baseline_updates(metric_name)",
            
            # Alert history indexes
            "CREATE INDEX IF NOT EXISTS idx_alert_history_timestamp ON alert_history(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_alert_history_target ON alert_history(target_host)",
            "CREATE INDEX IF NOT EXISTS idx_alert_history_severity ON alert_history(severity)",
            
            # System health indexes
            "CREATE INDEX IF NOT EXISTS idx_system_health_timestamp ON system_health(timestamp)"
        ]
        
        for index_sql in indexes:
            await self.db.execute(index_sql)
        
        await self.db.commit()
        logger.info("Database indexes created")
    
    async def store_metrics(self, metrics: Dict[str, Any]) -> bool:
        """Store network metrics"""
        
        try:
            # Determine if this is enhanced metrics
            is_enhanced = any(key in metrics for key in [
                'tcp_connect_time', 'http_response_time', 'mos_score'
            ])
            
            if is_enhanced:
                await self._store_enhanced_metrics(metrics)
            else:
                await self._store_basic_metrics(metrics)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store metrics: {e}")
            return False
    
    async def _store_basic_metrics(self, metrics: Dict[str, Any]):
        """Store basic metrics"""
        
        await self.db.execute("""
            INSERT INTO metrics (
                timestamp, target_host, tcp_handshake_time, icmp_ping_time,
                dns_resolve_time, packet_loss, jitter, bandwidth_test,
                connection_errors, dns_errors, timeout_errors
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metrics.get('timestamp', time.time()),
            metrics.get('target_host', 'unknown'),
            metrics.get('tcp_handshake_time', 0),
            metrics.get('icmp_ping_time', 0),
            metrics.get('dns_resolve_time', 0),
            metrics.get('packet_loss', 0),
            metrics.get('jitter', 0),
            metrics.get('bandwidth_test', 0),
            metrics.get('connection_errors', 0),
            metrics.get('dns_errors', 0),
            metrics.get('timeout_errors', 0)
        ))
        
        await self.db.commit()
    
    async def _store_enhanced_metrics(self, metrics: Dict[str, Any]):
        """Store enhanced metrics"""
        
        # Prepare all enhanced metric fields
        fields = [
            'timestamp', 'target_host', 'tcp_connect_time', 'tcp_ssl_handshake_time',
            'http_response_time', 'http_first_byte_time', 'burst_loss_rate',
            'out_of_order_packets', 'duplicate_packets', 'delay_variation',
            'bandwidth_download', 'bandwidth_upload', 'concurrent_connections',
            'connection_setup_rate', 'http_status_code', 'http_content_length',
            'certificate_days_remaining', 'redirect_count', 'interface_utilization',
            'interface_errors', 'interface_drops', 'interface_collisions',
            'hop_count', 'path_mtu', 'route_changes', 'mos_score', 'r_factor',
            'source_interface', 'network_type', 'measurement_duration'
        ]
        
        values = []
        for field in fields:
            if field == 'timestamp' and field not in metrics:
                values.append(time.time())
            else:
                values.append(metrics.get(field, None))
        
        placeholders = ', '.join(['?' for _ in fields])
        field_names = ', '.join(fields)
        
        await self.db.execute(
            f"INSERT INTO enhanced_metrics ({field_names}) VALUES ({placeholders})",
            values
        )
        
        await self.db.commit()
    
    async def store_anomaly(self, timestamp: float, anomaly_data: Dict[str, Any]) -> bool:
        """Store anomaly detection result"""
        
        try:
            await self.db.execute("""
                INSERT INTO anomalies (
                    timestamp, target_host, anomaly_score, confidence, is_critical,
                    baseline_values, thresholds, feature_scores, recommendation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                anomaly_data.get('target_host', 'unknown'),
                anomaly_data.get('anomaly_score', 0),
                anomaly_data.get('confidence', 0),
                anomaly_data.get('severity', 'low') in ['critical', 'high'],
                json.dumps(anomaly_data.get('baseline_values', {})),
                json.dumps(anomaly_data.get('thresholds', {})),
                json.dumps(anomaly_data.get('feature_contributions', {})),
                anomaly_data.get('recommendation', 'No recommendation')
            ))
            
            await self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to store anomaly: {e}")
            return False
    
    async def get_recent_metrics(self, target_host: str = None, 
                                hours: int = 24, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get recent metrics"""
        
        cutoff_time = time.time() - (hours * 3600)
        
        if target_host:
            query = """
                SELECT * FROM enhanced_metrics 
                WHERE target_host = ? AND timestamp > ? 
                ORDER BY timestamp DESC LIMIT ?
            """
            params = (target_host, cutoff_time, limit)
        else:
            query = """
                SELECT * FROM enhanced_metrics 
                WHERE timestamp > ? 
                ORDER BY timestamp DESC LIMIT ?
            """
            params = (cutoff_time, limit)
        
        try:
            async with self.db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                
                # Convert rows to dictionaries
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get recent metrics: {e}")
            return []
    
    async def get_recent_anomalies(self, target_host: str = None, 
                                  hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent anomalies"""
        
        cutoff_time = time.time() - (hours * 3600)
        
        if target_host:
            query = """
                SELECT * FROM anomalies 
                WHERE target_host = ? AND timestamp > ? 
                ORDER BY timestamp DESC LIMIT ?
            """
            params = (target_host, cutoff_time, limit)
        else:
            query = """
                SELECT * FROM anomalies 
                WHERE timestamp > ? 
                ORDER BY timestamp DESC LIMIT ?
            """
            params = (cutoff_time, limit)
        
        try:
            async with self.db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                
                anomalies = []
                for row in rows:
                    anomaly = dict(zip(columns, row))
                    
                    # Parse JSON fields
                    for json_field in ['baseline_values', 'thresholds', 'feature_scores']:
                        if anomaly.get(json_field):
                            try:
                                anomaly[json_field] = json.loads(anomaly[json_field])
                            except json.JSONDecodeError:
                                anomaly[json_field] = {}
                    
                    anomalies.append(anomaly)
                
                return anomalies
                
        except Exception as e:
            logger.error(f"Failed to get recent anomalies: {e}")
            return []
    
    async def get_metrics_for_training(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get metrics data for AI training"""
        
        cutoff_time = time.time() - (hours * 3600)
        
        query = """
            SELECT * FROM enhanced_metrics 
            WHERE timestamp > ? 
            ORDER BY timestamp ASC
        """
        
        try:
            async with self.db.execute(query, (cutoff_time,)) as cursor:
                rows = await cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get training data: {e}")
            return []
    
    async def store_ai_performance(self, performance_data: Dict[str, Any]) -> bool:
        """Store AI model performance metrics"""
        
        try:
            await self.db.execute("""
                INSERT INTO ai_model_performance (
                    timestamp, model_type, accuracy, precision, recall, f1_score,
                    training_samples, inference_time_ms, memory_usage_mb
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                performance_data.get('timestamp', time.time()),
                performance_data.get('model_type', 'unknown'),
                performance_data.get('accuracy'),
                performance_data.get('precision'),
                performance_data.get('recall'),
                performance_data.get('f1_score'),
                performance_data.get('training_samples'),
                performance_data.get('inference_time_ms'),
                performance_data.get('memory_usage_mb')
            ))
            
            await self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to store AI performance: {e}")
            return False
    
    async def store_baseline_update(self, update_data: Dict[str, Any]) -> bool:
        """Store baseline update"""
        
        try:
            await self.db.execute("""
                INSERT INTO baseline_updates (
                    timestamp, metric_name, baseline_type, old_value, 
                    new_value, confidence, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                update_data.get('timestamp', time.time()),
                update_data.get('metric_name'),
                update_data.get('baseline_type'),
                update_data.get('old_value'),
                update_data.get('new_value'),
                update_data.get('confidence'),
                update_data.get('source', 'unknown')
            ))
            
            await self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to store baseline update: {e}")
            return False
    
    async def cleanup_old_data(self, days: int = 30) -> Dict[str, int]:
        """Clean up old data from database"""
        
        cutoff_time = time.time() - (days * 24 * 3600)
        cleanup_stats = {}
        
        tables_to_cleanup = [
            'metrics', 'enhanced_metrics', 'anomalies', 
            'ai_model_performance', 'baseline_updates', 
            'alert_history', 'system_health'
        ]
        
        try:
            for table in tables_to_cleanup:
                cursor = await self.db.execute(
                    f"DELETE FROM {table} WHERE timestamp < ?", 
                    (cutoff_time,)
                )
                cleanup_stats[table] = cursor.rowcount
            
            await self.db.commit()
            
            # VACUUM to reclaim space
            await self.db.execute("VACUUM")
            
            total_deleted = sum(cleanup_stats.values())
            logger.info(f"Cleaned up {total_deleted} old records from database")
            
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return {}
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        
        stats = {}
        
        try:
            # Get table counts
            tables = [
                'metrics', 'enhanced_metrics', 'anomalies', 
                'ai_model_performance', 'baseline_updates'
            ]
            
            for table in tables:
                async with self.db.execute(f"SELECT COUNT(*) FROM {table}") as cursor:
                    count = await cursor.fetchone()
                    stats[f"{table}_count"] = count[0] if count else 0
            
            # Get database size
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
            stats['database_size_mb'] = db_size / (1024 * 1024)
            
            # Get recent activity
            cutoff_time = time.time() - 3600  # Last hour
            
            async with self.db.execute(
                "SELECT COUNT(*) FROM enhanced_metrics WHERE timestamp > ?", 
                (cutoff_time,)
            ) as cursor:
                recent_metrics = await cursor.fetchone()
                stats['recent_metrics_count'] = recent_metrics[0] if recent_metrics else 0
            
            async with self.db.execute(
                "SELECT COUNT(*) FROM anomalies WHERE timestamp > ?", 
                (cutoff_time,)
            ) as cursor:
                recent_anomalies = await cursor.fetchone()
                stats['recent_anomalies_count'] = recent_anomalies[0] if recent_anomalies else 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}
    
    async def backup_database(self, backup_path: str) -> bool:
        """Create database backup"""
        
        try:
            backup_path = Path(backup_path)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create backup using SQLite backup API
            backup_db = await aiosqlite.connect(str(backup_path))
            await self.db.backup(backup_db)
            await backup_db.close()
            
            logger.info(f"Database backup created: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create database backup: {e}")
            return False
    
    async def get_health_summary(self) -> Dict[str, Any]:
        """Get database health summary"""
        
        try:
            # Get recent metrics count
            recent_time = time.time() - 3600
            async with self.db.execute(
                "SELECT COUNT(*) FROM enhanced_metrics WHERE timestamp > ?",
                (recent_time,)
            ) as cursor:
                recent_count = (await cursor.fetchone())[0]
            
            # Get anomaly rate
            async with self.db.execute(
                "SELECT COUNT(*) FROM anomalies WHERE timestamp > ?",
                (recent_time,)
            ) as cursor:
                anomaly_count = (await cursor.fetchone())[0]
            
            # Calculate anomaly rate
            anomaly_rate = (anomaly_count / max(1, recent_count)) * 100
            
            # Get database performance
            stats = await self.get_database_stats()
            
            return {
                'status': 'healthy',
                'recent_metrics': recent_count,
                'anomaly_rate_percent': anomaly_rate,
                'database_size_mb': stats.get('database_size_mb', 0),
                'total_records': sum(v for k, v in stats.items() if k.endswith('_count')),
                'last_updated': time.time()
            }
            
        except Exception as e:
            logger.error(f"Failed to get health summary: {e}")
            return {'status': 'error', 'error': str(e)}

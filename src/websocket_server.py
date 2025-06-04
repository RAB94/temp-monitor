#!/usr/bin/env python3
"""
WebSocket Server for Real-time Updates
======================================

WebSocket server to push real-time metrics, anomalies, and alerts to clients.
Supports multiple channels and efficient data streaming.
"""

import asyncio
import websockets
import json
import logging
import time
import threading
from typing import Dict, List, Set, Any, Optional
from dataclasses import asdict
from datetime import datetime
import weakref

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manages WebSocket connections and real-time data streaming"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8001):
        self.host = host
        self.port = port
        self.clients: Dict[str, Set[websockets.WebSocketServerProtocol]] = {
            'metrics': set(),
            'anomalies': set(),
            'alerts': set(),
            'health': set(),
            'all': set()
        }
        
        # Message queues for different channels
        self.message_queues: Dict[str, asyncio.Queue] = {
            'metrics': asyncio.Queue(maxsize=100),
            'anomalies': asyncio.Queue(maxsize=50),
            'alerts': asyncio.Queue(maxsize=50),
            'health': asyncio.Queue(maxsize=20)
        }
        
        # Server state
        self.server = None
        self.running = False
        self.stats = {
            'connections_total': 0,
            'messages_sent': 0,
            'errors': 0,
            'start_time': time.time()
        }
        
        # Background tasks
        self.broadcaster_tasks = []
    
    async def start_server(self):
        """Start the WebSocket server"""
        
        if self.running:
            logger.warning("WebSocket server already running")
            return
        
        try:
            self.server = await websockets.serve(
                self.handle_client,
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            self.running = True
            
            # Start broadcaster tasks
            for channel in self.message_queues.keys():
                task = asyncio.create_task(self._broadcast_channel_messages(channel))
                self.broadcaster_tasks.append(task)
            
            # Start health monitoring
            health_task = asyncio.create_task(self._send_periodic_health())
            self.broadcaster_tasks.append(health_task)
            
            logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            raise
    
    async def stop_server(self):
        """Stop the WebSocket server"""
        
        if not self.running:
            return
        
        self.running = False
        
        # Cancel broadcaster tasks
        for task in self.broadcaster_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self.broadcaster_tasks:
            await asyncio.gather(*self.broadcaster_tasks, return_exceptions=True)
        
        # Close all client connections
        all_clients = set()
        for client_set in self.clients.values():
            all_clients.update(client_set)
        
        if all_clients:
            await asyncio.gather(
                *[client.close() for client in all_clients],
                return_exceptions=True
            )
        
        # Stop server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("WebSocket server stopped")
    
    async def handle_client(self, websocket, path):
        """Handle new WebSocket client connection"""
        
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"New WebSocket client connected: {client_id}")
        
        self.stats['connections_total'] += 1
        
        try:
            # Parse path to determine subscriptions
            subscriptions = self._parse_subscriptions(path)
            
            # Add client to appropriate channels
            for channel in subscriptions:
                if channel in self.clients:
                    self.clients[channel].add(websocket)
            
            self.clients['all'].add(websocket)
            
            # Send welcome message
            welcome_message = {
                'type': 'welcome',
                'timestamp': time.time(),
                'subscriptions': subscriptions,
                'server_info': {
                    'version': '1.0.0',
                    'uptime': time.time() - self.stats['start_time'],
                    'available_channels': list(self.clients.keys())
                }
            }
            
            await websocket.send(json.dumps(welcome_message))
            
            # Keep connection alive and handle messages
            await self._handle_client_messages(websocket, subscriptions)
            
        except websockets.exceptions.ConnectionClosed:
            logger.debug(f"Client {client_id} disconnected")
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
            self.stats['errors'] += 1
        finally:
            # Remove client from all channels
            for client_set in self.clients.values():
                client_set.discard(websocket)
            
            logger.debug(f"Client {client_id} cleanup completed")
    
    def _parse_subscriptions(self, path: str) -> List[str]:
        """Parse WebSocket path to determine channel subscriptions"""
        
        # Default subscriptions
        subscriptions = ['metrics', 'anomalies', 'health']
        
        if path and path != '/':
            # Parse path like /ws/metrics,anomalies or /ws/all
            path_parts = path.strip('/').split('/')
            if len(path_parts) >= 2:
                channels = path_parts[1].split(',')
                
                # Validate channels
                valid_channels = []
                for channel in channels:
                    channel = channel.strip()
                    if channel == 'all':
                        return list(self.clients.keys())[:-1]  # All except 'all'
                    elif channel in self.clients:
                        valid_channels.append(channel)
                
                if valid_channels:
                    subscriptions = valid_channels
        
        return subscriptions
    
    async def _handle_client_messages(self, websocket, subscriptions: List[str]):
        """Handle incoming messages from client"""
        
        async for message in websocket:
            try:
                data = json.loads(message)
                await self._process_client_message(websocket, data, subscriptions)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    'type': 'error',
                    'message': 'Invalid JSON message'
                }))
            except Exception as e:
                logger.error(f"Error processing client message: {e}")
    
    async def _process_client_message(self, websocket, data: Dict[str, Any], subscriptions: List[str]):
        """Process message from client"""
        
        message_type = data.get('type')
        
        if message_type == 'subscribe':
            # Handle subscription changes
            new_channels = data.get('channels', [])
            
            # Remove from old channels
            for channel in subscriptions:
                if channel in self.clients:
                    self.clients[channel].discard(websocket)
            
            # Add to new channels
            subscriptions.clear()
            for channel in new_channels:
                if channel in self.clients:
                    self.clients[channel].add(websocket)
                    subscriptions.append(channel)
            
            await websocket.send(json.dumps({
                'type': 'subscription_updated',
                'subscriptions': subscriptions
            }))
        
        elif message_type == 'ping':
            # Respond to ping
            await websocket.send(json.dumps({
                'type': 'pong',
                'timestamp': time.time()
            }))
        
        elif message_type == 'get_stats':
            # Send server statistics
            await websocket.send(json.dumps({
                'type': 'stats',
                'data': self.get_server_stats()
            }))
    
    async def _broadcast_channel_messages(self, channel: str):
        """Broadcast messages for a specific channel"""
        
        while self.running:
            try:
                # Wait for message with timeout
                message = await asyncio.wait_for(
                    self.message_queues[channel].get(),
                    timeout=1.0
                )
                
                # Get clients for this channel
                clients = self.clients.get(channel, set()).copy()
                
                if clients:
                    # Prepare message
                    websocket_message = json.dumps({
                        'type': 'data',
                        'channel': channel,
                        'timestamp': time.time(),
                        'data': message
                    })
                    
                    # Send to all clients (with error handling)
                    await self._send_to_clients(clients, websocket_message)
                    
                    self.stats['messages_sent'] += len(clients)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error broadcasting to channel {channel}: {e}")
                await asyncio.sleep(1)
    
    async def _send_to_clients(self, clients: Set[websockets.WebSocketServerProtocol], message: str):
        """Send message to a set of clients with error handling"""
        
        if not clients:
            return
        
        # Send to all clients concurrently
        tasks = []
        for client in clients:
            tasks.append(self._send_to_client(client, message))
        
        # Wait for all sends to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Remove failed clients
        failed_clients = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_clients.append(list(clients)[i])
        
        # Clean up failed clients
        for client in failed_clients:
            for client_set in self.clients.values():
                client_set.discard(client)
    
    async def _send_to_client(self, client: websockets.WebSocketServerProtocol, message: str):
        """Send message to a single client"""
        
        try:
            await client.send(message)
        except websockets.exceptions.ConnectionClosed:
            raise  # Will be handled by caller
        except Exception as e:
            logger.debug(f"Failed to send to client: {e}")
            raise
    
    async def _send_periodic_health(self):
        """Send periodic health updates"""
        
        while self.running:
            try:
                health_data = {
                    'server_stats': self.get_server_stats(),
                    'active_connections': {
                        channel: len(clients) 
                        for channel, clients in self.clients.items()
                    },
                    'timestamp': time.time()
                }
                
                await self.send_health_update(health_data)
                
                # Wait 30 seconds
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error sending periodic health: {e}")
                await asyncio.sleep(30)
    
    # Public methods for sending data
    
    async def send_metrics_update(self, metrics_data: Dict[str, Any]):
        """Send metrics update to subscribed clients"""
        
        try:
            await self.message_queues['metrics'].put(metrics_data)
        except asyncio.QueueFull:
            logger.warning("Metrics queue full, dropping message")
    
    async def send_anomaly_alert(self, anomaly_data: Dict[str, Any]):
        """Send anomaly alert to subscribed clients"""
        
        try:
            await self.message_queues['anomalies'].put(anomaly_data)
        except asyncio.QueueFull:
            logger.warning("Anomalies queue full, dropping message")
    
    async def send_alert_notification(self, alert_data: Dict[str, Any]):
        """Send alert notification to subscribed clients"""
        
        try:
            await self.message_queues['alerts'].put(alert_data)
        except asyncio.QueueFull:
            logger.warning("Alerts queue full, dropping message")
    
    async def send_health_update(self, health_data: Dict[str, Any]):
        """Send health update to subscribed clients"""
        
        try:
            await self.message_queues['health'].put(health_data)
        except asyncio.QueueFull:
            logger.warning("Health queue full, dropping message")
    
    def get_server_stats(self) -> Dict[str, Any]:
        """Get WebSocket server statistics"""
        
        return {
            'uptime_seconds': time.time() - self.stats['start_time'],
            'total_connections': self.stats['connections_total'],
            'active_connections': sum(len(clients) for clients in self.clients.values()) - len(self.clients['all']),
            'messages_sent': self.stats['messages_sent'],
            'errors': self.stats['errors'],
            'queue_sizes': {
                channel: queue.qsize() 
                for channel, queue in self.message_queues.items()
            }
        }
    
    def get_client_count(self, channel: str = 'all') -> int:
        """Get number of connected clients for a channel"""
        
        return len(self.clients.get(channel, set()))

class WebSocketIntegration:
    """Integration layer for WebSocket with monitoring system"""
    
    def __init__(self, websocket_manager: WebSocketManager):
        self.ws_manager = websocket_manager
        self.integration_stats = {
            'metrics_sent': 0,
            'anomalies_sent': 0,
            'alerts_sent': 0
        }
    
    async def on_metrics_collected(self, metrics):
        """Handle metrics collection event"""
        
        try:
            # Convert metrics to WebSocket format
            metrics_data = self._format_metrics_for_websocket(metrics)
            
            await self.ws_manager.send_metrics_update(metrics_data)
            self.integration_stats['metrics_sent'] += 1
            
        except Exception as e:
            logger.error(f"Error sending metrics via WebSocket: {e}")
    
    async def on_anomaly_detected(self, anomaly_result, target: str):
        """Handle anomaly detection event"""
        
        try:
            anomaly_data = {
                'target': target,
                'anomaly_score': anomaly_result.anomaly_score,
                'confidence': anomaly_result.confidence,
                'severity': anomaly_result.severity,
                'recommendation': anomaly_result.recommendation,
                'feature_contributions': anomaly_result.feature_contributions,
                'temporal_pattern': anomaly_result.temporal_pattern,
                'timestamp': time.time()
            }
            
            await self.ws_manager.send_anomaly_alert(anomaly_data)
            self.integration_stats['anomalies_sent'] += 1
            
        except Exception as e:
            logger.error(f"Error sending anomaly via WebSocket: {e}")
    
    async def on_alert_created(self, alert):
        """Handle alert creation event"""
        
        try:
            alert_data = {
                'id': alert.id,
                'title': alert.title,
                'description': alert.description,
                'severity': alert.severity.value,
                'target': alert.target,
                'metric_name': alert.metric_name,
                'current_value': alert.current_value,
                'threshold': alert.threshold,
                'created_at': alert.created_at,
                'timestamp': time.time()
            }
            
            await self.ws_manager.send_alert_notification(alert_data)
            self.integration_stats['alerts_sent'] += 1
            
        except Exception as e:
            logger.error(f"Error sending alert via WebSocket: {e}")
    
    def _format_metrics_for_websocket(self, metrics) -> Dict[str, Any]:
        """Format metrics for WebSocket transmission"""
        
        if hasattr(metrics, 'to_dict'):
            metrics_dict = metrics.to_dict()
        else:
            metrics_dict = metrics
        
        # Create summary for efficient transmission
        summary = {
            'target': metrics_dict.get('target_host', 'unknown'),
            'timestamp': metrics_dict.get('timestamp', time.time()),
            'key_metrics': {
                'latency': metrics_dict.get('icmp_ping_time', 0),
                'packet_loss': metrics_dict.get('packet_loss', 0),
                'jitter': metrics_dict.get('jitter', 0),
                'mos_score': metrics_dict.get('mos_score', 0),
                'bandwidth_download': metrics_dict.get('bandwidth_download', 0),
                'connection_errors': metrics_dict.get('connection_errors', 0)
            },
            'quality_score': self._calculate_quality_score(metrics_dict),
            'status': self._determine_connection_status(metrics_dict)
        }
        
        return summary
    
    def _calculate_quality_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate overall quality score"""
        
        score = 100.0
        
        # Latency impact
        latency = metrics.get('icmp_ping_time', 0)
        if latency > 0:
            if latency > 200:
                score -= 30
            elif latency > 100:
                score -= 20
            elif latency > 50:
                score -= 10
        
        # Packet loss impact
        packet_loss = metrics.get('packet_loss', 0)
        score -= packet_loss * 10  # 10 points per percent loss
        
        # Jitter impact
        jitter = metrics.get('jitter', 0)
        if jitter > 20:
            score -= 15
        elif jitter > 10:
            score -= 10
        elif jitter > 5:
            score -= 5
        
        # Connection errors impact
        errors = metrics.get('connection_errors', 0)
        score -= errors * 5
        
        return max(0, min(100, score))
    
    def _determine_connection_status(self, metrics: Dict[str, Any]) -> str:
        """Determine connection status"""
        
        if metrics.get('connection_errors', 0) > 0:
            return 'error'
        elif metrics.get('icmp_ping_time', 0) <= 0:
            return 'down'
        elif metrics.get('packet_loss', 0) > 5:
            return 'degraded'
        elif metrics.get('icmp_ping_time', 0) > 200:
            return 'slow'
        else:
            return 'healthy'
    
    def get_integration_stats(self) -> Dict[str, Any]:
        """Get integration statistics"""
        
        return {
            'metrics_sent': self.integration_stats['metrics_sent'],
            'anomalies_sent': self.integration_stats['anomalies_sent'],
            'alerts_sent': self.integration_stats['alerts_sent'],
            'websocket_stats': self.ws_manager.get_server_stats()
        }

# Utility functions

async def create_websocket_server(host: str = "0.0.0.0", port: int = 8001) -> WebSocketManager:
    """Create and start WebSocket server"""
    
    ws_manager = WebSocketManager(host, port)
    await ws_manager.start_server()
    return ws_manager

def integrate_websocket_with_monitor(monitor, ws_manager: WebSocketManager):
    """Integrate WebSocket with monitoring system"""
    
    integration = WebSocketIntegration(ws_manager)
    
    # Hook into monitor events (this would need to be implemented in the monitor)
    if hasattr(monitor, 'add_metrics_callback'):
        monitor.add_metrics_callback(integration.on_metrics_collected)
    
    if hasattr(monitor, 'add_anomaly_callback'):
        monitor.add_anomaly_callback(integration.on_anomaly_detected)
    
    if hasattr(monitor, 'add_alert_callback'):
        monitor.add_alert_callback(integration.on_alert_created)
    
    return integration

# Example WebSocket client for testing
class WebSocketTestClient:
    """Test client for WebSocket functionality"""
    
    def __init__(self, uri: str = "ws://localhost:8001/ws/all"):
        self.uri = uri
        self.websocket = None
        self.running = False
        self.messages_received = 0
    
    async def connect(self):
        """Connect to WebSocket server"""
        
        try:
            self.websocket = await websockets.connect(self.uri)
            self.running = True
            logger.info(f"Connected to WebSocket server: {self.uri}")
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket server: {e}")
            raise
    
    async def listen(self):
        """Listen for messages from server"""
        
        try:
            async for message in self.websocket:
                data = json.loads(message)
                self.messages_received += 1
                
                print(f"Received: {data['type']}")
                if data['type'] == 'data':
                    print(f"  Channel: {data['channel']}")
                    print(f"  Data: {data['data']}")
                
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error in WebSocket client: {e}")
        finally:
            self.running = False
    
    async def send_ping(self):
        """Send ping to server"""
        
        if self.websocket:
            ping_message = json.dumps({
                'type': 'ping',
                'timestamp': time.time()
            })
            await self.websocket.send(ping_message)
    
    async def disconnect(self):
        """Disconnect from server"""
        
        self.running = False
        if self.websocket:
            await self.websocket.close()

# Example usage
async def test_websocket_server():
    """Test the WebSocket server functionality"""
    
    # Start server
    ws_manager = await create_websocket_server()
    
    try:
        # Simulate some data
        for i in range(10):
            await asyncio.sleep(2)
            
            # Send test metrics
            test_metrics = {
                'target': 'test.example.com',
                'timestamp': time.time(),
                'latency': 50 + i * 5,
                'packet_loss': i * 0.5,
                'jitter': i * 2
            }
            
            await ws_manager.send_metrics_update(test_metrics)
            
            if i % 3 == 0:
                # Send test anomaly
                test_anomaly = {
                    'target': 'test.example.com',
                    'anomaly_score': 0.8,
                    'severity': 'high',
                    'message': f'Test anomaly {i}'
                }
                
                await ws_manager.send_anomaly_alert(test_anomaly)
    
    finally:
        await ws_manager.stop_server()

if __name__ == "__main__":
    # Run test
    asyncio.run(test_websocket_server())

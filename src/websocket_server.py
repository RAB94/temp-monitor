#!/usr/bin/env python3
"""
WebSocket Server for Real-time Updates - Enhanced
==================================================

Enhanced WebSocket server with better error handling and HTTP fallback.
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
from websockets.exceptions import InvalidUpgrade, ConnectionClosedError, ConnectionClosedOK

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Enhanced WebSocket manager with better error handling"""
    
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
            'connections_active': 0,
            'messages_sent': 0,
            'errors': 0,
            'invalid_upgrades': 0,
            'start_time': time.time()
        }
        
        # Background tasks
        self.broadcaster_tasks = []
    
    async def start_server(self):
        """Start the WebSocket server with enhanced error handling"""
        
        if self.running:
            logger.warning("WebSocket server already running")
            return
        
        try:
            # Create server with custom request handler
            self.server = await websockets.serve(
                self.handle_client,  # This handler takes (websocket, path)
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10,
                process_request=self.process_request,  # Custom request processor
                logger=logging.getLogger('websockets.server')
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
            logger.info(f"WebSocket endpoint: ws://{self.host}:{self.port}/ws")
            logger.info(f"Available channels: {list(self.clients.keys())[:-1]}")
            
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            raise

    async def process_request(self, connection, request):
        """Process incoming request and provide helpful responses for non-WebSocket requests"""
        
        # Check if this is a WebSocket upgrade request
        upgrade_header = request.headers.get('Upgrade', '').lower()
        connection_header = request.headers.get('Connection', '').lower()
        
        if upgrade_header != 'websocket' or 'upgrade' not in connection_header:
            # This is not a WebSocket request
            self.stats['invalid_upgrades'] += 1
            
            # Log the attempt for debugging
            logger.warning(f"Non-WebSocket request to WebSocket endpoint from {connection.remote_address}: "
                         f"Path: {request.path}, Headers: Connection={connection_header}, Upgrade={upgrade_header}")
            
            # Return HTTP response with information
            response_body = self._create_info_page(request)
            
            return (
                400,  # Bad Request
                [
                    ('Content-Type', 'text/html'),
                    ('Content-Length', str(len(response_body))),
                    ('Cache-Control', 'no-cache'),
                ],
                response_body.encode()
            )
        
        # This is a valid WebSocket request, let it proceed
        return None
    
    def _create_info_page(self, request) -> str:
        """Create an informational HTML page for non-WebSocket requests"""
        
        # Extract request details safely
        try:
            request_method = getattr(request, 'method', 'GET')
            request_path = getattr(request, 'path', '/ws')
            user_agent = request.headers.get('User-Agent', 'Unknown') if hasattr(request, 'headers') else 'Unknown'
        except Exception:
            request_method = 'Unknown'
            request_path = '/ws'
            user_agent = 'Unknown'
        
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Server - Network Monitor</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
        .container {{ max-width: 800px; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; }}
        .info {{ background: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .error {{ background: #ffebee; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .code {{ background: #f5f5f5; padding: 10px; border-radius: 3px; font-family: monospace; }}
        .stats {{ background: #f0f8ff; padding: 15px; border-radius: 5px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Network Intelligence Monitor - WebSocket Server</h1>
        
        <div class="error">
            <h3>❌ WebSocket Connection Required</h3>
            <p>This endpoint requires a WebSocket connection. You attempted to access it with a regular HTTP request.</p>
        </div>
        
        <div class="info">
            <h3>📡 WebSocket Connection Information</h3>
            <ul>
                <li><strong>WebSocket URL:</strong> <code>ws://{self.host}:{self.port}/ws</code></li>
                <li><strong>Available Channels:</strong> {', '.join(list(self.clients.keys())[:-1])}</li>
                <li><strong>Protocol:</strong> WebSocket (RFC 6455)</li>
            </ul>
        </div>
        
        <div class="info">
            <h3>🔌 JavaScript Connection Example</h3>
            <div class="code">
const ws = new WebSocket('ws://{self.host}:{self.port}/ws/metrics');
ws.onopen = () => console.log('Connected');
ws.onmessage = (event) => console.log('Data:', JSON.parse(event.data));
            </div>
        </div>
        
        <div class="info">
            <h3>📊 Channel Subscriptions</h3>
            <ul>
                <li><code>/ws</code> - Default (metrics + health)</li>
                <li><code>/ws/all</code> - All channels</li>
                <li><code>/ws/metrics</code> - Network metrics only</li>
                <li><code>/ws/anomalies</code> - Anomaly alerts only</li>
                <li><code>/ws/alerts</code> - System alerts only</li>
                <li><code>/ws/health</code> - Health updates only</li>
                <li><code>/ws/metrics,alerts</code> - Multiple channels</li>
            </ul>
        </div>
        
        <div class="stats">
            <h3>📈 Server Statistics</h3>
            <ul>
                <li><strong>Uptime:</strong> {time.time() - self.stats['start_time']:.1f} seconds</li>
                <li><strong>Active Connections:</strong> {self.stats['connections_active']}</li>
                <li><strong>Total Connections:</strong> {self.stats['connections_total']}</li>
                <li><strong>Messages Sent:</strong> {self.stats['messages_sent']}</li>
                <li><strong>Invalid Upgrade Attempts:</strong> {self.stats['invalid_upgrades']}</li>
            </ul>
        </div>
        
        <div class="info">
            <h3>🛠️ Troubleshooting</h3>
            <p>If you're seeing this page unexpectedly:</p>
            <ul>
                <li>Ensure your client is using WebSocket protocol (ws://) not HTTP (http://)</li>
                <li>Check that WebSocket upgrade headers are being sent</li>
                <li>Verify there's no proxy stripping WebSocket headers</li>
                <li>Use browser developer tools to inspect the connection</li>
            </ul>
        </div>
        
        <p><small>Request details: {request_method} {request_path} from {user_agent}</small></p>
    </div>
</body>
</html>"""
    
    async def stop_server(self):
        """Stop the WebSocket server"""
        
        if not self.running:
            return
        
        logger.info("Stopping WebSocket server...")
        self.running = False
        
        # Cancel broadcaster tasks
        for task in self.broadcaster_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self.broadcaster_tasks:
            await asyncio.gather(*self.broadcaster_tasks, return_exceptions=True)
        
        # Close all client connections
        all_clients = set()
        for client_set in self.clients.values():
            all_clients.update(client_set)
        
        if all_clients:
            logger.info(f"Closing {len(all_clients)} active WebSocket connections...")
            close_tasks = []
            for client in all_clients:
                try:
                    close_tasks.append(client.close(1001, "Server shutting down"))
                except Exception:
                    pass
            
            if close_tasks:
                await asyncio.gather(*close_tasks, return_exceptions=True)
        
        # Stop server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("WebSocket server stopped")
    
    async def handle_client(self, websocket, path):
        """Handle new WebSocket client connection with correct signature"""
        
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"New WebSocket client connected: {client_id} (path: {path})")
        
        self.stats['connections_total'] += 1
        self.stats['connections_active'] += 1
        
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
                    'available_channels': list(self.clients.keys())[:-1]
                }
            }
            
            await websocket.send(json.dumps(welcome_message))
            logger.info(f"Client {client_id} subscribed to channels: {subscriptions}")
            
            # Keep connection alive and handle messages
            await self._handle_client_messages(websocket, subscriptions)
            
        except Exception as e:
            # Handle different types of disconnection
            from websockets.exceptions import ConnectionClosed
            
            if isinstance(e, ConnectionClosed):
                if e.code == 1000:  # Normal closure
                    logger.debug(f"Client {client_id} disconnected normally")
                else:
                    logger.info(f"Client {client_id} disconnected with code {e.code}: {e.reason}")
            else:
                logger.error(f"Error handling client {client_id}: {e}")
                self.stats['errors'] += 1
        finally:
            # Remove client from all channels
            for client_set in self.clients.values():
                client_set.discard(websocket)
            
            self.stats['connections_active'] -= 1
            logger.debug(f"Client {client_id} cleanup completed")

        def _parse_subscriptions(self, path: str) -> List[str]:
            """Parse WebSocket path to determine channel subscriptions"""
            
            # Default subscriptions
            subscriptions = ['metrics', 'health']
            
            if path and path != '/':
                # Remove leading slash and split path
                path_clean = path.lstrip('/')
                
                # Handle /ws prefix
                if path_clean.startswith('ws/'):
                    path_clean = path_clean[3:]  # Remove 'ws/' prefix
                elif path_clean == 'ws':
                    return subscriptions  # Default for /ws
                
                if path_clean:
                    channels = path_clean.split(',')
                    
                    # Validate channels
                    valid_channels = []
                    for channel in channels:
                        channel = channel.strip()
                        if channel == 'all':
                            return ['metrics', 'anomalies', 'alerts', 'health']
                        elif channel in self.clients and channel != 'all':
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
                error_msg = {'type': 'error', 'message': 'Invalid JSON message'}
                await self._safe_send(websocket, json.dumps(error_msg))
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
            
            response = {
                'type': 'subscription_updated',
                'subscriptions': subscriptions,
                'timestamp': time.time()
            }
            await self._safe_send(websocket, json.dumps(response))
        
        elif message_type == 'ping':
            # Respond to ping
            pong = {
                'type': 'pong',
                'timestamp': time.time()
            }
            await self._safe_send(websocket, json.dumps(pong))
        
        elif message_type == 'get_stats':
            # Send server statistics
            stats_response = {
                'type': 'stats',
                'data': self.get_server_stats(),
                'timestamp': time.time()
            }
            await self._safe_send(websocket, json.dumps(stats_response))
    
    async def _safe_send(self, websocket, message: str):
        """Safely send message to websocket with error handling"""
        try:
            await websocket.send(message)
        except ConnectionClosedError:
            # Connection already closed, ignore
            pass
        except Exception as e:
            logger.debug(f"Failed to send message to websocket: {e}")
    
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
        send_tasks = []
        for client in clients:
            send_tasks.append(self._safe_send(client, message))
        
        # Wait for all sends to complete
        await asyncio.gather(*send_tasks, return_exceptions=True)
    
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
            'active_connections': self.stats['connections_active'],
            'messages_sent': self.stats['messages_sent'],
            'errors': self.stats['errors'],
            'invalid_upgrades': self.stats['invalid_upgrades'],
            'queue_sizes': {
                channel: queue.qsize() 
                for channel, queue in self.message_queues.items()
            }
        }
    
    def get_client_count(self, channel: str = 'all') -> int:
        """Get number of connected clients for a channel"""
        return len(self.clients.get(channel, set()))

# Keep the WebSocketIntegration class unchanged
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
        
        return {
            'target': metrics_dict.get('target_host', 'unknown'),
            'timestamp': metrics_dict.get('timestamp', time.time()),
            'key_metrics': {
                'latency': metrics_dict.get('icmp_ping_time', 0),
                'packet_loss': metrics_dict.get('packet_loss', 0),
                'jitter': metrics_dict.get('jitter', 0),
                'mos_score': metrics_dict.get('mos_score', 0)
            }
        }

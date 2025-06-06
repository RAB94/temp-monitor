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
        
        self.message_queues: Dict[str, asyncio.Queue] = {
            'metrics': asyncio.Queue(maxsize=100),
            'anomalies': asyncio.Queue(maxsize=50),
            'alerts': asyncio.Queue(maxsize=50),
            'health': asyncio.Queue(maxsize=20)
        }
        
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
        
        self.broadcaster_tasks = []
    
    async def start_server(self):
        """Start the WebSocket server with enhanced error handling"""
        
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
                close_timeout=10,
                process_request=self.process_request,
                logger=logging.getLogger('websockets.server')
            )
            
            self.running = True
            
            for channel in self.message_queues.keys():
                task = asyncio.create_task(self._broadcast_channel_messages(channel))
                self.broadcaster_tasks.append(task)
            
            health_task = asyncio.create_task(self._send_periodic_health())
            self.broadcaster_tasks.append(health_task)
            
            logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")
            logger.info(f"WebSocket endpoint: ws://{self.host}:{self.port}/ws")
            logger.info(f"Available channels: {list(self.clients.keys())[:-1]}")
            
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            raise

    # FIX: Corrected the signature and logic for process_request
    async def process_request(self, path: str, request_headers: websockets.Headers):
        """Process incoming request and provide helpful responses for non-WebSocket requests"""
        
        upgrade_header = request_headers.get('Upgrade', '').lower()
        connection_header = request_headers.get('Connection', '').lower()
        
        if upgrade_header != 'websocket' or 'upgrade' not in connection_header:
            self.stats['invalid_upgrades'] += 1
            
            logger.warning(f"Non-WebSocket request to WebSocket endpoint: "
                         f"Path: {path}, Headers: Connection={connection_header}, Upgrade={upgrade_header}")
            
            response_body = self._create_info_page(path, request_headers)
            
            return (
                400,
                [
                    ('Content-Type', 'text/html'),
                    ('Content-Length', str(len(response_body))),
                    ('Cache-Control', 'no-cache'),
                ],
                response_body.encode()
            )
        
        return None
    
    # FIX: Corrected to use path and headers
    def _create_info_page(self, path: str, headers: websockets.Headers) -> str:
        """Create an informational HTML page for non-WebSocket requests"""
        
        user_agent = headers.get('User-Agent', 'Unknown')
        request_method = 'GET' # Assume GET for non-WS requests
        
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
            </ul>
        </div>
        <div class="stats">
            <h3>📈 Server Statistics</h3>
            <ul>
                <li><strong>Uptime:</strong> {time.time() - self.stats['start_time']:.1f} seconds</li>
                <li><strong>Active Connections:</strong> {self.stats['connections_active']}</li>
                <li><strong>Messages Sent:</strong> {self.stats['messages_sent']}</li>
            </ul>
        </div>
        <p><small>Request details: {request_method} {path} from {user_agent}</small></p>
    </div>
</body>
</html>"""
    
    async def stop_server(self):
        """Stop the WebSocket server"""
        
        if not self.running:
            return
        
        logger.info("Stopping WebSocket server...")
        self.running = False
        
        for task in self.broadcaster_tasks:
            if not task.done():
                task.cancel()
        
        if self.broadcaster_tasks:
            await asyncio.gather(*self.broadcaster_tasks, return_exceptions=True)
        
        all_clients = set().union(*self.clients.values())
        
        if all_clients:
            logger.info(f"Closing {len(all_clients)} active WebSocket connections...")
            await asyncio.gather(
                *(client.close(1001, "Server shutting down") for client in all_clients),
                return_exceptions=True
            )
        
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
            subscriptions = self._parse_subscriptions(path)
            
            for channel in subscriptions:
                if channel in self.clients:
                    self.clients[channel].add(websocket)
            
            self.clients['all'].add(websocket)
            
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
            
            await self._handle_client_messages(websocket, subscriptions)
            
        except ConnectionClosedOK:
            logger.debug(f"Client {client_id} disconnected normally")
        except ConnectionClosedError as e:
            logger.info(f"Client {client_id} disconnected with code {e.code}: {e.reason}")
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
            self.stats['errors'] += 1
        finally:
            for client_set in self.clients.values():
                client_set.discard(websocket)
            
            self.stats['connections_active'] -= 1
            logger.debug(f"Client {client_id} cleanup completed")

    def _parse_subscriptions(self, path: str) -> List[str]:
        """Parse WebSocket path to determine channel subscriptions"""
        
        subscriptions = ['metrics', 'health']
        
        if path and path != '/':
            path_clean = path.lstrip('/')
            if path_clean.startswith('ws/'):
                path_clean = path_clean[3:]
            elif path_clean == 'ws':
                return subscriptions
            
            if path_clean:
                channels = path_clean.split(',')
                valid_channels = []
                for channel in channels:
                    channel = channel.strip()
                    if channel == 'all':
                        return ['metrics', 'anomalies', 'alerts', 'health']
                    elif channel in self.clients and channel != 'all':
                        valid_channels.append(channel)
                
                if valid_channels:
                    subscriptions = list(set(valid_channels))
        
        return subscriptions
    
    async def _handle_client_messages(self, websocket, subscriptions: List[str]):
        """Handle incoming messages from client"""
        async for message in websocket:
            try:
                data = json.loads(message)
                await self._process_client_message(websocket, data, subscriptions)
            except json.JSONDecodeError:
                await self._safe_send(websocket, json.dumps({'type': 'error', 'message': 'Invalid JSON'}))
    
    async def _process_client_message(self, websocket, data: Dict[str, Any], subscriptions: List[str]):
        """Process message from client"""
        message_type = data.get('type')
        
        if message_type == 'ping':
            await self._safe_send(websocket, json.dumps({'type': 'pong', 'timestamp': time.time()}))
        elif message_type == 'get_stats':
            await self._safe_send(websocket, json.dumps({
                'type': 'stats',
                'data': self.get_server_stats(),
                'timestamp': time.time()
            }))
    
    async def _safe_send(self, websocket, message: str):
        """Safely send message to websocket"""
        try:
            await websocket.send(message)
        except ConnectionClosedError:
            pass
    
    async def _broadcast_channel_messages(self, channel: str):
        """Broadcast messages for a specific channel"""
        while self.running:
            try:
                message = await asyncio.wait_for(self.message_queues[channel].get(), timeout=1.0)
                clients = self.clients.get(channel, set()).copy()
                if clients:
                    websocket_message = json.dumps({
                        'type': 'data',
                        'channel': channel,
                        'timestamp': time.time(),
                        'data': message
                    })
                    await self._send_to_clients(clients, websocket_message)
                    self.stats['messages_sent'] += len(clients)
            except asyncio.TimeoutError:
                continue
    
    async def _send_to_clients(self, clients: Set[websockets.WebSocketServerProtocol], message: str):
        if clients:
            await asyncio.gather(*(self._safe_send(client, message) for client in clients), return_exceptions=True)
    
    async def _send_periodic_health(self):
        """Send periodic health updates"""
        while self.running:
            try:
                await self.send_health_update({
                    'server_stats': self.get_server_stats(),
                    'active_connections': {c: len(s) for c, s in self.clients.items()}
                })
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Error sending periodic health: {e}")
                await asyncio.sleep(30)
    
    async def send_metrics_update(self, metrics_data: Dict[str, Any]):
        await self._enqueue_message('metrics', metrics_data)
    
    async def send_anomaly_alert(self, anomaly_data: Dict[str, Any]):
        await self._enqueue_message('anomalies', anomaly_data)
    
    async def send_alert_notification(self, alert_data: Dict[str, Any]):
        await self._enqueue_message('alerts', alert_data)
    
    async def send_health_update(self, health_data: Dict[str, Any]):
        await self._enqueue_message('health', health_data)

    async def _enqueue_message(self, channel, data):
        try:
            await self.message_queues[channel].put(data)
        except asyncio.QueueFull:
            logger.warning(f"{channel.capitalize()} queue full, dropping message")
    
    def get_server_stats(self) -> Dict[str, Any]:
        """Get WebSocket server statistics"""
        return {
            'uptime_seconds': time.time() - self.stats['start_time'],
            'total_connections': self.stats['connections_total'],
            'active_connections': self.stats['connections_active'],
            'messages_sent': self.stats['messages_sent'],
            'errors': self.stats['errors'],
            'invalid_upgrades': self.stats['invalid_upgrades'],
            'queue_sizes': {c: q.qsize() for c, q in self.message_queues.items()}
        }

class WebSocketIntegration:
    """Integration layer for WebSocket with monitoring system"""
    
    def __init__(self, websocket_manager: WebSocketManager):
        self.ws_manager = websocket_manager
    
    async def on_metrics_collected(self, metrics):
        """Handle metrics collection event"""
        await self.ws_manager.send_metrics_update(self._format_metrics(metrics))
    
    async def on_anomaly_detected(self, anomaly_result, target: str):
        """Handle anomaly detection event"""
        await self.ws_manager.send_anomaly_alert({
            'target': target,
            'anomaly_score': getattr(anomaly_result, 'anomaly_score', 0),
            'severity': getattr(anomaly_result, 'severity', 'unknown'),
            'recommendation': getattr(anomaly_result, 'recommendation', '')
        })
    
    async def on_alert_created(self, alert):
        """Handle alert creation event"""
        await self.ws_manager.send_alert_notification({
            'id': alert.id,
            'title': alert.title,
            'severity': alert.severity.value,
        })
    
    def _format_metrics(self, metrics) -> Dict[str, Any]:
        """Format metrics for WebSocket"""
        metrics_dict = metrics.to_dict() if hasattr(metrics, 'to_dict') else metrics
        return {
            'target': metrics_dict.get('target_host', 'unknown'),
            'latency': metrics_dict.get('icmp_ping_time', 0),
            'packet_loss': metrics_dict.get('packet_loss', 0),
            'jitter': metrics_dict.get('jitter', 0),
            'mos_score': metrics_dict.get('mos_score', 0)
        }

#!/usr/bin/env python3
"""
WebSocket Test Client
====================

Simple test client to verify WebSocket connectivity and functionality.
"""

import asyncio
import websockets
import json
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebSocketTestClient:
    """Test client for WebSocket server"""
    
    def __init__(self, host="localhost", port=8001):
        self.host = host
        self.port = port
        self.websocket = None
        self.running = False
        self.stats = {
            'messages_received': 0,
            'errors': 0,
            'connect_time': None
        }
    
    async def test_connection(self, channel="metrics"):
        """Test WebSocket connection to specific channel"""
        
        uri = f"ws://{self.host}:{self.port}/ws/{channel}"
        logger.info(f"Testing WebSocket connection to: {uri}")
        
        try:
            # Connect to WebSocket
            logger.info("Attempting to connect...")
            self.websocket = await websockets.connect(
                uri,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            self.running = True
            self.stats['connect_time'] = time.time()
            logger.info(f"✅ Successfully connected to WebSocket server")
            
            # Listen for welcome message
            welcome_msg = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
            welcome_data = json.loads(welcome_msg)
            
            if welcome_data.get('type') == 'welcome':
                logger.info(f"📨 Received welcome message:")
                logger.info(f"   Subscriptions: {welcome_data.get('subscriptions', [])}")
                logger.info(f"   Server uptime: {welcome_data.get('server_info', {}).get('uptime', 0):.1f}s")
                logger.info(f"   Available channels: {welcome_data.get('server_info', {}).get('available_channels', [])}")
            
            # Test ping/pong
            await self.test_ping()
            
            # Test subscription changes
            await self.test_subscription_change()
            
            # Listen for a few messages
            await self.listen_for_messages(duration=10)
            
            logger.info(f"✅ Test completed successfully")
            logger.info(f"📊 Stats: {self.stats}")
            
        except asyncio.TimeoutError:
            logger.error("❌ Connection timeout - server may not be running")
            return False
        except websockets.exceptions.InvalidURI:
            logger.error(f"❌ Invalid WebSocket URI: {uri}")
            return False
        except websockets.exceptions.ConnectionRefused:
            logger.error(f"❌ Connection refused - check server is running on {self.host}:{self.port}")
            return False
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            self.stats['errors'] += 1
            return False
        finally:
            await self.disconnect()
        
        return True
    
    async def test_ping(self):
        """Test ping/pong functionality"""
        
        logger.info("🏓 Testing ping/pong...")
        
        ping_message = json.dumps({
            'type': 'ping',
            'timestamp': time.time()
        })
        
        await self.websocket.send(ping_message)
        
        # Wait for pong response
        response = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
        pong_data = json.loads(response)
        
        if pong_data.get('type') == 'pong':
            logger.info("✅ Ping/pong test successful")
        else:
            logger.warning(f"⚠️ Unexpected response to ping: {pong_data}")
    
    async def test_subscription_change(self):
        """Test changing subscriptions"""
        
        logger.info("🔄 Testing subscription changes...")
        
        # Change to health channel
        subscribe_message = json.dumps({
            'type': 'subscribe',
            'channels': ['health', 'alerts']
        })
        
        await self.websocket.send(subscribe_message)
        
        # Wait for subscription update
        response = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
        update_data = json.loads(response)
        
        if update_data.get('type') == 'subscription_updated':
            new_subs = update_data.get('subscriptions', [])
            logger.info(f"✅ Subscription changed to: {new_subs}")
        else:
            logger.warning(f"⚠️ Unexpected response to subscription change: {update_data}")
    
    async def listen_for_messages(self, duration=10):
        """Listen for messages for specified duration"""
        
        logger.info(f"👂 Listening for messages for {duration} seconds...")
        
        end_time = time.time() + duration
        
        while time.time() < end_time and self.running:
            try:
                message = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                data = json.loads(message)
                
                self.stats['messages_received'] += 1
                
                msg_type = data.get('type', 'unknown')
                channel = data.get('channel', 'none')
                
                if msg_type == 'data':
                    logger.info(f"📊 Received {msg_type} from {channel} channel")
                else:
                    logger.info(f"📨 Received {msg_type} message")
                
            except asyncio.TimeoutError:
                continue
            except json.JSONDecodeError:
                logger.warning("⚠️ Received invalid JSON message")
                self.stats['errors'] += 1
            except Exception as e:
                logger.error(f"❌ Error receiving message: {e}")
                self.stats['errors'] += 1
                break
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        
        self.running = False
        
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("🔌 Disconnected from WebSocket server")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")

async def test_all_channels():
    """Test all available channels"""
    
    channels = ['metrics', 'health', 'anomalies', 'alerts', 'all']
    
    for channel in channels:
        logger.info(f"\n{'='*50}")
        logger.info(f"Testing channel: {channel}")
        logger.info(f"{'='*50}")
        
        client = WebSocketTestClient()
        success = await client.test_connection(channel)
        
        if not success:
            logger.error(f"❌ Test failed for channel: {channel}")
            break
        
        # Wait a bit between tests
        await asyncio.sleep(2)

async def test_invalid_requests():
    """Test that the server properly handles invalid requests"""
    
    import aiohttp
    
    logger.info(f"\n{'='*50}")
    logger.info("Testing HTTP request to WebSocket endpoint")
    logger.info(f"{'='*50}")
    
    try:
        async with aiohttp.ClientSession() as session:
            # Try to make HTTP request to WebSocket endpoint
            async with session.get("http://localhost:11450/ws") as response:
                text = await response.text()
                logger.info(f"📄 HTTP response status: {response.status}")
                logger.info(f"📄 Response contains info page: {'WebSocket Server' in text}")
                
                if response.status == 400 and 'WebSocket Server' in text:
                    logger.info("✅ Server properly handles non-WebSocket requests")
                else:
                    logger.warning("⚠️ Unexpected response to HTTP request")
                    
    except Exception as e:
        logger.error(f"❌ Error testing HTTP request: {e}")

async def main():
    """Run all tests"""
    
    logger.info("🚀 Starting WebSocket tests...")
    logger.info("Make sure your WebSocket server is running on localhost:11450")
    
    try:
        # Test individual channels
        await test_all_channels()
        
        # Test HTTP requests
        await test_invalid_requests()
        
        logger.info(f"\n{'='*50}")
        logger.info("✅ All tests completed!")
        logger.info(f"{'='*50}")
        
    except KeyboardInterrupt:
        logger.info("\n⏹️ Tests interrupted by user")
    except Exception as e:
        logger.error(f"❌ Test suite failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())

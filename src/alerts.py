#!/usr/bin/env python3
"""
Intelligent Alert Management System
===================================

Advanced alert management with intelligence features:
- Alert correlation and grouping
- Escalation policies
- Notification routing
- Alert fatigue reduction
- Dependency mapping
- Contextual enrichment
- Performance tracking
"""

import asyncio
import aiohttp
import logging
import time
import json
import threading
from collections import deque, defaultdict
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Callable, Set
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    """Alert severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class AlertStatus(Enum):
    """Alert status values"""
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    SUPPRESSED = "suppressed"
    RESOLVED = "resolved"
    CLOSED = "closed"

@dataclass
class Alert:
    """Alert data structure"""
    id: str
    title: str
    description: str
    severity: AlertSeverity
    status: AlertStatus
    source: str
    metric_name: str
    current_value: float
    threshold: float
    target: str
    
    created_at: float
    updated_at: float
    acknowledged_at: Optional[float] = None
    resolved_at: Optional[float] = None
    
    tags: List[str] = None
    labels: Dict[str, str] = None
    context: Dict[str, Any] = None
    
    # Correlation information
    correlation_id: Optional[str] = None
    parent_alert_id: Optional[str] = None
    child_alert_ids: List[str] = None
    
    # Notification tracking
    notifications_sent: List[str] = None
    escalation_level: int = 0
    
    # Performance tracking
    detection_time: Optional[float] = None
    resolution_time: Optional[float] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.labels is None:
            self.labels = {}
        if self.context is None:
            self.context = {}
        if self.child_alert_ids is None:
            self.child_alert_ids = []
        if self.notifications_sent is None:
            self.notifications_sent = []

@dataclass
class EscalationRule:
    """Escalation rule configuration"""
    name: str
    conditions: Dict[str, Any]
    delay_seconds: int
    channels: List[str]
    enabled: bool = True

@dataclass
class NotificationChannel:
    """Notification channel configuration"""
    name: str
    type: str  # email, webhook, slack, etc.
    config: Dict[str, Any]
    enabled: bool = True
    rate_limit: Optional[int] = None  # max notifications per hour

class AlertCorrelator:
    """Correlate related alerts to reduce noise"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.correlation_window = config.get('correlation_window_seconds', 300)  # 5 minutes
        self.active_correlations = {}
        
    def correlate_alert(self, alert: Alert, existing_alerts: List[Alert]) -> Optional[str]:
        """Find correlation for new alert"""
        
        # Try different correlation strategies
        correlation_id = (
            self._correlate_by_target(alert, existing_alerts) or
            self._correlate_by_metric_family(alert, existing_alerts) or
            self._correlate_by_dependency(alert, existing_alerts)
        )
        
        return correlation_id
    
    def _correlate_by_target(self, alert: Alert, existing_alerts: List[Alert]) -> Optional[str]:
        """Correlate alerts from the same target"""
        
        cutoff_time = time.time() - self.correlation_window
        
        for existing_alert in existing_alerts:
            if (existing_alert.target == alert.target and
                existing_alert.created_at > cutoff_time and
                existing_alert.status in [AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]):
                
                return existing_alert.correlation_id or existing_alert.id
        
        return None
    
    def _correlate_by_metric_family(self, alert: Alert, existing_alerts: List[Alert]) -> Optional[str]:
        """Correlate alerts from related metrics"""
        
        metric_families = {
            'network_latency': ['icmp_ping_time', 'tcp_handshake_time', 'http_response_time'],
            'network_quality': ['packet_loss', 'jitter', 'mos_score'],
            'connectivity': ['connection_errors', 'dns_errors', 'timeout_errors'],
            'bandwidth': ['bandwidth_download', 'bandwidth_upload', 'interface_utilization']
        }
        
        alert_family = None
        for family, metrics in metric_families.items():
            if alert.metric_name in metrics:
                alert_family = family
                break
        
        if not alert_family:
            return None
        
        cutoff_time = time.time() - self.correlation_window
        family_metrics = metric_families[alert_family]
        
        for existing_alert in existing_alerts:
            if (existing_alert.metric_name in family_metrics and
                existing_alert.created_at > cutoff_time and
                existing_alert.status in [AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]):
                
                return existing_alert.correlation_id or existing_alert.id
        
        return None
    
    def _correlate_by_dependency(self, alert: Alert, existing_alerts: List[Alert]) -> Optional[str]:
        """Correlate alerts based on network dependencies"""
        
        # Simple dependency logic - can be enhanced with topology data
        if 'dns' in alert.metric_name.lower():
            # DNS issues might be related to connectivity issues
            for existing_alert in existing_alerts:
                if ('connection' in existing_alert.metric_name.lower() and
                    existing_alert.status in [AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]):
                    return existing_alert.correlation_id or existing_alert.id
        
        return None

class AlertGrouper:
    """Group correlated alerts for better management"""
    
    def __init__(self):
        self.groups = {}  # correlation_id -> AlertGroup
    
    def add_alert_to_group(self, alert: Alert):
        """Add alert to appropriate group"""
        
        correlation_id = alert.correlation_id or alert.id
        
        if correlation_id not in self.groups:
            self.groups[correlation_id] = AlertGroup(
                id=correlation_id,
                title=f"Alert Group: {alert.metric_name}",
                severity=alert.severity,
                created_at=alert.created_at
            )
        
        group = self.groups[correlation_id]
        group.add_alert(alert)
        
        return group
    
    def get_group(self, correlation_id: str) -> Optional['AlertGroup']:
        """Get alert group by correlation ID"""
        return self.groups.get(correlation_id)
    
    def cleanup_resolved_groups(self):
        """Clean up groups where all alerts are resolved"""
        
        resolved_groups = []
        
        for group_id, group in self.groups.items():
            if group.is_resolved():
                resolved_groups.append(group_id)
        
        for group_id in resolved_groups:
            del self.groups[group_id]

@dataclass
class AlertGroup:
    """Group of correlated alerts"""
    id: str
    title: str
    severity: AlertSeverity
    created_at: float
    updated_at: float = None
    
    alerts: List[Alert] = None
    
    def __post_init__(self):
        if self.alerts is None:
            self.alerts = []
        if self.updated_at is None:
            self.updated_at = self.created_at
    
    def add_alert(self, alert: Alert):
        """Add alert to group"""
        self.alerts.append(alert)
        self.updated_at = time.time()
        
        # Update group severity to highest
        if alert.severity.value in ['critical', 'high']:
            if self.severity.value not in ['critical', 'high']:
                self.severity = alert.severity
        elif alert.severity == AlertSeverity.HIGH and self.severity != AlertSeverity.CRITICAL:
            self.severity = AlertSeverity.HIGH
    
    def get_primary_alert(self) -> Alert:
        """Get primary alert (usually first or highest severity)"""
        if not self.alerts:
            return None
        
        # Find highest severity alert
        critical_alerts = [a for a in self.alerts if a.severity == AlertSeverity.CRITICAL]
        if critical_alerts:
            return critical_alerts[0]
        
        high_alerts = [a for a in self.alerts if a.severity == AlertSeverity.HIGH]
        if high_alerts:
            return high_alerts[0]
        
        return self.alerts[0]
    
    def is_resolved(self) -> bool:
        """Check if all alerts in group are resolved"""
        return all(alert.status in [AlertStatus.RESOLVED, AlertStatus.CLOSED] 
                  for alert in self.alerts)
    
    def get_summary(self) -> str:
        """Get group summary"""
        primary = self.get_primary_alert()
        if not primary:
            return "Empty alert group"
        
        count = len(self.alerts)
        return f"{primary.title} (and {count-1} related alerts)" if count > 1 else primary.title

class NotificationManager:
    """Manage alert notifications across multiple channels"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.channels = {}
        self.rate_limits = defaultdict(deque)  # channel_name -> timestamps
        
        self._setup_channels()
    
    def _setup_channels(self):
        """Setup notification channels"""
        
        for channel_config in self.config.get('channels', []):
            channel = NotificationChannel(**channel_config)
            self.channels[channel.name] = channel
    
    async def send_notification(self, alert: Alert, channel_names: List[str],
                              template: str = "default") -> Dict[str, bool]:
        """Send notification to specified channels"""
        
        results = {}
        
        for channel_name in channel_names:
            if channel_name not in self.channels:
                logger.warning(f"Unknown notification channel: {channel_name}")
                results[channel_name] = False
                continue
            
            channel = self.channels[channel_name]
            
            if not channel.enabled:
                logger.debug(f"Channel {channel_name} is disabled")
                results[channel_name] = False
                continue
            
            # Check rate limiting
            if not self._check_rate_limit(channel):
                logger.warning(f"Rate limit exceeded for channel {channel_name}")
                results[channel_name] = False
                continue
            
            try:
                success = await self._send_to_channel(alert, channel, template)
                results[channel_name] = success
                
                if success:
                    self._record_rate_limit(channel)
                    alert.notifications_sent.append(channel_name)
                
            except Exception as e:
                logger.error(f"Error sending notification to {channel_name}: {e}")
                results[channel_name] = False
        
        return results
    
    def _check_rate_limit(self, channel: NotificationChannel) -> bool:
        """Check if channel rate limit allows sending"""
        
        if not channel.rate_limit:
            return True
        
        now = time.time()
        hour_ago = now - 3600
        
        # Clean old entries
        timestamps = self.rate_limits[channel.name]
        while timestamps and timestamps[0] < hour_ago:
            timestamps.popleft()
        
        return len(timestamps) < channel.rate_limit
    
    def _record_rate_limit(self, channel: NotificationChannel):
        """Record notification for rate limiting"""
        
        if channel.rate_limit:
            self.rate_limits[channel.name].append(time.time())
    
    async def _send_to_channel(self, alert: Alert, channel: NotificationChannel,
                             template: str) -> bool:
        """Send notification to specific channel"""
        
        if channel.type == "email":
            return await self._send_email(alert, channel, template)
        elif channel.type == "webhook":
            return await self._send_webhook(alert, channel, template)
        elif channel.type == "slack":
            return await self._send_slack(alert, channel, template)
        else:
            logger.warning(f"Unknown channel type: {channel.type}")
            return False
    
    async def _send_email(self, alert: Alert, channel: NotificationChannel,
                         template: str) -> bool:
        """Send email notification"""
        
        try:
            smtp_server = channel.config.get('smtp_server')
            smtp_port = channel.config.get('smtp_port', 587)
            username = channel.config.get('username')
            password = channel.config.get('password')
            recipients = channel.config.get('recipients', [])
            
            if not all([smtp_server, username, password, recipients]):
                logger.error("Incomplete email configuration")
                return False
            
            # Create message
            subject = f"[{alert.severity.value.upper()}] {alert.title}"
            body = self._format_alert_message(alert, template)
            
            msg = MIMEMultipart()
            msg['From'] = username
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'html'))
            
            # Send email
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(username, password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email notification sent for alert {alert.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False
    
    async def _send_webhook(self, alert: Alert, channel: NotificationChannel,
                           template: str) -> bool:
        """Send webhook notification"""
        
        try:
            url = channel.config.get('url')
            headers = channel.config.get('headers', {})
            
            if not url:
                logger.error("Webhook URL not configured")
                return False
            
            # Prepare payload with proper serialization
            alert_dict = asdict(alert)
            
            # Convert enums to strings
            alert_dict['severity'] = alert.severity.value
            alert_dict['status'] = alert.status.value
            
            # Convert timestamps to ISO format - FIX: Use datetime imported at top
            alert_dict['created_at'] = datetime.fromtimestamp(alert.created_at).isoformat()
            alert_dict['updated_at'] = datetime.fromtimestamp(alert.updated_at).isoformat()
            
            if alert.acknowledged_at:
                alert_dict['acknowledged_at'] = datetime.fromtimestamp(alert.acknowledged_at).isoformat()
            if alert.resolved_at:
                alert_dict['resolved_at'] = datetime.fromtimestamp(alert.resolved_at).isoformat()
            
            payload = {
                'alert': alert_dict,
                'message': self._format_alert_message(alert, template),
                'timestamp': time.time()
            }
            
            # Send webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=10) as response:
                    if response.status < 400:
                        logger.info(f"Webhook notification sent for alert {alert.id}")
                        return True
                    else:
                        logger.error(f"Webhook returned status {response.status}")
                        return False
        
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            return False

    async def _send_slack(self, alert: Alert, channel: NotificationChannel,
                         template: str) -> bool:
        """Send Slack notification"""
        
        try:
            webhook_url = channel.config.get('webhook_url')
            
            if not webhook_url:
                logger.error("Slack webhook URL not configured")
                return False
            
            # Format message for Slack
            color = {
                AlertSeverity.CRITICAL: "danger",
                AlertSeverity.HIGH: "warning", 
                AlertSeverity.MEDIUM: "warning",
                AlertSeverity.LOW: "good",
                AlertSeverity.INFO: "good"
            }.get(alert.severity, "warning")
            
            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": alert.title,
                        "text": alert.description,
                        "fields": [
                            {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                            {"title": "Target", "value": alert.target, "short": True},
                            {"title": "Metric", "value": alert.metric_name, "short": True},
                            {"title": "Value", "value": f"{alert.current_value:.2f}", "short": True},
                            {"title": "Threshold", "value": f"{alert.threshold:.2f}", "short": True},
                            {"title": "Time", "value": datetime.fromtimestamp(alert.created_at).strftime('%Y-%m-%d %H:%M:%S'), "short": True}
                        ],
                        "footer": "Network Intelligence Monitor",
                        "ts": int(alert.created_at)
                    }
                ]
            }
            
            # Send to Slack
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        logger.info(f"Slack notification sent for alert {alert.id}")
                        return True
                    else:
                        logger.error(f"Slack webhook returned status {response.status}")
                        return False
        
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False
    
    def _format_alert_message(self, alert: Alert, template: str) -> str:
        """Format alert message using template"""
        
        if template == "html":
            return self._format_html_message(alert)
        else:
            return self._format_text_message(alert)
    
    def _format_html_message(self, alert: Alert) -> str:
        """Format HTML email message"""
        
        severity_color = {
            AlertSeverity.CRITICAL: "#dc3545",
            AlertSeverity.HIGH: "#fd7e14",
            AlertSeverity.MEDIUM: "#ffc107",
            AlertSeverity.LOW: "#28a745",
            AlertSeverity.INFO: "#17a2b8"
        }.get(alert.severity, "#6c757d")
        
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="border-left: 4px solid {severity_color}; padding-left: 16px;">
                <h2 style="color: {severity_color};">{alert.title}</h2>
                <p><strong>Severity:</strong> {alert.severity.value.upper()}</p>
                <p><strong>Target:</strong> {alert.target}</p>
                <p><strong>Metric:</strong> {alert.metric_name}</p>
                <p><strong>Current Value:</strong> {alert.current_value:.2f}</p>
                <p><strong>Threshold:</strong> {alert.threshold:.2f}</p>
                <p><strong>Time:</strong> {datetime.fromtimestamp(alert.created_at).strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Description:</strong><br>{alert.description}</p>
                
                {self._format_context_html(alert.context) if alert.context else ""}
            </div>
        </body>
        </html>
        """
    
    def _format_text_message(self, alert: Alert) -> str:
        """Format plain text message"""
        
        message = f"""
Alert: {alert.title}

Severity: {alert.severity.value.upper()}
Target: {alert.target}
Metric: {alert.metric_name}
Current Value: {alert.current_value:.2f}
Threshold: {alert.threshold:.2f}
Time: {datetime.fromtimestamp(alert.created_at).strftime('%Y-%m-%d %H:%M:%S')}

Description:
{alert.description}
"""
        
        if alert.context:
            message += f"\nAdditional Context:\n{json.dumps(alert.context, indent=2)}"
        
        return message
    
    def _format_context_html(self, context: Dict[str, Any]) -> str:
        """Format context as HTML"""
        
        if not context:
            return ""
        
        html = "<h3>Additional Context:</h3><ul>"
        for key, value in context.items():
            html += f"<li><strong>{key}:</strong> {value}</li>"
        html += "</ul>"
        
        return html

class EscalationManager:
    """Manage alert escalation policies"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.rules = []
        self.escalation_tasks = {}  # alert_id -> asyncio.Task
        
        self._setup_rules()
    
    def _setup_rules(self):
        """Setup escalation rules"""
        
        for rule_config in self.config.get('rules', []):
            rule = EscalationRule(**rule_config)
            self.rules.append(rule)
        
        logger.info(f"Loaded {len(self.rules)} escalation rules")
    
    def start_escalation(self, alert: Alert, notification_manager: NotificationManager):
        """Start escalation process for an alert"""
        
        if alert.id in self.escalation_tasks:
            return  # Already escalating
        
        task = asyncio.create_task(
            self._escalation_process(alert, notification_manager)
        )
        self.escalation_tasks[alert.id] = task
    
    def stop_escalation(self, alert_id: str):
        """Stop escalation for an alert"""
        
        if alert_id in self.escalation_tasks:
            task = self.escalation_tasks[alert_id]
            task.cancel()
            del self.escalation_tasks[alert_id]
    
    async def _escalation_process(self, alert: Alert, notification_manager: NotificationManager):
        """Escalation process for an alert"""
        
        try:
            for rule in self.rules:
                if not rule.enabled:
                    continue
                
                if not self._matches_conditions(alert, rule.conditions):
                    continue
                
                # Wait for escalation delay
                await asyncio.sleep(rule.delay_seconds)
                
                # Check if alert is still open
                if alert.status in [AlertStatus.RESOLVED, AlertStatus.CLOSED]:
                    break
                
                # Send escalation notification
                logger.info(f"Escalating alert {alert.id} to level {alert.escalation_level + 1}")
                
                await notification_manager.send_notification(
                    alert, rule.channels, template="escalation"
                )
                
                alert.escalation_level += 1
                alert.updated_at = time.time()
                
        except asyncio.CancelledError:
            logger.debug(f"Escalation cancelled for alert {alert.id}")
        except Exception as e:
            logger.error(f"Error in escalation process for alert {alert.id}: {e}")
        finally:
            if alert.id in self.escalation_tasks:
                del self.escalation_tasks[alert.id]
    
    def _matches_conditions(self, alert: Alert, conditions: Dict[str, Any]) -> bool:
        """Check if alert matches escalation conditions"""
        
        # Check severity
        if 'severity' in conditions:
            required_severities = conditions['severity']
            if isinstance(required_severities, str):
                required_severities = [required_severities]
            if alert.severity.value not in required_severities:
                return False
        
        # Check metric patterns
        if 'metric_patterns' in conditions:
            patterns = conditions['metric_patterns']
            if not any(pattern in alert.metric_name for pattern in patterns):
                return False
        
        # Check tags
        if 'tags' in conditions:
            required_tags = conditions['tags']
            if not all(tag in alert.tags for tag in required_tags):
                return False
        
        return True

class AlertManager:
    """Main alert management system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Storage
        self.alerts = {}  # alert_id -> Alert
        self.alert_history = deque(maxlen=10000)
        
        # Components
        self.correlator = AlertCorrelator(config.get('correlation', {}))
        self.grouper = AlertGrouper()
        self.notification_manager = NotificationManager(config.get('notifications', {}))
        self.escalation_manager = EscalationManager(config.get('escalation', {}))
        
        # Threading
        self._lock = threading.Lock()
        self._cleanup_thread = None
        self._running = False
        
        # Performance tracking
        self.metrics = {
            'total_alerts': 0,
            'active_alerts': 0,
            'notifications_sent': 0,
            'escalations_triggered': 0,
            'average_resolution_time': 0.0
        }
    
    def start(self):
        """Start the alert management system"""
        
        self._running = True
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        
        logger.info("Alert management system started")
    
    def stop(self):
        """Stop the alert management system"""
        
        self._running = False
        
        # Cancel all escalation tasks
        for task in list(self.escalation_manager.escalation_tasks.values()):
            task.cancel()
        
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        
        logger.info("Alert management system stopped")
    
    async def create_alert(self, title: str, description: str, severity: AlertSeverity,
                          source: str, metric_name: str, current_value: float,
                          threshold: float, target: str, **kwargs) -> Alert:
        """Create a new alert"""
        
        # Generate alert ID
        alert_id = self._generate_alert_id(title, target, metric_name)
        
        # Check for existing alert
        with self._lock:
            existing_alert = self.alerts.get(alert_id)
            if existing_alert and existing_alert.status in [AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]:
                # Update existing alert
                existing_alert.current_value = current_value
                existing_alert.updated_at = time.time()
                return existing_alert
        
        # Create new alert
        alert = Alert(
            id=alert_id,
            title=title,
            description=description,
            severity=severity,
            status=AlertStatus.OPEN,
            source=source,
            metric_name=metric_name,
            current_value=current_value,
            threshold=threshold,
            target=target,
            created_at=time.time(),
            updated_at=time.time(),
            detection_time=time.time(),
            **kwargs
        )
        
        # Find correlation
        with self._lock:
            existing_alerts = list(self.alerts.values())
        
        correlation_id = self.correlator.correlate_alert(alert, existing_alerts)
        if correlation_id:
            alert.correlation_id = correlation_id
        
        # Add to storage
        with self._lock:
            self.alerts[alert_id] = alert
            self.alert_history.append(alert)
            self.metrics['total_alerts'] += 1
            self.metrics['active_alerts'] = len([a for a in self.alerts.values() 
                                               if a.status in [AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]])
        
        # Add to group
        group = self.grouper.add_alert_to_group(alert)
        
        # Send initial notifications
        await self._send_initial_notifications(alert)
        
        # Start escalation if configured
        if self.config.get('escalation', {}).get('enabled', True):
            self.escalation_manager.start_escalation(alert, self.notification_manager)
        
        logger.info(f"Created alert {alert_id}: {title} (severity: {severity.value})")
        
        return alert
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "system") -> bool:
        """Acknowledge an alert"""
        
        with self._lock:
            alert = self.alerts.get(alert_id)
            if not alert or alert.status != AlertStatus.OPEN:
                return False
            
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = time.time()
            alert.updated_at = time.time()
        
        # Stop escalation
        self.escalation_manager.stop_escalation(alert_id)
        
        logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
        return True
    
    async def resolve_alert(self, alert_id: str, resolved_by: str = "system") -> bool:
        """Resolve an alert"""
        
        with self._lock:
            alert = self.alerts.get(alert_id)
            if not alert or alert.status in [AlertStatus.RESOLVED, AlertStatus.CLOSED]:
                return False
            
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = time.time()
            alert.updated_at = time.time()
            
            if alert.detection_time:
                alert.resolution_time = time.time() - alert.detection_time
        
        # Stop escalation
        self.escalation_manager.stop_escalation(alert_id)
        
        # Update metrics
        with self._lock:
            self.metrics['active_alerts'] = len([a for a in self.alerts.values() 
                                               if a.status in [AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]])
            
            # Update average resolution time
            resolved_alerts = [a for a in self.alerts.values() 
                             if a.resolution_time is not None]
            if resolved_alerts:
                total_time = sum(a.resolution_time for a in resolved_alerts)
                self.metrics['average_resolution_time'] = total_time / len(resolved_alerts)
        
        logger.info(f"Alert {alert_id} resolved by {resolved_by}")
        return True
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get alert by ID"""
        
        with self._lock:
            return self.alerts.get(alert_id)
    
    def get_active_alerts(self, target: str = None, severity: AlertSeverity = None) -> List[Alert]:
        """Get active alerts with optional filtering"""
        
        with self._lock:
            alerts = [
                alert for alert in self.alerts.values()
                if alert.status in [AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]
            ]
        
        if target:
            alerts = [alert for alert in alerts if alert.target == target]
        
        if severity:
            alerts = [alert for alert in alerts if alert.severity == severity]
        
        return sorted(alerts, key=lambda a: a.created_at, reverse=True)
    
    def get_alert_groups(self) -> List[AlertGroup]:
        """Get all alert groups"""
        
        return list(self.grouper.groups.values())
    
    async def _send_initial_notifications(self, alert: Alert):
        """Send initial notifications for a new alert"""
        
        # Determine notification channels based on severity
        channels = self._get_notification_channels(alert)
        
        if channels:
            results = await self.notification_manager.send_notification(
                alert, channels, template="default"
            )
            
            successful_channels = [ch for ch, success in results.items() if success]
            if successful_channels:
                self.metrics['notifications_sent'] += len(successful_channels)
                logger.info(f"Notifications sent for alert {alert.id} to: {', '.join(successful_channels)}")
    
    def _get_notification_channels(self, alert: Alert) -> List[str]:
        """Get notification channels for alert based on severity"""
        
        channel_config = self.config.get('notifications', {}).get('routing', {})
        
        severity_channels = {
            AlertSeverity.CRITICAL: channel_config.get('critical', ['email', 'slack']),
            AlertSeverity.HIGH: channel_config.get('high', ['email', 'slack']),
            AlertSeverity.MEDIUM: channel_config.get('medium', ['slack']),
            AlertSeverity.LOW: channel_config.get('low', ['slack']),
            AlertSeverity.INFO: channel_config.get('info', [])
        }
        
        return severity_channels.get(alert.severity, [])
    
    def _generate_alert_id(self, title: str, target: str, metric_name: str) -> str:
        """Generate unique alert ID"""
        
        # Create deterministic ID so same issue doesn't create multiple alerts
        content = f"{title}:{target}:{metric_name}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _cleanup_loop(self):
        """Background cleanup loop"""
        
        while self._running:
            try:
                self._cleanup_old_alerts()
                self.grouper.cleanup_resolved_groups()
                time.sleep(3600)  # Run every hour
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                time.sleep(300)
    
    def _cleanup_old_alerts(self):
        """Clean up old resolved alerts"""
        
        retention_hours = self.config.get('retention_hours', 168)  # 1 week
        cutoff_time = time.time() - (retention_hours * 3600)
        
        with self._lock:
            alerts_to_remove = []
            
            for alert_id, alert in self.alerts.items():
                if (alert.status in [AlertStatus.RESOLVED, AlertStatus.CLOSED] and
                    alert.updated_at < cutoff_time):
                    alerts_to_remove.append(alert_id)
            
            for alert_id in alerts_to_remove:
                del self.alerts[alert_id]
            
            if alerts_to_remove:
                logger.info(f"Cleaned up {len(alerts_to_remove)} old alerts")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get alert system metrics"""
        
        with self._lock:
            return self.metrics.copy()
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get detailed alert statistics"""
        
        with self._lock:
            alerts = list(self.alerts.values())
        
        now = time.time()
        hour_ago = now - 3600
        day_ago = now - 86400
        
        stats = {
            'total_alerts': len(alerts),
            'active_alerts': len([a for a in alerts if a.status in [AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]]),
            'alerts_last_hour': len([a for a in alerts if a.created_at > hour_ago]),
            'alerts_last_day': len([a for a in alerts if a.created_at > day_ago]),
            'by_severity': {},
            'by_status': {},
            'by_target': {},
            'average_resolution_time_minutes': self.metrics['average_resolution_time'] / 60,
            'total_notifications_sent': self.metrics['notifications_sent'],
            'escalations_triggered': self.metrics['escalations_triggered']
        }
        
        # Count by severity
        for severity in AlertSeverity:
            stats['by_severity'][severity.value] = len([a for a in alerts if a.severity == severity])
        
        # Count by status
        for status in AlertStatus:
            stats['by_status'][status.value] = len([a for a in alerts if a.status == status])
        
        # Count by target
        target_counts = defaultdict(int)
        for alert in alerts:
            target_counts[alert.target] += 1
        stats['by_target'] = dict(target_counts)
        
        return stats

# Utility functions for integration

def create_alert_manager(config: Dict[str, Any]) -> AlertManager:
    """Create and configure alert manager"""
    
    manager = AlertManager(config)
    manager.start()
    return manager

def integrate_alerts_with_detector(detector, alert_manager: AlertManager):
    """Integrate alert manager with anomaly detector"""
    
    original_detect_anomaly = detector.detect_anomaly
    
    async def enhanced_detect_anomaly(metrics):
        result = await original_detect_anomaly(metrics)
        
        if result.is_anomaly:
            # Create alert from anomaly
            severity = AlertSeverity.CRITICAL if result.severity == "critical" else \
                      AlertSeverity.HIGH if result.severity == "high" else \
                      AlertSeverity.MEDIUM
            
            await alert_manager.create_alert(
                title=f"Network Anomaly: {metrics.target_host}",
                description=result.recommendation,
                severity=severity,
                source="ai_detector",
                metric_name="anomaly_score",
                current_value=result.anomaly_score,
                threshold=detector.thresholds.get('reconstruction_error', 0.1),
                target=metrics.target_host,
                context={
                    'confidence': result.confidence,
                    'temporal_pattern': result.temporal_pattern,
                    'feature_contributions': result.feature_contributions
                }
            )
        
        return result
    
    detector.detect_anomaly = enhanced_detect_anomaly
    logger.info("Alert management integrated with detector")

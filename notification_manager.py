"""
Enterprise OCR Notification Management
Provides comprehensive notification system for job completion, status updates, and alerts
"""
import smtplib
import json
import requests
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from email.mime.base import MimeBase
from email import encoders
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import threading
from pathlib import Path
from logger import log_manager
from config import config


@dataclass
class NotificationMessage:
    """Notification message structure"""
    subject: str
    body: str
    message_type: str  # 'success', 'error', 'warning', 'info'
    priority: str = 'normal'  # 'low', 'normal', 'high', 'urgent'
    attachments: List[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.attachments is None:
            self.attachments = []
        if self.metadata is None:
            self.metadata = {}


class NotificationChannel:
    """Base class for notification channels"""

    def send(self, message: NotificationMessage) -> bool:
        """Send notification message"""
        raise NotImplementedError

    def test_connection(self) -> bool:
        """Test channel connectivity"""
        raise NotImplementedError


class EmailChannel(NotificationChannel):
    """Email notification channel"""

    def __init__(self, config):
        self.config = config
        self._connection = None

    def send(self, message: NotificationMessage) -> bool:
        """Send email notification"""
        try:
            # Create message
            msg = MimeMultipart()
            msg['From'] = self.config.smtp_username
            msg['To'] = self.config.notification_email
            msg['Subject'] = message.subject

            # Add priority header
            if message.priority == 'high':
                msg['X-Priority'] = '2'
            elif message.priority == 'urgent':
                msg['X-Priority'] = '1'

            # Email body
            body = f"""
OCR Processing Notification

Type: {message.message_type.upper()}
Priority: {message.priority.upper()}
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{message.body}

---
OCR Processor Enterprise Edition
Generated: {datetime.now().isoformat()}
            """

            msg.attach(MimeText(body, 'plain'))

            # Add attachments
            for attachment_path in message.attachments:
                self._add_attachment(msg, attachment_path)

            # Send email
            with self._get_smtp_connection() as server:
                server.send_message(msg)

            log_manager.logger.info(
                "Email notification sent",
                recipient=self.config.notification_email,
                subject=message.subject,
                message_type=message.message_type
            )

            return True

        except Exception as e:
            log_manager.logger.error(
                "Email notification failed",
                error=str(e),
                recipient=self.config.notification_email,
                message_type=message.message_type
            )
            return False

    def test_connection(self) -> bool:
        """Test email connectivity"""
        try:
            with self._get_smtp_connection() as server:
                # Send test email
                msg = MimeText("OCR Processor - Email channel test")
                msg['From'] = self.config.smtp_username
                msg['To'] = self.config.notification_email
                msg['Subject'] = "OCR Processor - Connection Test"

                server.send_message(msg)

            return True

        except Exception as e:
            log_manager.logger.error("Email connection test failed", error=str(e))
            return False

    def _get_smtp_connection(self):
        """Get SMTP connection with connection pooling"""
        if self._connection is None or self._connection is smtplib.SMTP:
            try:
                if self._connection:
                    self._connection.quit()
            except:
                pass

            self._connection = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port)
            self._connection.starttls()
            self._connection.login(self.config.smtp_username, self.config.smtp_password)

        return self._connection

    def _add_attachment(self, msg: MimeMultipart, file_path: str):
        """Add file attachment to email"""
        try:
            path = Path(file_path)
            if not path.exists():
                return

            # Guess MIME type
            import mimetypes
            mime_type, encoding = mimetypes.guess_type(str(path))

            if mime_type is None:
                mime_type = 'application/octet-stream'

            # Create attachment
            with open(path, 'rb') as attachment:
                part = MimeBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)

                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{path.name}"'
                )

                if encoding:
                    part.add_header('Content-Encoding', encoding)

                msg.attach(part)

        except Exception as e:
            log_manager.logger.warning(
                "Failed to attach file",
                file_path=file_path,
                error=str(e)
            )


class WebhookChannel(NotificationChannel):
    """Webhook notification channel"""

    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.session.timeout = 10

    def send(self, message: NotificationMessage) -> bool:
        """Send webhook notification"""
        try:
            payload = {
                'subject': message.subject,
                'body': message.body,
                'type': message.message_type,
                'priority': message.priority,
                'timestamp': datetime.now().isoformat(),
                'source': 'ocr-processor',
                'version': '2.0.0',
                'metadata': message.metadata
            }

            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'OCR-Processor/2.0.0'
            }

            response = self.session.post(
                self.config.webhook_url,
                json=payload,
                headers=headers
            )

            if response.status_code in [200, 201, 202, 204]:
                log_manager.logger.info(
                    "Webhook notification sent",
                    webhook_url=self.config.webhook_url,
                    status_code=response.status_code,
                    message_type=message.message_type
                )
                return True
            else:
                log_manager.logger.error(
                    "Webhook notification failed",
                    webhook_url=self.config.webhook_url,
                    status_code=response.status_code,
                    response_body=response.text[:500],
                    message_type=message.message_type
                )
                return False

        except requests.exceptions.RequestException as e:
            log_manager.logger.error(
                "Webhook request failed",
                webhook_url=self.config.webhook_url,
                error=str(e),
                message_type=message.message_type
            )
            return False

    def test_connection(self) -> bool:
        """Test webhook connectivity"""
        try:
            test_payload = {
                'test': True,
                'timestamp': datetime.now().isoformat(),
                'source': 'ocr-processor'
            }

            response = self.session.post(
                self.config.webhook_url,
                json=test_payload,
                timeout=5
            )

            return response.status_code in [200, 201, 202, 204]

        except Exception as e:
            log_manager.logger.error("Webhook connection test failed", error=str(e))
            return False


class SlackChannel(NotificationChannel):
    """Slack notification channel"""

    def __init__(self, webhook_url: str, channel: str = None):
        self.webhook_url = webhook_url
        self.channel = channel
        self.session = requests.Session()

    def send(self, message: NotificationMessage) -> bool:
        """Send Slack notification"""
        try:
            # Determine color based on message type and priority
            color_map = {
                ('success', 'normal'): 'good',
                ('success', 'high'): 'good',
                ('error', 'normal'): 'danger',
                ('error', 'high'): 'danger',
                ('error', 'urgent'): 'danger',
                ('warning', 'normal'): 'warning',
                ('warning', 'high'): 'warning',
                ('info', 'normal'): '#439FE0'
            }

            color = color_map.get((message.message_type, message.priority), '#439FE0')

            # Create Slack payload
            payload = {
                'attachments': [{
                    'color': color,
                    'title': message.subject,
                    'text': message.body,
                    'ts': int(datetime.now().timestamp()),
                    'footer': 'OCR Processor',
                    'footer_icon': 'https://platform.slack-edge.com/img/default_application_icon.png'
                }]
            }

            if self.channel:
                payload['channel'] = self.channel

            response = self.session.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                log_manager.logger.info(
                    "Slack notification sent",
                    message_type=message.message_type,
                    priority=message.priority
                )
                return True
            else:
                log_manager.logger.error(
                    "Slack notification failed",
                    status_code=response.status_code,
                    response_body=response.text[:500]
                )
                return False

        except Exception as e:
            log_manager.logger.error("Slack notification error", error=str(e))
            return False

    def test_connection(self) -> bool:
        """Test Slack connectivity"""
        try:
            test_payload = {
                'text': 'OCR Processor - Slack channel test',
                'channel': self.channel
            }

            response = self.session.post(
                self.webhook_url,
                json=test_payload,
                timeout=5
            )

            return response.status_code == 200

        except Exception as e:
            log_manager.logger.error("Slack connection test failed", error=str(e))
            return False


class NotificationManager:
    """Main notification management system"""

    def __init__(self, config):
        self.config = config
        self.channels: Dict[str, NotificationChannel] = {}
        self._setup_channels()

    def _setup_channels(self):
        """Set up notification channels based on configuration"""
        # Email channel
        if (self.config.enable_notifications and
            self.config.notification_email and
            self.config.smtp_server):
            self.channels['email'] = EmailChannel(self.config)

        # Webhook channel
        if (self.config.enable_notifications and
            self.config.webhook_url):
            self.channels['webhook'] = WebhookChannel(self.config)

        # Slack channel (if webhook URL contains slack)
        if (self.config.webhook_url and
            'slack' in self.config.webhook_url.lower()):
            self.channels['slack'] = SlackChannel(self.config.webhook_url)

    def send_notification(self, message: NotificationMessage) -> bool:
        """Send notification through all configured channels"""
        if not self.channels:
            log_manager.logger.debug(
                "No notification channels configured",
                message_type=message.message_type
            )
            return False

        success_count = 0

        for channel_name, channel in self.channels.items():
            try:
                if channel.send(message):
                    success_count += 1
                else:
                    log_manager.logger.warning(
                        "Notification failed",
                        channel=channel_name,
                        message_type=message.message_type
                    )
            except Exception as e:
                log_manager.logger.error(
                    "Notification channel error",
                    channel=channel_name,
                    error=str(e),
                    message_type=message.message_type
                )

        success = success_count > 0
        log_manager.logger.info(
            "Notification attempt completed",
            message_type=message.message_type,
            success=success,
            channels_attempted=len(self.channels),
            channels_successful=success_count
        )

        return success

    def send_job_completion_notification(self, job_id: str, success: bool,
                                       job_details: Dict[str, Any]) -> bool:
        """Send job completion notification"""
        if success:
            message_type = 'success'
            priority = 'normal'
            subject = f"✅ OCR Job Completed Successfully - {job_id[:8]}"
            body = f"""
OCR processing job has completed successfully!

📋 Job Details:
- Job ID: {job_id}
- Input: {job_details.get('input_path', 'Unknown')}
- Mode: {job_details.get('mode', 'Unknown')}
- Files Processed: {job_details.get('processed_files', 0)}
- Processing Time: {job_details.get('processing_time', 'Unknown')}s

📁 Output Location:
{job_details.get('output_path', 'See logs for details')}

The OCR processing completed without errors. All output files have been generated successfully.
            """
        else:
            message_type = 'error'
            priority = 'high'
            subject = f"❌ OCR Job Failed - {job_id[:8]}"
            body = f"""
OCR processing job has failed!

📋 Job Details:
- Job ID: {job_id}
- Input: {job_details.get('input_path', 'Unknown')}
- Mode: {job_details.get('mode', 'Unknown')}
- Error: {job_details.get('error_message', 'Unknown error')}

🔍 Troubleshooting:
- Check the job logs for detailed error information
- Verify input file integrity
- Ensure sufficient system resources
- Check OCR engine availability

The job will be retried automatically if recovery is enabled.
            """

        message = NotificationMessage(
            subject=subject,
            body=body,
            message_type=message_type,
            priority=priority,
            metadata={
                'job_id': job_id,
                'success': success,
                **job_details
            }
        )

        return self.send_notification(message)

    def send_batch_completion_notification(self, batch_details: Dict[str, Any]) -> bool:
        """Send batch processing completion notification"""
        total_jobs = batch_details.get('total_jobs', 0)
        successful_jobs = batch_details.get('successful_jobs', 0)
        failed_jobs = batch_details.get('failed_jobs', 0)

        if failed_jobs == 0:
            message_type = 'success'
            priority = 'normal'
            subject = f"✅ Batch Processing Completed - {successful_jobs}/{total_jobs} Jobs"
        elif successful_jobs == 0:
            message_type = 'error'
            priority = 'urgent'
            subject = f"❌ Batch Processing Failed - All {total_jobs} Jobs"
        else:
            message_type = 'warning'
            priority = 'high'
            subject = f"⚠️ Batch Processing Mixed Results - {successful_jobs}/{total_jobs} Jobs"

        body = f"""
Batch OCR processing has completed!

📊 Summary:
- Total Jobs: {total_jobs}
- Successful: {successful_jobs}
- Failed: {failed_jobs}
- Success Rate: {(successful_jobs/total_jobs)*100:.1f}%
- Total Processing Time: {batch_details.get('total_time', 'Unknown')}s

📁 Input Details:
- Input Path: {batch_details.get('input_path', 'Unknown')}
- Processing Mode: {batch_details.get('mode', 'Unknown')}
- Language: {batch_details.get('language', 'Unknown')}

🔍 Performance Metrics:
- Average Time per Job: {batch_details.get('avg_job_time', 'Unknown')}s
- Files Processed: {batch_details.get('total_files', 0)}
- Data Processed: {batch_details.get('total_size_mb', 'Unknown')} MB

{'✅ All jobs completed successfully!' if failed_jobs == 0 else '⚠️ Some jobs failed - check logs for details'}
        """

        message = NotificationMessage(
            subject=subject,
            body=body,
            message_type=message_type,
            priority=priority,
            metadata=batch_details
        )

        return self.send_notification(message)

    def send_system_alert(self, alert_type: str, message: str,
                         severity: str = 'medium', **metadata) -> bool:
        """Send system alert notification"""
        priority_map = {
            'low': 'low',
            'medium': 'normal',
            'high': 'high',
            'critical': 'urgent'
        }

        subject = f"🚨 System Alert - {alert_type.replace('_', ' ').title()}"
        body = f"""
System Alert Notification

Alert Type: {alert_type}
Severity: {severity.upper()}
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Message:
{message}

Metadata:
{json.dumps(metadata, indent=2, default=str)}

Please investigate this alert and take appropriate action.
        """

        notification_message = NotificationMessage(
            subject=subject,
            body=body,
            message_type='warning',
            priority=priority_map.get(severity, 'normal'),
            metadata={'alert_type': alert_type, 'severity': severity, **metadata}
        )

        return self.send_notification(notification_message)

    def test_all_channels(self) -> Dict[str, bool]:
        """Test all configured notification channels"""
        results = {}

        for channel_name, channel in self.channels.items():
            try:
                results[channel_name] = channel.test_connection()
                log_manager.logger.info(
                    "Channel test completed",
                    channel=channel_name,
                    success=results[channel_name]
                )
            except Exception as e:
                log_manager.logger.error(
                    "Channel test failed",
                    channel=channel_name,
                    error=str(e)
                )
                results[channel_name] = False

        return results


class NotificationScheduler:
    """Schedule notifications for delayed delivery"""

    def __init__(self, notification_manager: NotificationManager):
        self.notification_manager = notification_manager
        self.scheduled_notifications = []
        self._lock = threading.Lock()
        self._scheduler_thread = None
        self._start_scheduler()

    def _start_scheduler(self):
        """Start notification scheduler thread"""
        if self._scheduler_thread is None:
            self._scheduler_thread = threading.Thread(target=self._process_schedule, daemon=True)
            self._scheduler_thread.start()

    def schedule_notification(self, message: NotificationMessage,
                            delay_seconds: int = 0) -> str:
        """Schedule notification for future delivery"""
        delivery_time = datetime.now().timestamp() + delay_seconds
        notification_id = f"notif_{int(datetime.now().timestamp())}_{id(message)}"

        scheduled_notification = {
            'id': notification_id,
            'message': message,
            'delivery_time': delivery_time,
            'scheduled_at': datetime.now().timestamp()
        }

        with self._lock:
            self.scheduled_notifications.append(scheduled_notification)

        log_manager.logger.info(
            "Notification scheduled",
            notification_id=notification_id,
            delay_seconds=delay_seconds,
            delivery_time=datetime.fromtimestamp(delivery_time).isoformat()
        )

        return notification_id

    def cancel_notification(self, notification_id: str) -> bool:
        """Cancel scheduled notification"""
        with self._lock:
            for i, notification in enumerate(self.scheduled_notifications):
                if notification['id'] == notification_id:
                    del self.scheduled_notifications[i]

                    log_manager.logger.info(
                        "Notification cancelled",
                        notification_id=notification_id
                    )
                    return True

        return False

    def _process_schedule(self):
        """Process scheduled notifications"""
        while True:
            try:
                current_time = datetime.now().timestamp()

                with self._lock:
                    ready_notifications = [
                        n for n in self.scheduled_notifications
                        if current_time >= n['delivery_time']
                    ]

                    for notification in ready_notifications:
                        self.scheduled_notifications.remove(notification)
                        # Send in background thread to avoid blocking
                        threading.Thread(
                            target=self.notification_manager.send_notification,
                            args=(notification['message'],),
                            daemon=True
                        ).start()

            except Exception as e:
                log_manager.logger.error("Scheduler error", error=str(e))

            threading.Event().wait(10)  # Check every 10 seconds


# Global notification manager instance
notification_manager = None

def get_notification_manager(config) -> NotificationManager:
    """Get or create global notification manager"""
    global notification_manager
    if notification_manager is None:
        notification_manager = NotificationManager(config)
    return notification_manager
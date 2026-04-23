# ===== WebSocket Consumers for Real-time Notifications =====
# Django Channels implementation for instant notifications

import json
from django.db import models
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


User = get_user_model()


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications
    Each user connects to their personal notification channel
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Create personal notification channel for user
        self.notification_group_name = f'notifications_{self.user.id}'
        
        # Join notification group
        await self.channel_layer.group_add(
            self.notification_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        logger.info(f"User {self.user.email} connected to notifications")
        
        # Send unread count on connection
        await self.send_unread_count()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, 'notification_group_name'):
            await self.channel_layer.group_discard(
                self.notification_group_name,
                self.channel_name
            )
            
            logger.info(f"User {self.user.email} disconnected from notifications")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            action = data.get('action')
            
            if action == 'mark_read':
                notification_id = data.get('notification_id')
                await self.mark_notification_read(notification_id)
                
            elif action == 'mark_all_read':
                await self.mark_all_notifications_read()
                
            elif action == 'get_unread_count':
                await self.send_unread_count()
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
    
    async def notification_message(self, event):
        """
        Handle notification.message event from channel layer
        Send notification to WebSocket
        """
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': event['notification']
        }))
    
    async def unread_count(self, event):
        """Send unread count update"""
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': event['count']
        }))
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark a notification as read"""
        from .models import Notification
        
        try:
            notification = Notification.objects.get(
                notification_id=notification_id,
                user=self.user
            )
            notification.is_read = True
            notification.save()
            
            return True
        except Notification.DoesNotExist:
            return False
    
    @database_sync_to_async
    def mark_all_notifications_read(self):
        """Mark all notifications as read"""
        from .models import Notification
        
        Notification.objects.filter(
            user=self.user,
            is_read=False
        ).exclude(type="message").update(is_read=True)
    
    @database_sync_to_async
    def get_unread_count(self):
        """Get unread notification count"""
        from .models import Notification
        
        return Notification.objects.filter(
            user=self.user,
            is_read=False
        ).exclude(type="message").count()
    
    async def send_unread_count(self):
        """Send current unread count to client"""
        count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': count
        }))


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time chat between students and teachers
    """
    
    async def connect(self):
        """Handle chat connection"""
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Get conversation ID from URL
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'
        
        # Verify user has access to this conversation
        has_access = await self.verify_conversation_access()
        if not has_access:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        logger.info(f"User {self.user.email} joined chat {self.conversation_id}")
        
        # Mark messages as read
        await self.mark_messages_read()
    
    async def disconnect(self, close_code):
        """Handle chat disconnection"""
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            logger.info(f"User {self.user.email} left chat {self.conversation_id}")
    
    async def receive(self, text_data):
        """Handle incoming chat messages"""
        try:
            data = json.loads(text_data)
            message_text = data.get('message')
            
            if not message_text:
                return
            
            # Save message to database
            message = await self.save_message(message_text)
            
            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': {
                        'id': message['id'],
                        'text': message['text'],
                        'sender': message['sender'],
                        'timestamp': message['timestamp'],
                    }
                }
            )
            
        except json.JSONDecodeError:
            logger.error("Invalid JSON received in chat")
        except Exception as e:
            logger.error(f"Error handling chat message: {str(e)}")
    
    async def chat_message(self, event):
        """Send chat message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message']
        }))
    
    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user': event['user']
        }))
    
    @database_sync_to_async
    def verify_conversation_access(self):
        """Verify user has access to this conversation"""
        from .models import Message
        
        # Check if user is part of this conversation
        return Message.objects.filter(
            conversation_id=self.conversation_id
        ).filter(
            models.Q(sender=self.user) | models.Q(recipient=self.user)
        ).exists()
    
    @database_sync_to_async
    def save_message(self, message_text):
        """Save message to database"""
        from .models import Message
        from django.utils import timezone
        
        # Get recipient (other person in conversation)
        # This is simplified - you should implement proper conversation management
        message = Message.objects.create(
            sender=self.user,
            message_text=message_text,
            conversation_id=self.conversation_id,
        )
        
        return {
            'id': str(message.message_id),
            'text': message.message_text,
            'sender': {
                'id': self.user.id,
                'name': self.user.get_full_name(),
                'email': self.user.email,
            },
            'timestamp': message.sent_at.isoformat(),
        }
    
    @database_sync_to_async
    def mark_messages_read(self):
        """Mark all messages in this conversation as read"""
        from .models import Message
        
        Message.objects.filter(
            conversation_id=self.conversation_id,
            recipient=self.user,
            is_read=False
        ).update(is_read=True)


class PresenceConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for user online/offline presence
    """
    
    async def connect(self):
        """Handle presence connection"""
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        self.presence_group = 'presence'
        
        # Join presence group
        await self.channel_layer.group_add(
            self.presence_group,
            self.channel_name
        )
        
        await self.accept()
        
        # Broadcast user is online
        await self.update_user_status('online')
    
    async def disconnect(self, close_code):
        """Handle presence disconnection"""
        # Broadcast user is offline
        await self.update_user_status('offline')
        
        if hasattr(self, 'presence_group'):
            await self.channel_layer.group_discard(
                self.presence_group,
                self.channel_name
            )
    
    async def update_user_status(self, status):
        """Update and broadcast user status"""
        await self.set_user_online_status(status == 'online')
        
        # Broadcast to all in presence group
        await self.channel_layer.group_send(
            self.presence_group,
            {
                'type': 'user_status',
                'user_id': self.user.id,
                'status': status,
            }
        )
    
    async def user_status(self, event):
        """Send user status update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'presence',
            'user_id': event['user_id'],
            'status': event['status'],
        }))
    
    @database_sync_to_async
    def set_user_online_status(self, is_online):
        """Update user's online status in database"""
        # You can add an online_status field to User model
        # or create a separate UserPresence model
        pass


class LiveCallConsumer(AsyncWebsocketConsumer):
    """
    Local signaling channel for project-owned WebRTC live calls.
    """

    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return

        self.call_id = self.scope["url_route"]["kwargs"]["call_id"]
        self.room_group_name = f"live_call_{self.call_id}"

        participant_context = await self.get_participant_context()
        if not participant_context:
            await self.close()
            return

        self.participant_context = participant_context

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        await self.mark_connected()
        peers = await self.get_connected_peers()
        await self.send(
            text_data=json.dumps(
                {
                    "type": "room_state",
                    "call_id": int(self.call_id),
                    "self_id": self.user.id,
                    "peers": peers,
                }
            )
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "peer_joined",
                "user_id": self.user.id,
                "channel_name": self.channel_name,
                "participant": await self.serialize_current_user(),
            },
        )

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.mark_disconnected()
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "peer_left",
                    "user_id": getattr(self.user, "id", None),
                    "channel_name": self.channel_name,
                },
            )
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        action = data.get("action")
        if action == "signal":
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "live_call_signal",
                    "sender_id": self.user.id,
                    "target_id": data.get("target"),
                    "payload": data.get("payload", {}),
                },
            )
        elif action == "presence_state":
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "peer_presence",
                    "sender_id": self.user.id,
                    "payload": data.get("payload", {}),
                },
            )
        elif action == "heartbeat":
            await self.touch_connection()

    async def room_state(self, event):
        await self.send(text_data=json.dumps(event))

    async def live_call_signal(self, event):
        if event.get("target_id") != self.user.id:
            return
        await self.send(
            text_data=json.dumps(
                {
                    "type": "signal",
                    "sender_id": event["sender_id"],
                    "payload": event.get("payload", {}),
                }
            )
        )

    async def peer_joined(self, event):
        if event.get("channel_name") == self.channel_name:
            return
        await self.send(
            text_data=json.dumps(
                {
                    "type": "peer_joined",
                    "participant": event.get("participant", {}),
                }
            )
        )

    async def peer_left(self, event):
        if event.get("channel_name") == self.channel_name:
            return
        await self.send(
            text_data=json.dumps(
                {
                    "type": "peer_left",
                    "user_id": event.get("user_id"),
                }
            )
        )

    async def peer_presence(self, event):
        if event.get("sender_id") == self.user.id:
            return
        await self.send(
            text_data=json.dumps(
                {
                    "type": "peer_presence",
                    "sender_id": event.get("sender_id"),
                    "payload": event.get("payload", {}),
                }
            )
        )

    @database_sync_to_async
    def get_participant_context(self):
        from .models import LiveCallParticipant

        participant = (
            LiveCallParticipant.objects.select_related("live_call", "user")
            .filter(live_call_id=self.call_id, user=self.user)
            .first()
        )
        if not participant:
            return None
        if participant.status not in {"invited", "accepted"}:
            return None

        if participant.status == "invited":
            participant.status = "accepted"
            participant.responded_at = timezone.now()
            participant.save(update_fields=["status", "responded_at"])

        call = participant.live_call
        if call.status == "pending":
            call.status = "active"
            call.answered_at = timezone.now()
            call.save(update_fields=["status", "answered_at"])

        return {"participant_id": participant.participant_id, "call_id": participant.live_call_id}

    @database_sync_to_async
    def mark_connected(self):
        from .models import LiveCallParticipant

        LiveCallParticipant.objects.filter(live_call_id=self.call_id, user=self.user).update(
            joined_at=timezone.now(),
            left_at=None,
            status="accepted",
        )

    @database_sync_to_async
    def mark_disconnected(self):
        from .models import LiveCallParticipant

        LiveCallParticipant.objects.filter(live_call_id=self.call_id, user=self.user).update(
            left_at=timezone.now(),
            joined_at=None,
        )

    @database_sync_to_async
    def touch_connection(self):
        from .models import LiveCallParticipant

        LiveCallParticipant.objects.filter(live_call_id=self.call_id, user=self.user).update(joined_at=timezone.now())

    @database_sync_to_async
    def serialize_current_user(self):
        return {
            "user_id": self.user.id,
            "name": self.user.get_full_name() or self.user.email,
            "avatar": self.user.avatar.url if self.user.avatar else "",
            "role": "teacher" if self.user.is_teacher() else "student",
        }

    @database_sync_to_async
    def get_connected_peers(self):
        from .models import LiveCallParticipant

        peers = (
            LiveCallParticipant.objects.select_related("user")
            .filter(live_call_id=self.call_id, joined_at__isnull=False, status="accepted")
            .exclude(user=self.user)
            .order_by("joined_at")
        )
        return [
            {
                "user_id": peer.user_id,
                "name": peer.user.get_full_name() or peer.user.email,
                "avatar": peer.user.avatar.url if peer.user.avatar else "",
                "role": peer.role,
            }
            for peer in peers
        ]


# Utility function to send notifications via WebSocket
async def send_notification_to_user(user_id, notification_data):
    """
    Send notification to a specific user via WebSocket
    
    Args:
        user_id: User ID
        notification_data: Dict with notification details
    """
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    
    await channel_layer.group_send(
        f'notifications_{user_id}',
        {
            'type': 'notification_message',
            'notification': notification_data
        }
    )

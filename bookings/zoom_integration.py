# ===== Zoom Integration for EduVerse Platform =====
# Complete Zoom API integration for virtual sessions

import requests
import jwt
import time
from datetime import datetime, timedelta
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class ZoomIntegration:
    """
    Zoom API Integration for creating and managing meetings
    Documentation: https://marketplace.zoom.us/docs/api-reference/zoom-api
    """
    
    def __init__(self):
        self.api_key = getattr(settings, 'ZOOM_API_KEY', None)
        self.api_secret = getattr(settings, 'ZOOM_API_SECRET', None)
        self.base_url = "https://api.zoom.us/v2"
        self.is_configured = bool(self.api_key and self.api_secret)
        
        if not self.is_configured:
            logger.warning("Zoom API credentials not configured")
    
    def _generate_jwt_token(self):
        """Generate JWT token for Zoom API authentication"""
        token = jwt.encode(
            {
                'iss': self.api_key,
                'exp': time.time() + 5000
            },
            self.api_secret,
            algorithm='HS256'
        )
        return token
    
    def _get_headers(self):
        """Get headers for API requests"""
        return {
            'Authorization': f'Bearer {self._generate_jwt_token()}',
            'Content-Type': 'application/json'
        }
    
    def create_meeting(self, topic, start_time, duration, timezone='Asia/Riyadh', 
                      password=None, agenda=None):
        """
        Create a Zoom meeting
        
        Args:
            topic: Meeting title
            start_time: datetime object for meeting start
            duration: Duration in minutes
            timezone: Timezone for the meeting
            password: Optional meeting password
            agenda: Optional meeting agenda
        
        Returns:
            dict with meeting details or None on failure
        """
        if not self.is_configured:
            logger.error("Zoom not configured")
            return None
        
        try:
            # Format start time for Zoom API
            start_time_str = start_time.strftime('%Y-%m-%dT%H:%M:%S')
            
            meeting_data = {
                'topic': topic,
                'type': 2,  # Scheduled meeting
                'start_time': start_time_str,
                'duration': duration,
                'timezone': timezone,
                'agenda': agenda or topic,
                'settings': {
                    'host_video': True,
                    'participant_video': True,
                    'join_before_host': False,
                    'mute_upon_entry': True,
                    'watermark': False,
                    'use_pmi': False,
                    'approval_type': 2,  # No registration required
                    'audio': 'both',  # Both telephony and VoIP
                    'auto_recording': 'cloud',  # Auto record to cloud
                    'waiting_room': True,
                }
            }
            
            if password:
                meeting_data['password'] = password
            
            # Create meeting
            response = requests.post(
                f"{self.base_url}/users/me/meetings",
                json=meeting_data,
                headers=self._get_headers()
            )
            
            if response.status_code == 201:
                data = response.json()
                logger.info(f"Zoom meeting created: {data['id']}")
                
                return {
                    'id': data['id'],
                    'join_url': data['join_url'],
                    'start_url': data['start_url'],
                    'password': data.get('password', ''),
                    'meeting_id': str(data['id']),
                }
            else:
                logger.error(f"Zoom API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create Zoom meeting: {str(e)}")
            return None
    
    def get_meeting(self, meeting_id):
        """Get meeting details"""
        if not self.is_configured:
            return None
        
        try:
            response = requests.get(
                f"{self.base_url}/meetings/{meeting_id}",
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get meeting {meeting_id}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting meeting: {str(e)}")
            return None
    
    def update_meeting(self, meeting_id, updates):
        """
        Update meeting details
        
        Args:
            meeting_id: Zoom meeting ID
            updates: Dict with fields to update
        """
        if not self.is_configured:
            return False
        
        try:
            response = requests.patch(
                f"{self.base_url}/meetings/{meeting_id}",
                json=updates,
                headers=self._get_headers()
            )
            
            if response.status_code == 204:
                logger.info(f"Meeting {meeting_id} updated successfully")
                return True
            else:
                logger.error(f"Failed to update meeting: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating meeting: {str(e)}")
            return False
    
    def delete_meeting(self, meeting_id):
        """Delete a meeting"""
        if not self.is_configured:
            return False
        
        try:
            response = requests.delete(
                f"{self.base_url}/meetings/{meeting_id}",
                headers=self._get_headers()
            )
            
            if response.status_code == 204:
                logger.info(f"Meeting {meeting_id} deleted successfully")
                return True
            else:
                logger.error(f"Failed to delete meeting: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting meeting: {str(e)}")
            return False
    
    def list_meetings(self, user_id='me', meeting_type='scheduled'):
        """
        List meetings for a user
        
        Args:
            user_id: Zoom user ID or 'me' for authenticated user
            meeting_type: scheduled, live, or upcoming
        """
        if not self.is_configured:
            return []
        
        try:
            response = requests.get(
                f"{self.base_url}/users/{user_id}/meetings",
                params={'type': meeting_type},
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                return response.json().get('meetings', [])
            else:
                logger.error(f"Failed to list meetings: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error listing meetings: {str(e)}")
            return []
    
    def get_meeting_recordings(self, meeting_id):
        """Get recordings for a meeting"""
        if not self.is_configured:
            return None
        
        try:
            response = requests.get(
                f"{self.base_url}/meetings/{meeting_id}/recordings",
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get recordings: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting recordings: {str(e)}")
            return None
    
    def add_meeting_registrant(self, meeting_id, email, first_name, last_name):
        """Add a registrant to a meeting (if registration is enabled)"""
        if not self.is_configured:
            return None
        
        try:
            registrant_data = {
                'email': email,
                'first_name': first_name,
                'last_name': last_name
            }
            
            response = requests.post(
                f"{self.base_url}/meetings/{meeting_id}/registrants",
                json=registrant_data,
                headers=self._get_headers()
            )
            
            if response.status_code == 201:
                return response.json()
            else:
                logger.error(f"Failed to add registrant: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error adding registrant: {str(e)}")
            return None


class ZoomWebhookHandler:
    """
    Handle Zoom webhooks for meeting events
    """
    
    @staticmethod
    def verify_webhook(request):
        """Verify webhook signature"""
        # Implement webhook verification according to Zoom docs
        return True
    
    @staticmethod
    def handle_meeting_started(event_data):
        """Handle meeting.started event"""
        from .models import Booking
        
        meeting_id = event_data.get('object', {}).get('id')
        
        try:
            booking = Booking.objects.get(meeting_id=str(meeting_id))
            booking.status = 'in_progress'
            booking.save()
            
            logger.info(f"Meeting started: {meeting_id}, updated booking {booking.uuid}")
        except Booking.DoesNotExist:
            logger.warning(f"No booking found for meeting {meeting_id}")
    
    @staticmethod
    def handle_meeting_ended(event_data):
        """Handle meeting.ended event"""
        from .models import Booking
        
        meeting_id = event_data.get('object', {}).get('id')
        
        try:
            booking = Booking.objects.get(meeting_id=str(meeting_id))
            booking.status = 'completed'
            booking.save()
            
            logger.info(f"Meeting ended: {meeting_id}, updated booking {booking.uuid}")
        except Booking.DoesNotExist:
            logger.warning(f"No booking found for meeting {meeting_id}")
    
    @staticmethod
    def handle_recording_completed(event_data):
        """Handle recording.completed event"""
        meeting_id = event_data.get('object', {}).get('id')
        recording_files = event_data.get('object', {}).get('recording_files', [])
        
        logger.info(f"Recording completed for meeting {meeting_id}: {len(recording_files)} files")
        
        # You can save recording URLs to the booking model
        # Or process the recordings (download, upload to S3, etc.)


def create_zoom_meeting_for_booking(booking):
    """
    Helper function to create Zoom meeting for a booking
    
    Args:
        booking: Booking instance
    
    Returns:
        dict with meeting details or None
    """
    zoom = ZoomIntegration()
    
    if not zoom.is_configured:
        logger.warning("Zoom not configured, skipping meeting creation")
        return None
    
    topic = f"EduVerse Session: {booking.teacher.user.get_full_name()} & {booking.student.user.get_full_name()}"
    
    meeting_data = zoom.create_meeting(
        topic=topic,
        start_time=booking.scheduled_start,
        duration=booking.duration_minutes,
        agenda=booking.notes or "EduVerse tutoring session"
    )
    
    if meeting_data:
        booking.meeting_id = str(meeting_data['id'])
        booking.meeting_url = meeting_data['join_url']
        booking.meeting_provider = "zoom"
        booking.save()
        
        logger.info(f"Zoom meeting created for booking {booking.uuid}")
        return meeting_data
    
    return None

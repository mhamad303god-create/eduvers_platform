import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer


class BookingClassroomConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return

        self.booking_room = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"booking_classroom_{self.booking_room}"

        context = await self.get_booking_context()
        if not context:
            await self.close()
            return

        self.booking_id = context["booking_id"]
        self.role = context["role"]

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        peers = await self.get_peers()
        await self.send(
            text_data=json.dumps(
                {
                    "type": "room_state",
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
                "participant": await self.serialize_self(),
            },
        )

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
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
                    "type": "booking_signal",
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

    async def booking_signal(self, event):
        if event.get("target_id") != self.user.id:
            return
        await self.send(text_data=json.dumps({"type": "signal", "sender_id": event["sender_id"], "payload": event.get("payload", {})}))

    async def peer_joined(self, event):
        if event.get("channel_name") == self.channel_name:
            return
        await self.send(text_data=json.dumps({"type": "peer_joined", "participant": event.get("participant", {})}))

    async def peer_left(self, event):
        if event.get("channel_name") == self.channel_name:
            return
        await self.send(text_data=json.dumps({"type": "peer_left", "user_id": event.get("user_id")}))

    async def peer_presence(self, event):
        if event.get("sender_id") == self.user.id:
            return
        await self.send(text_data=json.dumps({"type": "peer_presence", "sender_id": event.get("sender_id"), "payload": event.get("payload", {})}))

    @database_sync_to_async
    def get_booking_context(self):
        from .models import Booking

        booking = (
            Booking.objects.select_related("student__user", "teacher__user")
            .filter(meeting_id=self.booking_room)
            .first()
        )
        if not booking:
            return None
        if booking.student.user_id != self.user.id and booking.teacher.user_id != self.user.id:
            return None
        return {
            "booking_id": booking.booking_id,
            "role": "teacher" if booking.teacher.user_id == self.user.id else "student",
        }

    @database_sync_to_async
    def serialize_self(self):
        return {
            "user_id": self.user.id,
            "name": self.user.get_full_name() or self.user.email,
            "avatar": self.user.avatar.url if self.user.avatar else "",
            "role": self.role,
        }

    @database_sync_to_async
    def get_peers(self):
        from .models import Booking

        booking = Booking.objects.select_related("student__user", "teacher__user").get(meeting_id=self.booking_room)
        peers = []
        for participant in [booking.teacher.user, booking.student.user]:
            if participant.id == self.user.id:
                continue
            peers.append(
                {
                    "user_id": participant.id,
                    "name": participant.get_full_name() or participant.email,
                    "avatar": participant.avatar.url if participant.avatar else "",
                    "role": "teacher" if participant.id == booking.teacher.user_id else "student",
                }
            )
        return peers

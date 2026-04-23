from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0005_contactrequest"),
    ]

    operations = [
        migrations.CreateModel(
            name="LiveCall",
            fields=[
                ("call_id", models.AutoField(primary_key=True, serialize=False)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("topic", models.CharField(blank=True, max_length=255, null=True)),
                ("message", models.TextField(blank=True, null=True)),
                ("room_name", models.CharField(max_length=255, unique=True)),
                ("room_url", models.URLField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("active", "Active"),
                            ("ended", "Ended"),
                            ("cancelled", "Cancelled"),
                            ("rejected", "Rejected"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("is_emergency", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("answered_at", models.DateTimeField(blank=True, null=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                (
                    "initiated_by",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="initiated_calls", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "teacher",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="teacher_live_calls", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "verbose_name": "Live Call",
                "verbose_name_plural": "Live Calls",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="LiveCallParticipant",
            fields=[
                ("participant_id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "role",
                    models.CharField(
                        choices=[("teacher", "Teacher"), ("student", "Student")],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("invited", "Invited"),
                            ("accepted", "Accepted"),
                            ("rejected", "Rejected"),
                            ("cancelled", "Cancelled"),
                            ("missed", "Missed"),
                        ],
                        default="invited",
                        max_length=20,
                    ),
                ),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "live_call",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="participants", to="notifications.livecall"),
                ),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="live_call_participations", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "verbose_name": "Live Call Participant",
                "verbose_name_plural": "Live Call Participants",
                "unique_together": {("live_call", "user")},
            },
        ),
    ]

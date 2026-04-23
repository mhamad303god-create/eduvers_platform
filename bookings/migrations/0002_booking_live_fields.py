from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="meeting_provider",
            field=models.CharField(
                choices=[
                    ("jitsi", "Jitsi Meet"),
                    ("zoom", "Zoom"),
                    ("external", "External"),
                ],
                default="jitsi",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="reminder_sent",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="booking",
            name="reminder_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

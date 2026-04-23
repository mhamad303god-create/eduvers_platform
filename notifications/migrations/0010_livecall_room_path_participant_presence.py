from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0009_message_delete_flags"),
    ]

    operations = [
        migrations.AddField(
            model_name="livecall",
            name="room_path",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="livecallparticipant",
            name="joined_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="livecallparticipant",
            name="left_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

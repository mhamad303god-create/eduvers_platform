from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0008_message_attachment_file"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="deleted_by_sender",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="message",
            name="deleted_by_receiver",
            field=models.BooleanField(default=False),
        ),
    ]

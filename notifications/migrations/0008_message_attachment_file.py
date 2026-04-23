from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0007_livecall_end_reason"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="attachment_file",
            field=models.FileField(blank=True, null=True, upload_to="messages/attachments/%Y/%m/"),
        ),
    ]

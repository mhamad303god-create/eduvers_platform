from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0006_livecall_livecallparticipant"),
    ]

    operations = [
        migrations.AddField(
            model_name="livecall",
            name="end_reason",
            field=models.TextField(blank=True, null=True),
        ),
    ]

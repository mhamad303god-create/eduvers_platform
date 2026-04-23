from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0010_livecall_room_path_participant_presence"),
    ]

    operations = [
        migrations.AddField(
            model_name="livecall",
            name="archived_by_initiator",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="NewsletterSubscription",
            fields=[
                ("subscription_id", models.AutoField(primary_key=True, serialize=False)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("full_name", models.CharField(blank=True, max_length=255, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("subscribed_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="accounts.user")),
            ],
            options={
                "verbose_name": "Newsletter Subscription",
                "verbose_name_plural": "Newsletter Subscriptions",
                "ordering": ["-subscribed_at"],
            },
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mirrors", "0005_video_thumbnail"),
    ]

    operations = [
        migrations.AddField(
            model_name="session",
            name="user_id",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
    ]

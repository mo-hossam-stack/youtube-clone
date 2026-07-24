from django.db import migrations


def set_existing_videos_safe(apps, schema_editor):
    Video = apps.get_model("videos", "Video")
    Video.objects.update(status="safe")


def reverse(apps, schema_editor):
    Video = apps.get_model("videos", "Video")
    Video.objects.update(status="pending")


class Migration(migrations.Migration):

    dependencies = [
        ("videos", "0005_secure_upload_processing"),
    ]

    operations = [
        migrations.RunPython(set_existing_videos_safe, reverse),
    ]

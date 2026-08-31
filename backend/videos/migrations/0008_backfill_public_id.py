from django.db import migrations
from . import _backfill


class Migration(migrations.Migration):

    dependencies = [
        ("videos", "0007_add_public_id"),
    ]

    operations = [
        migrations.RunPython(_backfill.backfill_public_id, _backfill.reverse),
    ]

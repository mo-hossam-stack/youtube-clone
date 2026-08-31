from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("videos", "0008_backfill_public_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="video",
            name="public_id",
            field=models.CharField(max_length=16, unique=True),
        ),
    ]

import secrets

from django.db import transaction
from django.db.utils import IntegrityError

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def generate_public_id(length=8):
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def backfill_public_id(apps, schema_editor):
    Video = apps.get_model("videos", "Video")
    batch_size = 1000
    last_pk = 0

    while True:
        with transaction.atomic():
            batch = list(
                Video.objects.filter(pk__gt=last_pk, public_id__isnull=True)
                .order_by("pk")[:batch_size]
            )
            if not batch:
                break
            for video in batch:
                for attempt in range(10):
                    video.public_id = generate_public_id()
                    try:
                        with transaction.atomic():
                            video.save(update_fields=["public_id"])
                        break
                    except IntegrityError:
                        if attempt == 9:
                            raise
            last_pk = batch[-1].pk


def reverse(apps, schema_editor):
    Video = apps.get_model("videos", "Video")
    Video.objects.all().update(public_id=None)

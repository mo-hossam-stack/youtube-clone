import logging
import os
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage

logger = logging.getLogger("videos.upload")


class QuarantineStorage(FileSystemStorage):
    """Storage backend for quarantine files. Never exposed publicly."""

    def __init__(self):
        from django.conf import settings
        quarantine_dir = str(settings.QUARANTINE_DIR)
        super().__init__(
            location=quarantine_dir,
            base_url=None,
            file_permissions_mode=0o600,
        )

    def url(self, name):
        raise NotImplementedError(
            "Quarantine files must never be served via public URL."
        )


def _get_storage():
    return QuarantineStorage()


def save_to_quarantine(file_obj, storage_name):
    """Write an uploaded file to quarantine storage.

    Args:
        file_obj: Django UploadedFile or file-like object.
        storage_name: UUID-prefixed filename (from sanitize_filename).

    Returns:
        Relative path to the quarantine file (suitable for DB storage).
    """
    from django.conf import settings

    file_obj.seek(0)
    ext = Path(storage_name).suffix or ".tmp"
    quarantine_name = f"{uuid.uuid4().hex}{ext}"

    quarantine_dir = Path(settings.QUARANTINE_DIR)
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    full_path = quarantine_dir / quarantine_name

    with open(full_path, "wb") as f:
        while True:
            chunk = file_obj.read(8192)
            if not chunk:
                break
            f.write(chunk)

    file_obj.seek(0)

    logger.info(
        "quarantine.file_saved",
        extra={
            "quarantine_path": quarantine_name,
            "original_name": storage_name,
            "file_size": os.path.getsize(str(full_path)),
        },
    )

    return quarantine_name


def delete_quarantine_file(quarantine_path):
    """Remove a file from quarantine storage.

    Args:
        quarantine_path: Relative path as stored in Video.quarantine_path.
    """
    if not quarantine_path:
        return

    full_path = Path(settings.QUARANTINE_DIR) / quarantine_path
    try:
        if full_path.exists():
            full_path.unlink()
            logger.info(
                "quarantine.file_deleted",
                extra={"quarantine_path": quarantine_path},
            )
    except OSError as e:
        logger.error(
            "quarantine.delete_failed",
            extra={"quarantine_path": quarantine_path, "error": str(e)},
        )


def get_quarantine_abs_path(quarantine_path):
    """Return the absolute filesystem path for a quarantine file.

    Args:
        quarantine_path: Relative path as stored in Video.quarantine_path.

    Returns:
        Absolute path as string, or None if quarantine_path is empty.
    """
    if not quarantine_path:
        return None
    return str(Path(settings.QUARANTINE_DIR) / quarantine_path)

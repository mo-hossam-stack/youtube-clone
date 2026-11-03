import logging

from django.db import transaction

from ..helpers import upload_thumbnail
from ..models import Video, VideoStatus
from ..quarantine import delete_quarantine_file, save_to_quarantine
from ..tasks import scan_video
from ..validators import normalize_title, validate_video_title

logger = logging.getLogger("videos.upload")


def _enqueue_scan(video_id, quarantine_path):
    try:
        scan_video.delay(video_id)
    except Exception:
        logger.exception(
            "upload.scan_enqueue_failed",
            extra={"video_id": video_id, "quarantine_path": quarantine_path},
        )
        Video.objects.filter(pk=video_id).delete()
        delete_quarantine_file(quarantine_path)
        raise


def _attach_thumbnail(video, video_file, custom_thumbnail):
    if not custom_thumbnail or not custom_thumbnail.startswith("data:image"):
        return

    try:
        base_name = video_file.storage_name.rsplit(".", 1)[0]
        thumb_result = upload_thumbnail(
            file_data=custom_thumbnail,
            file_name=base_name + "_thumb.jpg",
        )
        video.thumbnail_url = thumb_result["url"]
        video.save(update_fields=["thumbnail_url"])
    except Exception:
        logger.warning(
            "Thumbnail upload failed",
            extra={"upload_filename": video_file.name},
        )


def create_video_from_upload(*, user, cleaned_data, video_file, custom_thumbnail=""):
    """Persist a validated upload and enqueue scanning after commit."""
    title = normalize_title(cleaned_data["title"])
    validate_video_title(title)

    quarantine_path = save_to_quarantine(
        video_file,
        video_file.storage_name,
    )

    video = None
    try:
        with transaction.atomic():
            metadata = video_file.metadata
            video = Video(
                user=user,
                title=title,
                description=cleaned_data.get("description", ""),
                original_filename=video_file.name,
                storage_filename=video_file.storage_name,
                original_file_size=video_file.size,
                sha256_hash=video_file.sha256_hash,
                container=metadata["container"],
                codec=metadata["codec"],
                duration=metadata["duration"],
                width=metadata["width"],
                height=metadata["height"],
                status=VideoStatus.PENDING,
                quarantine_path=quarantine_path,
            )
            video.full_clean(exclude=["public_id"])
            video.save()
            transaction.on_commit(
                lambda: _enqueue_scan(video.id, quarantine_path)
            )

        _attach_thumbnail(video, video_file, custom_thumbnail)
        logger.info(
            "upload.queued",
            extra={
                "video_id": video.id,
                "user_id": user.id,
                "file_size": video.original_file_size,
                "sha256": video.sha256_hash[:12],
            },
        )
        return video
    except Exception:
        if video is not None and video.pk:
            Video.objects.filter(pk=video.pk).delete()
        delete_quarantine_file(quarantine_path)
        raise

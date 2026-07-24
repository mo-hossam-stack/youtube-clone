import logging
import os
import socket
import time

import clamd
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import ScanErrorCode, Video, VideoStatus
from .quarantine import delete_quarantine_file, get_quarantine_abs_path

logger = logging.getLogger("videos.upload")


def _fail_video(video, error_code, result_msg, scan_duration_ms=None):
    """Mark a video as FAILED with structured error info."""
    video.status = VideoStatus.FAILED
    video.scan_error_code = error_code
    video.scan_result = result_msg
    video.scanned_at = timezone.now()
    if scan_duration_ms is not None:
        video.scan_duration_ms = scan_duration_ms
    video.save(update_fields=[
        "status", "scan_error_code", "scan_result",
        "scanned_at", "scan_duration_ms",
    ])


def _mark_safe(video, file_id, url, scan_duration_ms):
    """Mark a video as safe after successful scan and ImageKit upload."""
    video.file_id = file_id
    video.video_url = url
    video.status = VideoStatus.SAFE
    video.scan_error_code = ""
    video.scan_result = "clean"
    video.scanned_at = timezone.now()
    video.scan_duration_ms = scan_duration_ms
    video.save(update_fields=[
        "file_id", "video_url", "status", "scan_error_code",
        "scan_result", "scanned_at", "scan_duration_ms",
    ])


def _mark_rejected(video, virus_name, scan_duration_ms):
    """Mark a video as rejected after virus detection."""
    video.status = VideoStatus.REJECTED
    video.scan_error_code = ScanErrorCode.VIRUS_DETECTED
    video.scan_result = f"infected: {virus_name}"
    video.scanned_at = timezone.now()
    video.scan_duration_ms = scan_duration_ms
    video.save(update_fields=[
        "status", "scan_error_code", "scan_result",
        "scanned_at", "scan_duration_ms",
    ])


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scan_video(self, video_id):
    """Scan an uploaded video for viruses using ClamAV.

    Flow:
        1. Lock the video record (select_for_update)
        2. Idempotency guard
        3. Re-validate quarantine file
        4. Dedup check (same hash already SAFE)
        5. ClamAV scan
        6. Upload to ImageKit if clean (transactional)
        7. Update status
    """
    start_time = time.monotonic()

    # --- Step 1: Lock and check state ---
    try:
        with transaction.atomic():
            video = Video.objects.select_for_update().get(id=video_id)

            # Idempotency: already processed
            if video.status == VideoStatus.SAFE:
                logger.info(
                    "scan.idempotent_skip",
                    extra={"video_id": video_id, "status": video.status},
                )
                return {"status": "skipped", "reason": "already_safe"}

            # Already rejected/failed by a previous attempt
            if video.status not in (VideoStatus.PENDING, VideoStatus.SCANNING):
                logger.info(
                    "scan.state_skip",
                    extra={"video_id": video_id, "status": video.status},
                )
                return {"status": "skipped", "reason": f"status={video.status}"}

            # Transition to SCANNING
            video.status = VideoStatus.SCANNING
            video.scanning_started_at = timezone.now()
            video.save(update_fields=["status", "scanning_started_at"])
    except Video.DoesNotExist:
        logger.error(
            "scan.video_not_found", extra={"video_id": video_id}
        )
        return {"status": "error", "reason": "video_not_found"}

    # --- Step 2: Re-validate quarantine file ---
    abs_path = get_quarantine_abs_path(video.quarantine_path)
    if not abs_path or not os.path.exists(abs_path):
        _fail_video(video, ScanErrorCode.FILE_MISSING, "Quarantine file missing")
        logger.error(
            "scan.file_missing",
            extra={"video_id": video_id, "quarantine_path": video.quarantine_path},
        )
        return {"status": "error", "reason": "file_missing"}

    actual_size = os.path.getsize(abs_path)
    if actual_size != video.original_file_size:
        _fail_video(
            video,
            ScanErrorCode.FILE_TAMPERED,
            f"File size mismatch: expected {video.original_file_size}, got {actual_size}",
        )
        logger.warning(
            "scan.file_tampered",
            extra={
                "video_id": video_id,
                "expected_size": video.original_file_size,
                "actual_size": actual_size,
            },
        )
        return {"status": "error", "reason": "file_tampered"}

    # --- Step 3: Dedup check ---
    existing_safe = (
        Video.objects.filter(
            sha256_hash=video.sha256_hash,
            status=VideoStatus.SAFE,
        )
        .exclude(id=video_id)
        .first()
    )

    if existing_safe:
        scan_duration_ms = int((time.monotonic() - start_time) * 1000)
        video.file_id = existing_safe.file_id
        video.video_url = existing_safe.video_url
        video.status = VideoStatus.SAFE
        video.scan_error_code = ""
        video.scan_result = f"duplicate_of:{existing_safe.id}"
        video.scanned_at = timezone.now()
        video.scan_duration_ms = scan_duration_ms
        video.save(update_fields=[
            "file_id", "video_url", "status", "scan_error_code",
            "scan_result", "scanned_at", "scan_duration_ms",
        ])
        delete_quarantine_file(video.quarantine_path)
        logger.info(
            "scan.deduplicated",
            extra={
                "video_id": video_id,
                "existing_id": existing_safe.id,
                "duration_ms": scan_duration_ms,
            },
        )
        return {"status": "safe", "reason": f"duplicate_of:{existing_safe.id}"}

    # --- Step 4: ClamAV scan ---
    scan_duration_ms = None
    try:
        cd = clamd.ClamdNetworkSocket(
            settings.CLAMAV_HOST, settings.CLAMAV_PORT, timeout=settings.CLAMAV_TIMEOUT
        )
        with open(abs_path, "rb") as f:
            scan_start = time.monotonic()
            result = cd.instream(f)
            scan_duration_ms = int((time.monotonic() - scan_start) * 1000)

    except clamd.ConnectionError as e:
        scan_duration_ms = int((time.monotonic() - start_time) * 1000)
        if self.request.retries < self.max_retries:
            logger.warning(
                "scan.connection_error_retrying",
                extra={
                    "video_id": video_id,
                    "attempt": self.request.retries + 1,
                    "max_retries": self.max_retries,
                    "error": str(e),
                },
            )
            video.status = VideoStatus.PENDING
            video.save(update_fields=["status"])
            raise self.retry(exc=e)

        _fail_video(video, ScanErrorCode.CONNECTION_REFUSED, str(e), scan_duration_ms)
        logger.error(
            "scan.failed_connection",
            extra={"video_id": video_id, "error": str(e), "duration_ms": scan_duration_ms},
        )
        return {"status": "failed", "reason": "connection_refused"}

    except (socket.timeout, TimeoutError) as e:
        scan_duration_ms = int((time.monotonic() - start_time) * 1000)
        if self.request.retries < self.max_retries:
            logger.warning(
                "scan.timeout_retrying",
                extra={
                    "video_id": video_id,
                    "attempt": self.request.retries + 1,
                    "max_retries": self.max_retries,
                },
            )
            video.status = VideoStatus.PENDING
            video.save(update_fields=["status"])
            raise self.retry(exc=e)

        _fail_video(video, ScanErrorCode.TIMEOUT, str(e), scan_duration_ms)
        logger.error(
            "scan.failed_timeout",
            extra={"video_id": video_id, "duration_ms": scan_duration_ms},
        )
        return {"status": "failed", "reason": "timeout"}

    except Exception as e:
        scan_duration_ms = int((time.monotonic() - start_time) * 1000)
        if self.request.retries < self.max_retries:
            logger.warning(
                "scan.error_retrying",
                extra={
                    "video_id": video_id,
                    "attempt": self.request.retries + 1,
                    "error": str(e),
                },
            )
            video.status = VideoStatus.PENDING
            video.save(update_fields=["status"])
            raise self.retry(exc=e)

        _fail_video(video, ScanErrorCode.SCANNER_ERROR, str(e), scan_duration_ms)
        logger.error(
            "scan.failed_error",
            extra={"video_id": video_id, "error": str(e), "duration_ms": scan_duration_ms},
        )
        return {"status": "failed", "reason": "scanner_error"}

    # --- Step 5: Process scan result ---
    if result and result.get("stream") and result["stream"][0] == "OK":
        # Clean — upload to ImageKit
        from .helpers import upload_video, delete_video

        try:
            with open(abs_path, "rb") as f:
                file_data = f.read()
            kit_result = upload_video(
                file_data=file_data,
                file_name=video.storage_filename,
            )
        except Exception as e:
            scan_duration_ms = int((time.monotonic() - start_time) * 1000)
            _fail_video(video, ScanErrorCode.UPLOAD_FAILED, str(e), scan_duration_ms)
            logger.error(
                "scan.imagekit_upload_failed",
                extra={"video_id": video_id, "error": str(e)},
            )
            return {"status": "failed", "reason": "upload_failed"}

        # Transactional DB update — if this fails, delete ImageKit orphan
        try:
            _mark_safe(video, kit_result["file_id"], kit_result["url"], scan_duration_ms)
        except Exception as e:
            try:
                delete_video(kit_result["file_id"])
            except Exception:
                logger.error(
                    "scan.imagekit_orphan_not_cleaned",
                    extra={"video_id": video_id, "file_id": kit_result["file_id"]},
                )
            _fail_video(
                video,
                ScanErrorCode.UNKNOWN,
                f"DB update failed after ImageKit upload: {e}",
                scan_duration_ms,
            )
            return {"status": "failed", "reason": "db_update_failed"}

        delete_quarantine_file(video.quarantine_path)
        logger.info(
            "scan.completed_safe",
            extra={"video_id": video_id, "duration_ms": scan_duration_ms},
        )
        return {"status": "safe", "duration_ms": scan_duration_ms}

    else:
        # Infected
        virus_name = "unknown"
        if result and result.get("stream"):
            virus_name = result["stream"][1] if len(result["stream"]) > 1 else "unknown"

        _mark_rejected(video, virus_name, scan_duration_ms)
        delete_quarantine_file(video.quarantine_path)
        logger.warning(
            "scan.virus_detected",
            extra={
                "video_id": video_id,
                "virus": virus_name,
                "duration_ms": scan_duration_ms,
            },
        )
        return {"status": "rejected", "virus": virus_name, "duration_ms": scan_duration_ms}

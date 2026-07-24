import logging
import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from videos.models import Video, VideoStatus
from videos.quarantine import delete_quarantine_file

logger = logging.getLogger("videos.upload")


class Command(BaseCommand):
    help = "Clean up quarantine files and handle orphaned records/files."

    def handle(self, *args, **options):
        now = timezone.now()
        stats = {
            "expired_pending": 0,
            "orphan_files_deleted": 0,
            "orphan_records_marked_failed": 0,
            "old_rejected_cleaned": 0,
            "stale_quarantine_deleted": 0,
        }

        # 1. Pending > 2 hours → FAILED
        expiry_cutoff = now - timedelta(hours=settings.QUARANTINE_EXPIRY_HOURS)
        expired = Video.objects.filter(
            status=VideoStatus.PENDING,
            created_at__lt=expiry_cutoff,
        )
        for video in expired:
            video.status = VideoStatus.FAILED
            video.scan_error_code = "unknown_error"
            video.scan_result = "expired: scan never initiated"
            video.scanned_at = now
            video.save(update_fields=[
                "status", "scan_error_code", "scan_result", "scanned_at",
            ])
            delete_quarantine_file(video.quarantine_path)
            stats["expired_pending"] += 1
            logger.info(
                "cleanup.expired_pending",
                extra={"video_id": video.id},
            )

        # 2. Orphan quarantine files (> 24h old, no matching DB record)
        quarantine_dir = Path(settings.QUARANTINE_DIR)
        if quarantine_dir.exists():
            stale_cutoff = now - timedelta(hours=24)
            for day_dir in quarantine_dir.iterdir():
                if not day_dir.is_dir():
                    continue
                for month_dir in day_dir.iterdir():
                    if not month_dir.is_dir():
                        continue
                    for day_subdir in month_dir.iterdir():
                        if not day_subdir.is_dir():
                            continue
                        for quarantine_file in day_subdir.iterdir():
                            if not quarantine_file.is_file():
                                continue
                            # Check if any DB record references this file
                            rel_path = str(
                                quarantine_file.relative_to(quarantine_dir)
                            )
                            exists_in_db = Video.objects.filter(
                                quarantine_path=rel_path
                            ).exists()
                            if not exists_in_db:
                                # Check file age
                                mtime = timezone.datetime.fromtimestamp(
                                    quarantine_file.stat().st_mtime,
                                    tz=timezone.get_current_timezone(),
                                )
                                if mtime < stale_cutoff:
                                    quarantine_file.unlink()
                                    stats["stale_quarantine_deleted"] += 1
                                    logger.info(
                                        "cleanup.stale_quarantine_deleted",
                                        extra={"path": rel_path},
                                    )

        # 3. Orphan DB records (quarantine_path set but file missing)
        videos_with_quarantine = Video.objects.filter(
            quarantine_path__isnull=False,
        ).exclude(quarantine_path="")
        for video in videos_with_quarantine:
            abs_path = quarantine_dir / video.quarantine_path
            if not abs_path.exists():
                if video.status in (VideoStatus.PENDING, VideoStatus.SCANNING):
                    video.status = VideoStatus.FAILED
                    video.scan_error_code = "file_missing"
                    video.scan_result = "Quarantine file missing after worker restart"
                    video.scanned_at = now
                    video.save(update_fields=[
                        "status", "scan_error_code", "scan_result", "scanned_at",
                    ])
                    stats["orphan_records_marked_failed"] += 1
                    logger.warning(
                        "cleanup.orphan_record",
                        extra={"video_id": video.id, "quarantine_path": video.quarantine_path},
                    )

        # 4. Old rejected videos (> 7 days) — delete quarantine files
        rejected_cutoff = now - timedelta(days=7)
        old_rejected = Video.objects.filter(
            status=VideoStatus.REJECTED,
            scanned_at__lt=rejected_cutoff,
        ).exclude(quarantine_path="")
        for video in old_rejected:
            delete_quarantine_file(video.quarantine_path)
            video.quarantine_path = ""
            video.save(update_fields=["quarantine_path"])
            stats["old_rejected_cleaned"] += 1

        self.stdout.write(self.style.SUCCESS(
            f"Cleanup complete: {stats}"
        ))
        logger.info("cleanup.complete", extra=stats)

import os
import tempfile
import time
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from celery.contrib.testing.worker import start_worker
from django.contrib.auth.models import User
from django.test import TransactionTestCase, override_settings

from config.celery import app
from .models import Video, VideoStatus
from .tasks import scan_video

RUN_INTEGRATION = os.environ.get("RUN_INTEGRATION") == "1"


@skipUnless(RUN_INTEGRATION, "set RUN_INTEGRATION=1 (make test-integration)")
@skipUnless(os.environ.get("REDIS_URL"), "REDIS_URL is required for the worker integration test")
class ScanWorkerIntegrationTests(TransactionTestCase):
    def test_worker_processes_scan_task(self):
        with tempfile.TemporaryDirectory() as quarantine_dir:
            data = b"clean integration test payload"
            path = Path(quarantine_dir) / "clip.mp4"
            path.write_bytes(data)

            user = User.objects.create_user(username="integrationuser", password="pass1234")
            video = Video.objects.create(
                user=user,
                title="Integration video",
                original_filename="clip.mp4",
                storage_filename="clip.mp4",
                original_file_size=len(data),
                sha256_hash="b" * 64,
                container="mp4",
                codec="h264",
                duration=1,
                width=640,
                height=480,
                status=VideoStatus.PENDING,
                quarantine_path="clip.mp4",
            )

            with override_settings(QUARANTINE_DIR=quarantine_dir):
                with patch(
                    "videos.helpers.upload_video",
                    return_value={
                        "file_id": "integration-file",
                        "url": "https://cdn.example.com/integration.mp4",
                    },
                ):
                    with start_worker(app, perform_ping_check=False):
                        scan_video.delay(video.id)
                        deadline = time.monotonic() + 30
                        while time.monotonic() < deadline:
                            video.refresh_from_db()
                            if video.status in {
                                VideoStatus.SAFE,
                                VideoStatus.REJECTED,
                                VideoStatus.FAILED,
                            }:
                                break
                            time.sleep(0.2)

            video.refresh_from_db()
            self.assertEqual(video.status, VideoStatus.SAFE)
            self.assertEqual(video.file_id, "integration-file")
            self.assertFalse(path.exists())

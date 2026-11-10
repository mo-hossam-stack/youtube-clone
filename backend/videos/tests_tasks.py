import tempfile
from pathlib import Path
from unittest.mock import patch

import clamd
from celery.exceptions import Retry
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import ScanErrorCode, Video, VideoStatus
from .tasks import scan_video


class ScanTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="scanuser", password="pass1234")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.quarantine_dir = self.temp_dir.name

    def _video(self, *, data=b"clean video bytes", status=VideoStatus.PENDING):
        path = Path(self.quarantine_dir) / "clip.mp4"
        path.write_bytes(data)
        video = Video.objects.create(
            user=self.user,
            title="Scan test video",
            original_filename="clip.mp4",
            storage_filename="clip.mp4",
            original_file_size=len(data),
            sha256_hash="a" * 64,
            container="mp4",
            codec="h264",
            duration=1,
            width=640,
            height=480,
            status=status,
            quarantine_path="clip.mp4",
        )
        return video, path

    def _run(self, video):
        return scan_video.apply(args=[video.id]).get()

    def test_clean_scan_marks_safe_and_deletes_quarantine(self):
        video, path = self._video()
        with override_settings(QUARANTINE_DIR=self.quarantine_dir):
            with patch("videos.tasks.clamd.ClamdNetworkSocket") as scanner:
                scanner.return_value.instream.return_value = {"stream": ["OK", None]}
                with patch(
                    "videos.helpers.upload_video",
                    return_value={
                        "file_id": "file-1",
                        "url": "https://cdn.example.com/video.mp4",
                    },
                ):
                    result = self._run(video)

        video.refresh_from_db()
        self.assertEqual(result["status"], "safe")
        self.assertEqual(video.status, VideoStatus.SAFE)
        self.assertEqual(video.file_id, "file-1")
        self.assertEqual(video.scan_result, "clean")
        self.assertFalse(path.exists())

    def test_infected_scan_is_rejected_and_deletes_quarantine(self):
        video, path = self._video()
        with override_settings(QUARANTINE_DIR=self.quarantine_dir):
            with patch("videos.tasks.clamd.ClamdNetworkSocket") as scanner:
                scanner.return_value.instream.return_value = {
                    "stream": ["FOUND", "Eicar-Test-Signature"]
                }
                result = self._run(video)

        video.refresh_from_db()
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(video.status, VideoStatus.REJECTED)
        self.assertEqual(video.scan_error_code, ScanErrorCode.VIRUS_DETECTED)
        self.assertIn("Eicar", video.scan_result)
        self.assertFalse(path.exists())

    def test_imagekit_failure_marks_failed_and_keeps_quarantine(self):
        video, path = self._video()
        with override_settings(QUARANTINE_DIR=self.quarantine_dir):
            with patch("videos.tasks.clamd.ClamdNetworkSocket") as scanner:
                scanner.return_value.instream.return_value = {"stream": ["OK", None]}
                with patch(
                    "videos.helpers.upload_video",
                    side_effect=RuntimeError("imagekit down"),
                ):
                    result = self._run(video)

        video.refresh_from_db()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(video.status, VideoStatus.FAILED)
        self.assertEqual(video.scan_error_code, ScanErrorCode.UPLOAD_FAILED)
        self.assertTrue(path.exists())

    def test_clamav_connection_error_schedules_retry(self):
        video, path = self._video()
        with override_settings(QUARANTINE_DIR=self.quarantine_dir):
            with patch("videos.tasks.clamd.ClamdNetworkSocket") as scanner:
                scanner.return_value.instream.side_effect = clamd.ConnectionError("down")
                with self.assertRaises(Retry):
                    scan_video.apply(args=[video.id], throw=True)

        video.refresh_from_db()
        self.assertEqual(video.status, VideoStatus.PENDING)
        self.assertTrue(path.exists())

    def test_missing_quarantine_file_marks_failed(self):
        video, path = self._video()
        path.unlink()
        with override_settings(QUARANTINE_DIR=self.quarantine_dir):
            result = self._run(video)

        video.refresh_from_db()
        self.assertEqual(result["status"], "error")
        self.assertEqual(video.status, VideoStatus.FAILED)
        self.assertEqual(video.scan_error_code, ScanErrorCode.FILE_MISSING)

    def test_tampered_quarantine_file_marks_failed(self):
        video, path = self._video()
        path.write_bytes(b"different length")
        with override_settings(QUARANTINE_DIR=self.quarantine_dir):
            result = self._run(video)

        video.refresh_from_db()
        self.assertEqual(result["status"], "error")
        self.assertEqual(video.status, VideoStatus.FAILED)
        self.assertEqual(video.scan_error_code, ScanErrorCode.FILE_TAMPERED)

    def test_duplicate_hash_reuses_existing_safe_video(self):
        existing = Video.objects.create(
            user=self.user,
            title="Existing video",
            sha256_hash="a" * 64,
            status=VideoStatus.SAFE,
            file_id="existing-file",
            video_url="https://cdn.example.com/existing.mp4",
        )
        video, path = self._video()
        with override_settings(QUARANTINE_DIR=self.quarantine_dir):
            with patch("videos.tasks.clamd.ClamdNetworkSocket") as scanner:
                result = self._run(video)

        video.refresh_from_db()
        scanner.assert_not_called()
        self.assertEqual(result["status"], "safe")
        self.assertEqual(video.status, VideoStatus.SAFE)
        self.assertEqual(video.file_id, existing.file_id)
        self.assertIn(f"duplicate_of:{existing.id}", video.scan_result)
        self.assertFalse(path.exists())

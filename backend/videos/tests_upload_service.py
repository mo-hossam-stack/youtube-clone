import io
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TransactionTestCase, override_settings

from .models import Video, VideoStatus
from .services.upload import create_video_from_upload


class DummyVideoFile(io.BytesIO):
    def __init__(self):
        super().__init__(b"fake video bytes")
        self.name = "clip.mp4"
        self.storage_name = "clip_storage.mp4"
        self.size = len(self.getvalue())
        self.sha256_hash = "a" * 64
        self.metadata = {
            "container": "mp4",
            "codec": "h264",
            "duration": 1,
            "width": 640,
            "height": 480,
        }


class CreateVideoFromUploadTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="serviceuser",
            password="pass1234",
        )
        self.cleaned_data = {
            "title": "  A valid title  ",
            "description": "Description",
        }

    def test_creates_video_and_enqueues_scan_after_commit(self):
        with tempfile.TemporaryDirectory() as quarantine_dir:
            with override_settings(QUARANTINE_DIR=quarantine_dir):
                with patch(
                    "videos.services.upload.scan_video.delay",
                ) as delay:
                    video = create_video_from_upload(
                        user=self.user,
                        cleaned_data=self.cleaned_data,
                        video_file=DummyVideoFile(),
                    )

                self.assertEqual(video.title, "A valid title")
                self.assertEqual(video.status, VideoStatus.PENDING)
                self.assertTrue(
                    (Path(quarantine_dir) / video.quarantine_path).exists(),
                )
                delay.assert_called_once_with(video.id)

    def test_enqueue_failure_removes_video_and_quarantine(self):
        with tempfile.TemporaryDirectory() as quarantine_dir:
            with override_settings(QUARANTINE_DIR=quarantine_dir):
                with patch(
                    "videos.services.upload.scan_video.delay",
                    side_effect=RuntimeError("broker down"),
                ):
                    with self.assertRaises(RuntimeError):
                        create_video_from_upload(
                            user=self.user,
                            cleaned_data=self.cleaned_data,
                            video_file=DummyVideoFile(),
                        )

                self.assertEqual(Video.objects.count(), 0)
                self.assertEqual(list(Path(quarantine_dir).iterdir()), [])

    def test_db_failure_removes_quarantine(self):
        with tempfile.TemporaryDirectory() as quarantine_dir:
            with override_settings(QUARANTINE_DIR=quarantine_dir):
                with patch(
                    "videos.services.upload.Video.full_clean",
                    side_effect=ValidationError("invalid"),
                ):
                    with self.assertRaises(ValidationError):
                        create_video_from_upload(
                            user=self.user,
                            cleaned_data=self.cleaned_data,
                            video_file=DummyVideoFile(),
                        )

                self.assertEqual(Video.objects.count(), 0)
                self.assertEqual(list(Path(quarantine_dir).iterdir()), [])

    def test_thumbnail_failure_is_non_fatal(self):
        with tempfile.TemporaryDirectory() as quarantine_dir:
            with override_settings(QUARANTINE_DIR=quarantine_dir):
                with patch(
                    "videos.services.upload.scan_video.delay",
                ):
                    with patch(
                        "videos.services.upload.upload_thumbnail",
                        side_effect=RuntimeError("imagekit down"),
                    ):
                        video = create_video_from_upload(
                            user=self.user,
                            cleaned_data=self.cleaned_data,
                            video_file=DummyVideoFile(),
                            custom_thumbnail="data:image/png;base64,abc",
                        )

                self.assertTrue(Video.objects.filter(pk=video.pk).exists())
                self.assertEqual(video.thumbnail_url, "")

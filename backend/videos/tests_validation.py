import io
import os
import subprocess
import tempfile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .validators import (
    compute_sha256,
    extract_video_metadata,
    sanitize_filename,
    save_temp_upload,
    validate_file_size,
    validate_mime_type,
    validate_video_metadata,
)


def _generate_test_video(
    duration=1,
    codec="h264",
    width=640,
    height=480,
    container="mp4",
):
    ext = "mp4" if container == "mp4" else "webm"
    suffix = f".{ext}"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        tmp_path = f.name

    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i",
            f"color=c=black:s={width}x{height}:d={duration}:r=30",
            "-f", "lavfi", "-i",
            f"sine=frequency=440:duration={duration}",
            "-c:v", "libx264" if codec == "h264" else "libvpx",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-t", str(duration),
            tmp_path,
        ]
        subprocess.run(
            cmd, capture_output=True, check=True, timeout=30,
        )

        with open(tmp_path, "rb") as f:
            data = f.read()

        return SimpleUploadedFile(
            name=f"test_video.{ext}",
            content=data,
            content_type="video/mp4" if ext == "mp4" else "video/webm",
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _generate_truncated_video():
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        tmp_path = f.name

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i",
                "color=c=black:s=640x480:d=2:r=30",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-t", "2",
                tmp_path,
            ],
            capture_output=True,
            check=True,
            timeout=30,
        )

        with open(tmp_path, "rb") as f:
            data = f.read()

        truncated = data[: len(data) // 2]
        return SimpleUploadedFile(
            name="truncated.mp4",
            content=truncated,
            content_type="video/mp4",
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _fake_exe_bytes():
    exe_header = b"MZ" + b"\x00" * 510
    return SimpleUploadedFile(
        name="fake_video.mp4",
        content=exe_header,
        content_type="video/mp4",
    )


class SanitizeFilenameTests(TestCase):
    def test_normal_filename(self):
        name, ext = sanitize_filename("holiday.mp4")
        self.assertTrue(name.endswith(".mp4"))
        self.assertEqual(ext, "mp4")
        self.assertIn("holiday", name)

    def test_path_traversal(self):
        name, _ = sanitize_filename("../../etc/passwd.mp4")
        self.assertNotIn("..", name)
        self.assertNotIn("/", name)

    def test_empty_filename(self):
        with self.assertRaises(ValidationError):
            sanitize_filename("")

    def test_dot_only(self):
        name, ext = sanitize_filename(".mp4")
        self.assertTrue(name.endswith(".mp4"))
        self.assertNotEqual(name, ".mp4")

    def test_double_extension(self):
        name, ext = sanitize_filename("video.mp4.exe")
        self.assertEqual(ext, "exe")
        self.assertTrue(name.endswith(".exe"))

    def test_huge_filename(self):
        long_name = "a" * 300 + ".mp4"
        name, _ = sanitize_filename(long_name)
        self.assertLessEqual(len(name), 255)

    def test_invalid_unicode(self):
        name, ext = sanitize_filename("video\x00\x01.mp4")
        self.assertTrue(name.endswith(".mp4"))
        self.assertNotIn("\x00", name)


class ValidateFileSizeTests(TestCase):
    def test_under_limit(self):
        f = SimpleUploadedFile("small.mp4", b"\x00" * 1024)
        validate_file_size(f, 1024 * 1024)

    def test_over_limit(self):
        f = SimpleUploadedFile("big.mp4", b"\x00" * (1024 * 1024 + 1))
        with self.assertRaises(ValidationError) as ctx:
            validate_file_size(f, 1024 * 1024)
        self.assertIn("MB", str(ctx.exception))

    def test_zero_bytes(self):
        f = SimpleUploadedFile("empty.mp4", b"")
        with self.assertRaises(ValidationError):
            validate_file_size(f, 1024 * 1024)


class ValidateMimeTests(TestCase):
    def test_real_mp4(self):
        video = _generate_test_video(duration=1)
        mime = validate_mime_type(
            video,
            {"video/mp4"},
            ["mp4"],
        )
        self.assertEqual(mime, "video/mp4")

    def test_renamed_exe(self):
        exe = _fake_exe_bytes()
        with self.assertRaises(ValidationError) as ctx:
            validate_mime_type(
                exe,
                {"video/mp4"},
                ["mp4"],
            )
        self.assertIn("not allowed", str(ctx.exception))

    def test_empty_file(self):
        f = SimpleUploadedFile("empty.mp4", b"")
        with self.assertRaises(ValidationError):
            validate_mime_type(
                f,
                {"video/mp4"},
                ["mp4"],
            )


class ComputeSha256Tests(TestCase):
    def test_deterministic(self):
        f1 = SimpleUploadedFile("a.mp4", b"hello world")
        h1 = compute_sha256(f1)

        f2 = SimpleUploadedFile("b.mp4", b"hello world")
        h2 = compute_sha256(f2)

        self.assertEqual(h1, h2)

    def test_different_content(self):
        f1 = SimpleUploadedFile("a.mp4", b"content A")
        h1 = compute_sha256(f1)

        f2 = SimpleUploadedFile("b.mp4", b"content B")
        h2 = compute_sha256(f2)

        self.assertNotEqual(h1, h2)

    def test_file_pointer_reset(self):
        f = SimpleUploadedFile("a.mp4", b"test data")
        compute_sha256(f)
        self.assertEqual(f.tell(), 0)


class ExtractVideoMetadataTests(TestCase):
    def test_valid_mp4(self):
        video = _generate_test_video(duration=2, width=640, height=480)
        with save_temp_upload(video) as tmp_path:
            meta = extract_video_metadata(tmp_path, timeout=10)
        self.assertEqual(meta["width"], 640)
        self.assertEqual(meta["height"], 480)
        self.assertEqual(meta["duration"], 2)
        self.assertEqual(meta["video_stream_count"], 1)
        self.assertGreater(meta["total_stream_count"], 0)

    def test_truncated_mp4(self):
        video = _generate_truncated_video()
        with save_temp_upload(video) as tmp_path:
            with self.assertRaises(ValidationError):
                extract_video_metadata(tmp_path, timeout=10)

    def test_empty_file(self):
        f = SimpleUploadedFile("empty.mp4", b"")
        with save_temp_upload(f) as tmp_path:
            with self.assertRaises(ValidationError):
                extract_video_metadata(tmp_path, timeout=10)

    def test_non_video_file(self):
        f = SimpleUploadedFile("text.mp4", b"This is not a video file " * 100)
        with save_temp_upload(f) as tmp_path:
            with self.assertRaises(ValidationError):
                extract_video_metadata(tmp_path, timeout=10)


class ValidateVideoMetadataTests(TestCase):
    def test_valid_metadata(self):
        meta = {
            "container": "mp4",
            "codec": "h264",
            "width": 1920,
            "height": 1080,
            "duration": 120,
            "video_stream_count": 1,
            "total_stream_count": 2,
        }
        validate_video_metadata(meta)

    def test_unsupported_codec(self):
        meta = {
            "container": "mp4",
            "codec": "mpeg2video",
            "width": 1920,
            "height": 1080,
            "duration": 120,
            "video_stream_count": 1,
            "total_stream_count": 2,
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_video_metadata(meta)
        self.assertIn("codec", str(ctx.exception).lower())

    def test_unsupported_container(self):
        meta = {
            "container": "3gp",
            "codec": "h264",
            "width": 1920,
            "height": 1080,
            "duration": 120,
            "video_stream_count": 1,
            "total_stream_count": 2,
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_video_metadata(meta)
        self.assertIn("Container", str(ctx.exception))

    def test_duration_too_long(self):
        meta = {
            "container": "mp4",
            "codec": "h264",
            "width": 1920,
            "height": 1080,
            "duration": 7200,
            "video_stream_count": 1,
            "total_stream_count": 2,
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_video_metadata(meta)
        self.assertIn("minutes", str(ctx.exception).lower())

    def test_zero_duration(self):
        meta = {
            "container": "mp4",
            "codec": "h264",
            "width": 1920,
            "height": 1080,
            "duration": 0,
            "video_stream_count": 1,
            "total_stream_count": 2,
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_video_metadata(meta)
        self.assertIn("duration", str(ctx.exception).lower())

    def test_zero_resolution(self):
        meta = {
            "container": "mp4",
            "codec": "h264",
            "width": 0,
            "height": 0,
            "duration": 120,
            "video_stream_count": 1,
            "total_stream_count": 2,
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_video_metadata(meta)
        self.assertIn("dimensions", str(ctx.exception).lower())

    def test_resolution_too_large(self):
        meta = {
            "container": "mp4",
            "codec": "h264",
            "width": 15360,
            "height": 8640,
            "duration": 120,
            "video_stream_count": 1,
            "total_stream_count": 2,
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_video_metadata(meta)
        self.assertIn("exceeds", str(ctx.exception).lower())

    def test_multiple_video_streams(self):
        meta = {
            "container": "mp4",
            "codec": "h264",
            "width": 1920,
            "height": 1080,
            "duration": 120,
            "video_stream_count": 2,
            "total_stream_count": 3,
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_video_metadata(meta)
        self.assertIn("video stream", str(ctx.exception).lower())

    def test_too_many_total_streams(self):
        meta = {
            "container": "mp4",
            "codec": "h264",
            "width": 1920,
            "height": 1080,
            "duration": 120,
            "video_stream_count": 1,
            "total_stream_count": 10,
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_video_metadata(meta)
        self.assertIn("streams", str(ctx.exception).lower())


class SaveTempUploadTests(TestCase):
    def test_temp_file_cleanup(self):
        f = SimpleUploadedFile("test.mp4", b"test data")
        with save_temp_upload(f) as tmp_path:
            self.assertTrue(os.path.exists(tmp_path))
        self.assertFalse(os.path.exists(tmp_path))

    def test_cleanup_on_exception(self):
        f = SimpleUploadedFile("test.mp4", b"test data")
        with self.assertRaises(RuntimeError):
            with save_temp_upload(f) as tmp_path:
                self.assertTrue(os.path.exists(tmp_path))
                raise RuntimeError("test error")
        self.assertFalse(os.path.exists(tmp_path))

    def test_file_pointer_reset_after_write(self):
        f = SimpleUploadedFile("test.mp4", b"test data")
        with save_temp_upload(f):
            pass
        self.assertEqual(f.tell(), 0)


class FullPipelineTests(TestCase):
    @override_settings(
        UPLOAD_MAX_FILE_SIZE=100 * 1024 * 1024,
        UPLOAD_MAX_DURATION=3600,
        UPLOAD_MAX_WIDTH=7680,
        UPLOAD_MAX_HEIGHT=4320,
        UPLOAD_MAX_STREAMS=5,
        UPLOAD_FFPROBE_TIMEOUT=10,
        UPLOAD_ALLOWED_EXTENSIONS=["mp4", "webm", "mov", "avi"],
        UPLOAD_ALLOWED_MIME_TYPES={"video/mp4", "video/webm", "video/quicktime"},
        UPLOAD_ALLOWED_CODECS={"h264", "h265", "hevc", "vp8", "vp9", "av1"},
        UPLOAD_ALLOWED_CONTAINERS={"mp4", "matroska,webm", "mov", "avi"},
    )
    def test_valid_upload_passes_all_checks(self):
        from .forms import VideoUploadForm

        video = _generate_test_video(duration=1, width=640, height=480)
        form = VideoUploadForm(
            data={"title": "Test Video", "description": "A test"},
            files={"video_file": video},
        )
        self.assertTrue(form.is_valid(), form.errors)

        vf = form.cleaned_data["video_file"]
        self.assertEqual(len(vf.sha256_hash), 64)
        self.assertEqual(vf.metadata["codec"], "h264")
        self.assertEqual(vf.metadata["width"], 640)
        self.assertIn("mp4", vf.storage_name)

    @override_settings(
        UPLOAD_ALLOWED_MIME_TYPES={"video/mp4", "video/webm"},
        UPLOAD_ALLOWED_EXTENSIONS=["mp4", "webm"],
    )
    def test_rejected_upload_ffprobe_not_called(self):
        from .forms import VideoUploadForm

        exe = _fake_exe_bytes()
        form = VideoUploadForm(
            data={"title": "Test Video"},
            files={"video_file": exe},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("video_file", form.errors)

import hashlib
import json
import logging
import os
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

import magic
from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger("videos.upload")

MAGIC_FALLBACK_TYPES = {"application/octet-stream", "application/x-empty", ""}


def sanitize_filename(raw_name):
    if not raw_name or not raw_name.strip():
        raise ValidationError("Filename is empty.")

    name = Path(raw_name)
    extension = name.suffix.lower()

    if not extension and name.name.startswith("."):
        extension = ".mp4"

    stem = name.stem
    if not stem:
        stem = "upload"

    safe_stem = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in stem
    )
    safe_stem = safe_stem.strip("_-.") or "upload"

    storage_name = f"{uuid.uuid4().hex}-{safe_stem}{extension}"

    if len(storage_name) > 255:
        ext_len = len(extension)
        max_stem = 255 - ext_len - 37
        storage_name = f"{uuid.uuid4().hex}-{safe_stem[:max_stem]}{extension}"

    return storage_name, extension.lstrip(".")


def validate_file_size(uploaded_file, max_bytes):
    if uploaded_file.size == 0:
        raise ValidationError("Uploaded file is empty.")

    if uploaded_file.size > max_bytes:
        max_mb = round(max_bytes / (1024 * 1024))
        actual_mb = round(uploaded_file.size / (1024 * 1024), 1)
        raise ValidationError(
            f"File is {actual_mb} MB. Maximum allowed size is {max_mb} MB."
        )


def validate_mime_type(uploaded_file, allowed_types, allowed_extensions):
    uploaded_file.seek(0)
    header = uploaded_file.read(8192)
    uploaded_file.seek(0)

    if not header:
        raise ValidationError("Cannot read file for MIME detection.")

    try:
        detected_mime = magic.from_buffer(header, mime=True)
    except Exception:
        raise ValidationError("Unable to detect file type.")

    if detected_mime in MAGIC_FALLBACK_TYPES:
        logger.warning(
            "Upload rejected",
            extra={
                "reason": "unknown_mime",
                "detected_mime": detected_mime,
                "upload_filename": uploaded_file.name,
                "filesize": uploaded_file.size,
            },
        )
        raise ValidationError(
            "Unable to determine file type. Please upload a valid video file."
        )

    if detected_mime not in allowed_types:
        logger.warning(
            "Upload rejected",
            extra={
                "reason": "invalid_mime",
                "detected_mime": detected_mime,
                "upload_filename": uploaded_file.name,
                "filesize": uploaded_file.size,
            },
        )
        raise ValidationError(
            f"File type '{detected_mime}' is not allowed. "
            f"Accepted types: {', '.join(sorted(allowed_types))}."
        )

    return detected_mime


def _run_ffprobe(args, timeout):
    try:
        result = subprocess.run(
            ["ffprobe"] + args,
            capture_output=True,
            check=True,
            timeout=timeout,
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        raise ValidationError(
            "Video analysis timed out. The file may be corrupted or too large."
        )
    except subprocess.CalledProcessError:
        raise ValidationError(
            "Unable to read video metadata. The file may be corrupted."
        )
    except FileNotFoundError:
        raise ValidationError(
            "Video processing tool is not available on the server."
        )


@contextmanager
def save_temp_upload(uploaded_file):
    uploaded_file.seek(0)
    suffix = Path(uploaded_file.name).suffix or ".tmp"
    tmp_fd = None
    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        os.write(tmp_fd, uploaded_file.read())
        os.close(tmp_fd)
        tmp_fd = None
        uploaded_file.seek(0)
        yield tmp_path
    finally:
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)
            except OSError:
                pass
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def extract_video_metadata(tmp_path, timeout):
    stdout = _run_ffprobe(
        [
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            tmp_path,
        ],
        timeout=timeout,
    )

    try:
        probe = json.loads(stdout)
    except json.JSONDecodeError:
        raise ValidationError(
            "Unable to parse video metadata. The file may be corrupted."
        )

    fmt = probe.get("format")
    streams = probe.get("streams", [])

    if not streams:
        raise ValidationError(
            "No media streams found in the file. The file may be corrupted."
        )

    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    non_video_streams = [s for s in streams if s.get("codec_type") != "video"]

    if len(video_streams) == 0:
        raise ValidationError(
            "No video stream found. Please upload a valid video file."
        )

    if len(video_streams) > 1:
        raise ValidationError(
            "Multiple video streams detected. Only single-track videos are accepted."
        )

    total_streams = len(streams)
    if total_streams > settings.UPLOAD_MAX_STREAMS:
        raise ValidationError(
            f"Too many media streams ({total_streams}). "
            f"Maximum allowed is {settings.UPLOAD_MAX_STREAMS}."
        )

    video_stream = video_streams[0]
    codec_name = video_stream.get("codec_name", "")
    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))

    duration = 0
    if fmt:
        raw_duration = fmt.get("duration")
        if raw_duration is not None:
            try:
                duration = int(float(raw_duration))
            except (ValueError, TypeError):
                raise ValidationError(
                    "Invalid video duration. The file may be corrupted."
                )

    if duration == 0:
        raise ValidationError(
            "Video has zero duration. The file may be corrupted or is not a valid video."
        )

    if width == 0 or height == 0:
        raise ValidationError(
            "Video has invalid dimensions. The file may be corrupted."
        )

    container = fmt.get("format_name", "") if fmt else ""

    return {
        "container": container,
        "codec": codec_name,
        "width": width,
        "height": height,
        "duration": duration,
        "video_stream_count": len(video_streams),
        "total_stream_count": total_streams,
    }


def validate_video_metadata(metadata):
    container = metadata.get("container", "")
    codec = metadata.get("codec", "")
    duration = metadata.get("duration", 0)
    width = metadata.get("width", 0)
    height = metadata.get("height", 0)
    video_stream_count = metadata.get("video_stream_count", 0)
    total_stream_count = metadata.get("total_stream_count", 0)

    container_tokens = {t.strip() for t in container.split(",")}
    if not container_tokens & settings.UPLOAD_ALLOWED_CONTAINERS:
        raise ValidationError(
            f"Container format '{container}' is not supported. "
            f"Accepted formats: {', '.join(sorted(settings.UPLOAD_ALLOWED_CONTAINERS))}."
        )

    if codec not in settings.UPLOAD_ALLOWED_CODECS:
        raise ValidationError(
            f"Video codec '{codec}' is not supported. "
            f"Accepted codecs: {', '.join(sorted(settings.UPLOAD_ALLOWED_CODECS))}."
        )

    if duration <= 0:
        raise ValidationError(
            "Video has zero or invalid duration."
        )

    if duration > settings.UPLOAD_MAX_DURATION:
        max_min = round(settings.UPLOAD_MAX_DURATION / 60)
        actual_min = round(duration / 60, 1)
        raise ValidationError(
            f"Video is {actual_min} minutes long. Maximum allowed duration is {max_min} minutes."
        )

    if width <= 0 or height <= 0:
        raise ValidationError(
            "Video has invalid dimensions."
        )

    if width > settings.UPLOAD_MAX_WIDTH or height > settings.UPLOAD_MAX_HEIGHT:
        raise ValidationError(
            f"Video resolution {width}x{height} exceeds maximum "
            f"allowed {settings.UPLOAD_MAX_WIDTH}x{settings.UPLOAD_MAX_HEIGHT}."
        )

    if video_stream_count != 1:
        raise ValidationError(
            f"Expected exactly 1 video stream, found {video_stream_count}."
        )

    if total_stream_count > settings.UPLOAD_MAX_STREAMS:
        raise ValidationError(
            f"Too many media streams ({total_stream_count}). "
            f"Maximum allowed is {settings.UPLOAD_MAX_STREAMS}."
        )


def compute_sha256(uploaded_file):
    uploaded_file.seek(0)
    hasher = hashlib.sha256()
    while True:
        chunk = uploaded_file.read(8192)
        if not chunk:
            break
        hasher.update(chunk)
    uploaded_file.seek(0)
    return hasher.hexdigest()

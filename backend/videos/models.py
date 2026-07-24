from django.db import models
from django.contrib.auth.models import User
from .helpers import (
    get_optimized_video_url,
    get_streaming_url,
    get_thumbnail_url,
    add_image_watermark,
)


class VideoStatus(models.TextChoices):
    PENDING = "pending", "Pending Scan"
    SCANNING = "scanning", "Scanning"
    SAFE = "safe", "Safe"
    REJECTED = "rejected", "Rejected — Virus Detected"
    FAILED = "failed", "Failed — Infrastructure Error"


class ScanErrorCode(models.TextChoices):
    VIRUS_DETECTED = "virus_detected", "Virus Detected"
    TIMEOUT = "timeout", "Scan Timeout"
    CONNECTION_REFUSED = "connection_refused", "Connection Refused"
    SCANNER_ERROR = "scanner_error", "Scanner Error"
    FILE_MISSING = "file_missing", "File Missing"
    FILE_TAMPERED = "file_tampered", "File Tampered"
    UPLOAD_FAILED = "upload_failed", "ImageKit Upload Failed"
    UNKNOWN = "unknown_error", "Unknown Error"


class Video(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="videos")
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    original_filename = models.CharField(max_length=255, blank=True)
    storage_filename = models.CharField(max_length=255, blank=True)
    file_id = models.CharField(max_length=200, blank=True)
    video_url = models.URLField(max_length=500, blank=True)
    thumbnail_url = models.URLField(max_length=500, blank=True)

    sha256_hash = models.CharField(max_length=64, blank=True, db_index=True)
    container = models.CharField(max_length=32, blank=True)
    codec = models.CharField(max_length=32, blank=True)
    duration = models.PositiveIntegerField(default=0, help_text="Duration in seconds")
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    original_file_size = models.PositiveBigIntegerField(
        default=0, help_text="File size in bytes at upload time"
    )

    status = models.CharField(
        max_length=20,
        choices=VideoStatus.choices,
        default=VideoStatus.PENDING,
        db_index=True,
    )
    scan_result = models.CharField(max_length=255, blank=True)
    scan_error_code = models.CharField(
        max_length=50,
        choices=ScanErrorCode.choices,
        blank=True,
    )
    quarantine_path = models.CharField(max_length=500, blank=True)
    scanned_at = models.DateTimeField(null=True, blank=True)
    scanning_started_at = models.DateTimeField(null=True, blank=True)
    scan_duration_ms = models.PositiveIntegerField(null=True, blank=True)

    views = models.PositiveIntegerField(default=0)
    likes = models.PositiveIntegerField(default=0)
    dislikes = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def display_thumbnail_url(self):
        if self.thumbnail_url and "/thumbnails/" in self.thumbnail_url:
            return add_image_watermark(self.thumbnail_url, self.user.username)
        return self.generated_thumbnail_url

    @property
    def generated_thumbnail_url(self):
        if not self.video_url:
            return ""
        return get_thumbnail_url(self.video_url, self.user.username)

    @property
    def streaming_url(self):
        if not self.video_url or self.status != VideoStatus.SAFE:
            return ""
        return get_streaming_url(self.video_url)

    @property
    def optimized_url(self):
        if not self.video_url or self.status != VideoStatus.SAFE:
            return ""
        return get_optimized_video_url(self.video_url)

    @property
    def quarantine_abs_path(self):
        from pathlib import Path
        from django.conf import settings
        if not self.quarantine_path:
            return None
        return str(Path(str(settings.QUARANTINE_DIR)) / self.quarantine_path)

        

class VideoView(models.Model):
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.CASCADE
    )
    video = models.ForeignKey(
        Video, on_delete=models.CASCADE, related_name="views_log"
    )
    session_key = models.CharField(max_length=40, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "video", "created_at"]),
            models.Index(fields=["session_key", "video", "created_at"]),
        ]


class VideoLike(models.Model):
    LIKE = 1
    DISLIKE = -1
    LIKE_CHOICES = [
        (LIKE, "Like"),
        (DISLIKE, "Dislike")
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="user_likes")
    value = models.SmallIntegerField(choices=LIKE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["user", "video"]

    def __str__(self):
        action = "liked" if self.value == self.LIKE else "disliked"
        return f"{self.user.username} {action} {self.video.title}"
from django.contrib import admin
from django.utils.html import format_html

from .models import Video, VideoLike, VideoView, VideoStatus


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "user",
        "status_badge",
        "original_file_size",
        "created_at",
        "scanned_at",
        "scan_duration_ms",
    )
    list_filter = ("status", "created_at")
    search_fields = ("title", "original_filename", "user__username", "sha256_hash")
    readonly_fields = (
        "scan_result",
        "scan_error_code",
        "scanned_at",
        "scanning_started_at",
        "scan_duration_ms",
        "sha256_hash",
        "quarantine_path",
    )

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            VideoStatus.PENDING: "#f59e0b",
            VideoStatus.SCANNING: "#3b82f6",
            VideoStatus.SAFE: "#10b981",
            VideoStatus.REJECTED: "#ef4444",
            VideoStatus.FAILED: "#6b7280",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:4px;font-size:12px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    actions = ["rescan_videos"]

    @admin.display(description="Rescan selected videos")
    def rescan_videos(self, request, queryset):
        from .tasks import scan_video

        count = 0
        for video in queryset.filter(status__in=[VideoStatus.REJECTED, VideoStatus.FAILED]):
            video.status = VideoStatus.PENDING
            video.scan_error_code = ""
            video.scan_result = ""
            video.save(update_fields=["status", "scan_error_code", "scan_result"])
            scan_video.delay(video.id)
            count += 1
        self.message_user(request, f"Queued {count} videos for rescan.")


@admin.register(VideoView)
class VideoViewAdmin(admin.ModelAdmin):
    list_display = ("user", "video", "session_key", "ip_address", "created_at")
    list_filter = ("created_at",)
    raw_id_fields = ("user", "video")


@admin.register(VideoLike)
class VideoLikeAdmin(admin.ModelAdmin):
    list_display = ("user", "video", "value", "created_at")
    list_filter = ("value", "created_at")
    raw_id_fields = ("user", "video")

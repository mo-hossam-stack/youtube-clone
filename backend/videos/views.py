from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from datetime import timedelta
import logging

from .models import Video, VideoLike, VideoView, VideoStatus
from .forms import VideoUploadForm
from .helpers import upload_thumbnail, delete_video
from .quarantine import save_to_quarantine, delete_quarantine_file
from .tasks import scan_video

logger = logging.getLogger("videos.upload")

VIEW_DEDUP_HOURS = 24


def video_detail(request, video_id):
    video = get_object_or_404(Video.objects, id=video_id)

    # Streaming gate — only show fully scanned videos
    if video.status != VideoStatus.SAFE:
        return render(request, "videos/processing.html", {
            "video": video,
            "status": video.get_status_display(),
        })

    user_vote = None

    should_count = True

    if request.user.is_authenticated and request.user == video.user:
        should_count = False

    if should_count:
        if not request.session.session_key:
            request.session.create()

        window = timezone.now() - timedelta(hours=VIEW_DEDUP_HOURS)

        if request.user.is_authenticated:
            recent = VideoView.objects.filter(
                user=request.user,
                video=video,
                created_at__gte=window,
            ).exists()
        else:
            recent = VideoView.objects.filter(
                session_key=request.session.session_key,
                video=video,
                created_at__gte=window,
            ).exists()

        if not recent:
            with transaction.atomic():
                if request.user.is_authenticated:
                    already_counted = VideoView.objects.filter(
                        user=request.user,
                        video=video,
                        created_at__gte=window,
                    ).exists()
                else:
                    already_counted = VideoView.objects.filter(
                        session_key=request.session.session_key,
                        video=video,
                        created_at__gte=window,
                    ).exists()

                if not already_counted:
                    Video.objects.filter(pk=video.pk).update(
                        views=F("views") + 1
                    )
                    VideoView.objects.create(
                        user=request.user if request.user.is_authenticated else None,
                        video=video,
                        session_key=request.session.session_key,
                        ip_address=(
                            request.META.get("HTTP_X_FORWARDED_FOR", "")
                            .split(",")[0]
                            .strip()
                            or request.META.get("REMOTE_ADDR")
                        ),
                    )

    if request.user.is_authenticated:
        like = VideoLike.objects.filter(user=request.user, video=video).first()
        if like:
            user_vote = like.value

    return render(request, "videos/detail.html", {"video": video, "user_vote": user_vote})

def video_list(request):
    videos = Video.objects.all()
    return render(request, 'videos/list.html', {"videos": videos})


def channel_videos(request, username):
    videos = Video.objects.filter(user__username=username)
    return render(request, "videos/channel.html", {"videos": videos, "channel_name": username})


@login_required
@require_POST
def video_upload(request):
    form = VideoUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        errors = []
        for field, field_errors in form.errors.items():
            for error in field_errors:
                errors.append(
                    f"{field}: {error}" if field != "__all__" else error
                )
        return JsonResponse({"success": False, "errors": errors})

    video_file = form.cleaned_data["video_file"]
    custom_thumbnail = request.POST.get("thumbnail_data", "")
    quarantine_path = None

    try:
        with transaction.atomic():
            # Save to quarantine (local disk, not publicly accessible)
            quarantine_path = save_to_quarantine(video_file, video_file.storage_name)

            metadata = video_file.metadata
            video = Video.objects.create(
                user=request.user,
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
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

            # Upload thumbnail synchronously (not a security concern)
            if custom_thumbnail and custom_thumbnail.startswith("data:image"):
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

            # Dispatch async virus scan
            scan_video.delay(video.id)

            logger.info(
                "upload.queued",
                extra={
                    "video_id": video.id,
                    "user_id": request.user.id,
                    "file_size": video.original_file_size,
                    "sha256": video.sha256_hash[:12],
                },
            )

            return JsonResponse({
                "success": True,
                "video_id": video.id,
                "status": "pending",
                "message": "Video uploaded successfully. Scanning in progress.",
            }, status=202)

    except ValidationError as e:
        # Clean up quarantine file if it was written before the error
        if quarantine_path:
            delete_quarantine_file(quarantine_path)
        logger.warning(
            "Upload rejected",
            extra={
                "reason": str(e),
                "upload_filename": video_file.name,
                "filesize": video_file.size,
                "client_ip": request.META.get("REMOTE_ADDR"),
            },
        )
        return JsonResponse({"success": False, "error": str(e)})

    except Exception:
        if quarantine_path:
            delete_quarantine_file(quarantine_path)
        logger.exception(
            "Upload failed",
            extra={
                "upload_filename": video_file.name,
                "filesize": video_file.size,
                "user_id": request.user.id,
                "client_ip": request.META.get("REMOTE_ADDR"),
            },
        )
        return JsonResponse(
            {"success": False, "error": "Upload failed. Please try again."}
        )


@login_required
def video_upload_page(request):
    return render(request, "videos/upload.html", {"form": VideoUploadForm()})


@login_required
@require_POST
def delete_video(request, video_id):
    video = get_object_or_404(Video, id=video_id, user=request.user)

    try:
        delete_video(video.file_id)
    except Exception as e:
        print(e)
        pass

    video.delete()

    return JsonResponse({"success": True, "message": "video deleted"})


@login_required
@require_POST
def video_vote(request, video_id):
    video = get_object_or_404(Video, id=video_id)
    vote_type = request.POST.get("vote")

    if vote_type not in ["like", "dislike"]:
        return JsonResponse({"success": False, "error": "Invalid vote"}, status=400)

    value = VideoLike.LIKE if vote_type == "like" else VideoLike.DISLIKE

    existing_vote = VideoLike.objects.filter(user=request.user, video=video).first()

    if existing_vote:
        if existing_vote.value == value:
            if value == VideoLike.LIKE:
                video.likes -= 1
            else:
                video.dislikes -= 1
            existing_vote.delete()
            user_vote = None
        else:
            if value == VideoLike.LIKE:
                video.likes += 1
                video.dislikes -= 1
            else:
                video.likes -=1
                video.dislikes += 1
            existing_vote.value = value
            existing_vote.save()
            user_vote = value
    else:
        VideoLike.objects.create(user=request.user, video=video, value=value)
        if value == VideoLike.LIKE:
            video.likes += 1
        else:
            video.dislikes += 1
        user_vote = value

    video.save(update_fields=["likes", "dislikes"])

    return JsonResponse({
        "likes": video.likes,
        "dislikes": video.dislikes,
        "user_vote": user_vote
    })


@login_required
@require_POST
def upload_status(request, video_id):
    """Return the scan status for an upload."""
    video = get_object_or_404(Video, id=video_id, user=request.user)
    return JsonResponse({
        "video_id": video.id,
        "status": video.status,
        "status_display": video.get_status_display(),
        "scan_result": video.scan_result,
        "scanned_at": video.scanned_at.isoformat() if video.scanned_at else None,
        "scan_duration_ms": video.scan_duration_ms,
    })
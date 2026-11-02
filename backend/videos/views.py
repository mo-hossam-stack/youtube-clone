from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from datetime import timedelta
import logging
import re
from . import errors
from .constants import VIDEO_TITLE_MAX_LENGTH, VIDEO_TITLE_MIN_LENGTH
from .models import Video, VideoLike, VideoView, VideoStatus
from .forms import VideoUploadForm
from .helpers import delete_video
from .services.upload import create_video_from_upload

PUBLIC_ID_RE = re.compile(r"^[A-Za-z0-9]{8}$")

logger = logging.getLogger("videos.upload")

VIEW_DEDUP_HOURS = 24


def video_detail(request, public_id):
    if not PUBLIC_ID_RE.match(public_id):
        raise Http404
    video = get_object_or_404(Video, public_id=public_id)

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


def _content_length(request):
    try:
        return int(request.META.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        return 0


def _upload_config():
    max_file_mb = round(settings.UPLOAD_MAX_FILE_SIZE / (1024 * 1024))
    return {
        "title": {
            "min": VIDEO_TITLE_MIN_LENGTH,
            "max": VIDEO_TITLE_MAX_LENGTH,
        },
        "file": {
            "maxBytes": settings.UPLOAD_MAX_FILE_SIZE,
            "maxSizeLabel": f"{max_file_mb} MB",
            "allowedExtensions": settings.UPLOAD_ALLOWED_EXTENSIONS,
        },
        "messages": {
            "title": errors.TITLE_MESSAGES,
            "file": {
                errors.REQUIRED: "Please select a video file.",
                errors.EMPTY_FILE: "Uploaded file is empty.",
                errors.FILE_TOO_LARGE: (
                    f"File is too large. Maximum allowed size is "
                    f"{max_file_mb} MB."
                ),
                errors.INVALID_EXTENSION: (
                    "File must be one of: "
                    f"{', '.join(settings.UPLOAD_ALLOWED_EXTENSIONS)}."
                ),
            },
        },
    }


@login_required
@require_POST
def video_upload(request):
    if _content_length(request) > settings.UPLOAD_REQUEST_MAX_BYTES:
        return JsonResponse(
            {
                "success": False,
                "errors": errors.error_payload(
                    errors.REQUEST_TOO_LARGE,
                    "Request is too large. Please upload a smaller video.",
                ),
            },
            status=413,
        )

    form = VideoUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse(
            {"success": False, "errors": errors.form_errors_payload(form)},
            status=400,
        )

    try:
        video = create_video_from_upload(
            user=request.user,
            cleaned_data=form.cleaned_data,
            video_file=form.cleaned_data["video_file"],
            custom_thumbnail=request.POST.get("thumbnail_data", ""),
        )
    except ValidationError as exc:
        logger.warning(
            "Upload rejected",
            extra={
                "reason": str(exc),
                "upload_filename": form.cleaned_data["video_file"].name,
                "filesize": form.cleaned_data["video_file"].size,
                "client_ip": request.META.get("REMOTE_ADDR"),
            },
        )
        return JsonResponse(
            {"success": False, "errors": errors.validation_error_payload(exc)},
            status=400,
        )
    except Exception:
        logger.exception(
            "Upload failed",
            extra={
                "upload_filename": form.cleaned_data["video_file"].name,
                "filesize": form.cleaned_data["video_file"].size,
                "user_id": request.user.id,
                "client_ip": request.META.get("REMOTE_ADDR"),
            },
        )
        return JsonResponse(
            {
                "success": False,
                "errors": errors.error_payload(
                    errors.UPLOAD_FAILED,
                    "Upload failed. Please try again.",
                ),
            },
            status=500,
        )

    return JsonResponse({
        "success": True,
        "public_id": video.public_id,
        "status": "pending",
        "message": "Video uploaded successfully. Scanning in progress.",
    }, status=202)


@login_required
def video_upload_page(request):
    return render(
        request,
        "videos/upload.html",
        {
            "form": VideoUploadForm(),
            "title_max_length": VIDEO_TITLE_MAX_LENGTH,
            "upload_config": _upload_config(),
        },
    )


@login_required
@require_POST
def delete_video(request, public_id):
    if not PUBLIC_ID_RE.match(public_id):
        raise Http404
    video = get_object_or_404(Video, public_id=public_id, user=request.user)

    try:
        delete_video(video.file_id)
    except Exception as e:
        print(e)
        pass

    video.delete()

    return JsonResponse({"success": True, "message": "video deleted"})


@login_required
@require_POST
def video_vote(request, public_id):
    if not PUBLIC_ID_RE.match(public_id):
        raise Http404
    video = get_object_or_404(Video, public_id=public_id)
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
def upload_status(request, public_id):
    """Return the scan status for an upload."""
    if not PUBLIC_ID_RE.match(public_id):
        raise Http404
    video = get_object_or_404(Video, public_id=public_id, user=request.user)
    return JsonResponse({
        "public_id": video.public_id,
        "status": video.status,
        "status_display": video.get_status_display(),
        "scan_result": video.scan_result,
        "scanned_at": video.scanned_at.isoformat() if video.scanned_at else None,
        "scan_duration_ms": video.scan_duration_ms,
    })
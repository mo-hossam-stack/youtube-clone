from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Video
from .forms import VideoUploadForm
from .helpers import upload_video, upload_thumbnail


def video_detail(request, video_id):
    video = get_object_or_404(Video.objects, id=video_id)
    return render(request, "videos/detail.html", {"video": video})

def video_list(request):
    videos = Video.objects.all()
    return render(request, 'videos/list.html', {"videos": videos})


@login_required
@require_POST
def video_upload(request):
    form = VideoUploadForm(request.POST, request.FILES)
    if form.is_valid():
        video_file = form.cleaned_data['video_file']
        custom_thumbnail = request.POST.get("thumbnail_data", "")

        try:
            result = upload_video(
                file_data=video_file.read(),
                file_name=video_file.name
            )

            thumbnail_url = ""
            if custom_thumbnail and custom_thumbnail.startswith("data:image"):
                try:
                    base_name = video_file.name.rsplit(".", 1)[0]
                    thumb_result = upload_thumbnail(
                        file_data=custom_thumbnail,
                        file_name=base_name + "_thumb.jpg"
                    )
                    thumbnail_url = thumb_result["url"]
                except Exception as e:
                    print(e)
                    pass

            video = Video.objects.create(
                user=request.user,
                title=form.cleaned_data['title'],
                description=form.cleaned_data['description'],
                file_id=result["file_id"],
                video_url=result["url"],
                thumbnail_url=thumbnail_url,
            )

            return JsonResponse({
                "success": True,
                "video_id": video.id,
                "message": "Video uploaded successfully"
            })
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    errors = []
    for field, field_errors in form.errors.items():
        for error in field_errors:
            errors.append(f"{field}: {error}" if field != "__all__" else error)
    return JsonResponse({"success": False, "errors": ";".join(errors)})


@login_required
def video_upload_page(request):
    return render(request, "videos/upload.html", {"form": VideoUploadForm()})


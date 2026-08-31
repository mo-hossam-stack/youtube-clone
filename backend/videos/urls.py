from django.urls import path
from . import views

app_name = "videos"

urlpatterns = [
    path("upload/", views.video_upload_page, name="upload"),
    path("upload/submit/", views.video_upload, name="upload_submit"),
    path("upload/<str:public_id>/status/", views.upload_status, name="upload_status"),
    path("", views.video_list, name="list"),
    path("<str:public_id>", views.video_detail, name="detail"),
    path("channel/<str:username>/", views.channel_videos, name="channel"),
    path("<str:public_id>/delete/", views.delete_video, name="delete"),
    path("<str:public_id>/vote/", views.video_vote, name="vote"),
]
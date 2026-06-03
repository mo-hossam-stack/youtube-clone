from django.urls import path
from . import views

app_name = "videos"

urlpatterns = [
    path("upload/", views.video_upload_page, name="upload"),
    path("upload/submit/", views.video_upload, name="upload_submit"),
]
from django import forms
from django.core.validators import FileExtensionValidator
import magic

class VideoUploadForm(forms.Form):
    title = forms.CharField( 
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "class": "form-input",
                "placeholder": "Enter ur title here"
            }
        )
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-input",
                "placeholder": "Enter video description",
                "rows": 4
            }
        )
    )
    
    video_file = forms.FileField(
        validators=[
            FileExtensionValidator(
                allowed_extensions=["mp4", "webm", "mov", "avi"]
            )
        ],
        widget=forms.FileInput(
            attrs={
                "class": "form-input",
                "accept": "video/*", 
            }
        ),
    )

    MAX_VIDEO_SIZE = 100 * 1024 * 1024

    ALLOWED_MIME_TYPES = {
        "video/mp4",
        "video/webm",
        "video/quicktime",
        "video/x-msvideo",
    }

    def clean_video_file(self):
        video = self.cleaned_data.get("video_file")

        if not video:
            return video

        if video.size > self.MAX_VIDEO_SIZE:
            raise forms.ValidationError(
                "Video must be under 100 MB."
            )

        try:
            mime = magic.from_buffer(
                video.read(4096),
                mime=True,
            )
            video.seek(0)
        except Exception:
            raise forms.ValidationError(
                "Unable to validate uploaded file."
            )

        if mime not in self.ALLOWED_MIME_TYPES:
            raise forms.ValidationError(
                "Invalid or unsupported video file."
            )

        return video
    
    def clean_title(self):
        title = self.cleaned_data["title"].strip()

        if len(title) < 3:
            raise forms.ValidationError(
                "Title is too short"
            )

        return title
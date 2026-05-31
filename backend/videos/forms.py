from django import forms
from django.core.validators import FileExtensionValidator

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

        if video.content_type not in self.ALLOWED_MIME_TYPES:
            raise forms.ValidationError(
                "This video type is not allowed."
            )

        return video
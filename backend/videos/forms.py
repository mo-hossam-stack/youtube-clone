from django import forms
from django.conf import settings
from django.core.validators import FileExtensionValidator

from .validators import (
    compute_sha256,
    extract_video_metadata,
    sanitize_filename,
    save_temp_upload,
    validate_file_size,
    validate_mime_type,
    validate_video_metadata,
)


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
                allowed_extensions=settings.UPLOAD_ALLOWED_EXTENSIONS,
            )
        ],
        widget=forms.FileInput(
            attrs={
                "class": "form-input",
                "accept": "video/*", 
            }
        ),
    )

    def clean_video_file(self):
        video = self.cleaned_data.get("video_file")

        if not video:
            return video

        validate_file_size(video, settings.UPLOAD_MAX_FILE_SIZE)

        validate_mime_type(
            video,
            settings.UPLOAD_ALLOWED_MIME_TYPES,
            settings.UPLOAD_ALLOWED_EXTENSIONS,
        )

        with save_temp_upload(video) as tmp_path:
            metadata = extract_video_metadata(
                tmp_path, settings.UPLOAD_FFPROBE_TIMEOUT,
            )
        validate_video_metadata(metadata)

        sha256 = compute_sha256(video)

        storage_name, _ = sanitize_filename(video.name)
        video.storage_name = storage_name
        video.sha256_hash = sha256
        video.metadata = metadata
        return video
    
    def clean_title(self):
        title = self.cleaned_data["title"].strip()

        if len(title) < 3:
            raise forms.ValidationError(
                
            )

        return title
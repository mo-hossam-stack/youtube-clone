import unicodedata

from django import forms
from django.conf import settings
from django.core.validators import FileExtensionValidator

from .constants import VIDEO_TITLE_MAX_LENGTH, VIDEO_TITLE_MIN_LENGTH
from .validators import (
    compute_sha256,
    extract_video_metadata,
    sanitize_filename,
    save_temp_upload,
    validate_file_size,
    validate_mime_type,
    validate_video_metadata,
)


class NormalizedCharField(forms.CharField):
    def to_python(self, value):
        value = super().to_python(value)
        return unicodedata.normalize("NFC", value) if value else value


class VideoUploadForm(forms.Form):
    title = NormalizedCharField(
        max_length=VIDEO_TITLE_MAX_LENGTH,
        min_length=VIDEO_TITLE_MIN_LENGTH,
        error_messages={
            "max_length": (
                "Title must be %(limit_value)d characters or fewer "
                "(currently %(show_value)d)."
            ),
            "min_length": (
                "Title must be at least %(limit_value)d characters."
            ),
        },
        widget=forms.TextInput(
            attrs={
                "class": "form-input",
                "placeholder": "Enter your title here",
                "maxlength": VIDEO_TITLE_MAX_LENGTH,
            }
        ),
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
        title = self.cleaned_data["title"]

        if "<" in title or ">" in title:
            raise forms.ValidationError("Title cannot contain < or >.")

        if any(unicodedata.category(char) == "Cc" for char in title):
            raise forms.ValidationError("Title contains invalid control characters.")

        return title

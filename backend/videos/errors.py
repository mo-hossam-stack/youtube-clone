"""Stable upload error codes and JSON error formatting."""

from .constants import VIDEO_TITLE_MAX_LENGTH, VIDEO_TITLE_MIN_LENGTH

REQUIRED = "required"
MIN_LENGTH = "min_length"
MAX_LENGTH = "max_length"
INVALID_CHARACTERS = "invalid_characters"
CONTROL_CHARACTERS = "control_characters"
INVALID_EXTENSION = "invalid_extension"
EMPTY_FILE = "empty_file"
FILE_TOO_LARGE = "file_too_large"
INVALID_FILE_TYPE = "invalid_file_type"
INVALID_FILENAME = "invalid_filename"
INVALID_VIDEO_METADATA = "invalid_video_metadata"
VIDEO_TIMEOUT = "video_timeout"
VIDEO_TOOL_UNAVAILABLE = "video_tool_unavailable"
REQUEST_TOO_LARGE = "request_too_large"
UPLOAD_FAILED = "upload_failed"

TITLE_MESSAGES = {
    REQUIRED: "Please enter a title.",
    MIN_LENGTH: f"Title must be at least {VIDEO_TITLE_MIN_LENGTH} characters.",
    MAX_LENGTH: (
        f"Title must be {VIDEO_TITLE_MAX_LENGTH} characters or fewer "
        "(currently {length})."
    ),
    INVALID_CHARACTERS: "Title cannot contain < or >.",
    CONTROL_CHARACTERS: "Title contains invalid control characters.",
}


def _validation_items(exc):
    items = []
    for error in getattr(exc, "error_list", [exc]):
        code = getattr(error, "code", None) or "invalid"
        for message in error.messages:
            items.append({"code": code, "message": message})
    return items


def form_errors_payload(form):
    return {
        field: [
            item
            for error in errors
            for item in _validation_items(error)
        ]
        for field, errors in form.errors.as_data().items()
    }


def validation_error_payload(exc, field="__all__"):
    error_dict = getattr(exc, "error_dict", None)
    if error_dict:
        return {
            key: _validation_items(errors)
            for key, errors in error_dict.items()
        }
    return {field: _validation_items(exc)}


def error_payload(code, message, field="__all__"):
    return {field: [{"code": code, "message": message}]}

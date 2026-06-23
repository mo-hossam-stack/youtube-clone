import os
from urllib.parse import urlparse
from imagekitio import ImageKit


def get_imagekit_client():
    return ImageKit()


def _get_url_endpoint(base_url: str) -> str:
    parsed = urlparse(base_url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _build_url(src: str, transformation: list = None, signed: bool = True, expires_in: int = None) -> str:
    client = get_imagekit_client()
    return client.helper.build_url(
        src=src,
        url_endpoint=_get_url_endpoint(src),
        transformation=transformation,
        signed=signed,
        expires_in=expires_in,
    )


def get_optimized_video_url(base_url: str) -> str:
    return _build_url(
        base_url,
        transformation=[{"quality": 50, "format": "auto"}],
    )


def get_streaming_url(base_url: str) -> str:
    hls_url = base_url.rstrip("/") + "/ik-master.m3u8"
    return _build_url(
        hls_url,
        transformation=[{"streaming_resolutions": ["240", "360", "480", "720", "1080"]}],
    )


def _get_watermark_transformation(username: str):
    if not username:
        return None
    return [{
        "overlay": {
            "type": "text",
            "text": username,
            "position": {
                "x": 10,
                "y": 10,
                "focus": "bottom_left",
            },
            "transformation": [{
                "font_size": 32,
                "font_color": "FFFFFF",
                "background": "00000060",
                "padding": "4_8",
            }],
        },
    }]


def add_image_watermark(
        base_url: str, username: str = None
) -> str:
    return _build_url(
        base_url,
        transformation=_get_watermark_transformation(username),
    )


def get_thumbnail_url(base_url: str, username: str = None) -> str:
    thumb_url = base_url.rstrip("/") + "/ik-thumbnail.jpg"
    return _build_url(
        thumb_url,
        transformation=_get_watermark_transformation(username),
    )


def upload_video(file_data: bytes, file_name: str, folder: str = "videos") -> dict:
    public_key = os.environ.get("IMAGEKIT_PUBLIC_KEY")

    client = get_imagekit_client()

    response = client.files.upload(
        file=file_data,
        file_name=file_name,
        folder=folder,
        public_key=public_key
    )

    return {
        "file_id": response.file_id,
        "url": response.url
    }


def upload_thumbnail(file_data: bytes, file_name: str, folder: str = "thumbnails") -> dict:
    import base64
    public_key = os.environ.get("IMAGEKIT_PUBLIC_KEY")

    if file_data.startswith("data:"):
        base64_data = file_data.split(",", 1)[1]
        image_bytes = base64.b64decode(base64_data)
    else:
        image_bytes = base64.b64decode(file_data)

    client = get_imagekit_client()

    response = client.files.upload(
        file=image_bytes,
        file_name=file_name,
        folder=folder,
        public_key=public_key
    )

    return {
        "file_id": response.file_id,
        "url": response.url
    }


def delete_video(file_id: str) -> bool:
    client = get_imagekit_client()
    client.files.delete(file_id=file_id)
    return True
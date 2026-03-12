"""Storage service — upload and retrieve assets.

R2-D2 would be proud. Everything gets filed properly.

Dual-mode:
  - Local dev: saves to ./assets/ and serves via /assets/ static route
  - Cloud Run: uploads to GCS with service account (signed URLs or public bucket)
"""

import logging
import uuid
from pathlib import Path
from typing import Optional

from app.config.settings import settings

logger = logging.getLogger(__name__)

# Local asset root (relative to backend working directory)
LOCAL_ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
LOCAL_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# GCS client (lazy-init, only for Cloud Run)
_storage_client = None


def _use_gcs() -> bool:
    """Whether to use GCS (only when running on Cloud Run with a service account)."""
    return settings.use_gcs if hasattr(settings, "use_gcs") else False


def _get_gcs_client():
    global _storage_client
    if _storage_client is None:
        from google.cloud import storage
        _storage_client = storage.Client(project=settings.google_cloud_project)
    return _storage_client


def _local_url(rel_path: str) -> str:
    """Build a URL path for locally-served assets."""
    return f"/assets/{rel_path}"


async def upload_image(
    image_bytes: bytes,
    project_id: str,
    category: str = "panels",
    filename: Optional[str] = None,
    content_type: str = "image/png",
) -> str:
    """Upload an image and return its URL.

    Local dev: saves to ./assets/projects/{id}/{category}/
    Cloud Run: uploads to GCS bucket.
    """
    if filename is None:
        ext = "png" if "png" in content_type else "jpg"
        filename = f"{uuid.uuid4().hex}.{ext}"

    rel_path = f"projects/{project_id}/{category}/{filename}"

    if _use_gcs():
        client = _get_gcs_client()
        bucket = client.bucket(settings.gcs_bucket)
        blob = bucket.blob(rel_path)
        blob.upload_from_string(image_bytes, content_type=content_type)
        logger.info("Storage: Uploaded to GCS: %s", rel_path)
        return blob.public_url
    else:
        local_path = LOCAL_ASSETS_DIR / rel_path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(image_bytes)
        logger.info("Storage: Saved locally: %s (%d KB)", local_path, len(image_bytes) // 1024)
        return _local_url(rel_path)


async def upload_video(
    video_bytes: bytes,
    project_id: str,
    filename: Optional[str] = None,
    content_type: str = "video/mp4",
) -> str:
    """Upload a video."""
    if filename is None:
        filename = f"{uuid.uuid4().hex}.mp4"

    rel_path = f"projects/{project_id}/videos/{filename}"

    if _use_gcs():
        client = _get_gcs_client()
        bucket = client.bucket(settings.gcs_bucket)
        blob = bucket.blob(rel_path)
        blob.upload_from_string(video_bytes, content_type=content_type)
        return blob.public_url
    else:
        local_path = LOCAL_ASSETS_DIR / rel_path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(video_bytes)
        return _local_url(rel_path)


async def upload_export(
    file_bytes: bytes,
    project_id: str,
    format: str,
    filename: Optional[str] = None,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload an export file (PDF, CBZ, PPTX, MP4)."""
    if filename is None:
        filename = f"export_{uuid.uuid4().hex[:8]}.{format}"

    rel_path = f"projects/{project_id}/exports/{filename}"

    if _use_gcs():
        client = _get_gcs_client()
        bucket = client.bucket(settings.gcs_bucket)
        blob = bucket.blob(rel_path)
        blob.upload_from_string(file_bytes, content_type=content_type)
        return blob.public_url
    else:
        local_path = LOCAL_ASSETS_DIR / rel_path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(file_bytes)
        return _local_url(rel_path)


async def delete_project_images(project_id: str, categories: list[str] = None) -> int:
    """Delete all image assets for a project (or specific categories).

    Used before regeneration to ensure only the latest images are stored.
    Returns count of files deleted.
    """
    if categories is None:
        categories = ["comic_pages", "manga_pages", "storyboard_pages", "panels"]

    deleted = 0

    if _use_gcs():
        client = _get_gcs_client()
        bucket = client.bucket(settings.gcs_bucket)
        for cat in categories:
            prefix = f"projects/{project_id}/{cat}/"
            blobs = list(bucket.list_blobs(prefix=prefix))
            for blob in blobs:
                blob.delete()
                deleted += 1
        logger.info("Storage: Deleted %d GCS objects for project %s", deleted, project_id)
    else:
        for cat in categories:
            cat_dir = LOCAL_ASSETS_DIR / "projects" / project_id / cat
            if cat_dir.exists():
                for f in cat_dir.iterdir():
                    if f.is_file():
                        f.unlink()
                        deleted += 1
        logger.info("Storage: Deleted %d local files for project %s", deleted, project_id)

    return deleted


async def download_blob(blob_path: str) -> bytes:
    """Download a blob."""
    if _use_gcs():
        client = _get_gcs_client()
        bucket = client.bucket(settings.gcs_bucket)
        blob = bucket.blob(blob_path)
        return blob.download_as_bytes()
    else:
        local_path = LOCAL_ASSETS_DIR / blob_path
        return local_path.read_bytes()

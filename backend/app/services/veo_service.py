"""Veo 3.1 Video Generation Service — WALL-E's core engine.

Integrates with Google's Veo video model via Vertex AI for:
- Text-to-video generation
- Image-to-video generation
- Video extension
- First/last frame interpolation

All operations are long-running — we poll with exponential backoff.
"""

import asyncio
import base64
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import aiohttp
import google.auth
import google.auth.transport.requests
from google.cloud import storage

from app.config.settings import settings

logger = logging.getLogger("storyforge.veo")


class VideoResolution(str, Enum):
    HD = "720p"
    FULL_HD = "1080p"
    FOUR_K = "4k"


class AspectRatio(str, Enum):
    WIDESCREEN = "16:9"
    VERTICAL = "9:16"
    SQUARE = "1:1"


@dataclass
class VideoResult:
    """Result from a Veo generation call."""
    video_url: str  # GCS URI or signed URL
    local_path: Optional[str] = None
    duration_seconds: float = 0.0
    resolution: str = "1080p"
    has_audio: bool = False
    operation_id: Optional[str] = None
    generation_time_seconds: float = 0.0
    metadata: dict = field(default_factory=dict)


class VeoService:
    """Google Veo 3.1 video generation via Vertex AI.

    WALL-E carefully crafts each video clip — persistent, patient,
    always polling until the beautiful result appears.
    """

    # Polling configuration — exponential backoff
    INITIAL_POLL_INTERVAL = 5.0   # seconds
    MAX_POLL_INTERVAL = 30.0      # seconds
    BACKOFF_MULTIPLIER = 1.5
    MAX_POLL_DURATION = 600.0     # 10 minutes max wait

    # Concurrency limit for parallel Veo calls
    MAX_CONCURRENT = 4

    def __init__(self):
        self.project = settings.google_cloud_project
        self.location = settings.google_cloud_location
        self.model = settings.veo_model
        self.bucket_name = settings.gcs_bucket
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)
        self._storage_client: Optional[storage.Client] = None
        self._credentials = None

    @property
    def storage_client(self) -> storage.Client:
        if self._storage_client is None:
            self._storage_client = storage.Client(project=self.project)
        return self._storage_client

    @property
    def base_url(self) -> str:
        return (
            f"https://{self.location}-aiplatform.googleapis.com/v1/"
            f"projects/{self.project}/locations/{self.location}/"
            f"publishers/google/models/{self.model}"
        )

    async def _get_access_token(self) -> str:
        """Get a fresh access token for Vertex AI API calls."""
        if self._credentials is None:
            self._credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        # Refresh in a thread to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._credentials.refresh,
            google.auth.transport.requests.Request(),
        )
        return self._credentials.token

    async def _make_request(
        self,
        endpoint_suffix: str,
        payload: dict,
    ) -> dict:
        """Make an authenticated request to Vertex AI."""
        token = await self._get_access_token()
        url = f"{self.base_url}:{endpoint_suffix}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error("Veo API error %d: %s", resp.status, body)
                    raise VeoAPIError(f"Veo API returned {resp.status}: {body}")
                return await resp.json()

    async def _poll_operation(self, operation_name: str) -> dict:
        """Poll a long-running operation until completion.

        WALL-E is patient — exponential backoff, never gives up
        (until the timeout).
        """
        token = await self._get_access_token()
        poll_url = (
            f"https://{self.location}-aiplatform.googleapis.com/v1/"
            f"{operation_name}"
        )
        interval = self.INITIAL_POLL_INTERVAL
        elapsed = 0.0
        start = time.monotonic()

        while elapsed < self.MAX_POLL_DURATION:
            await asyncio.sleep(interval)
            elapsed = time.monotonic() - start

            # Refresh token if needed (long polls can exceed token lifetime)
            token = await self._get_access_token()
            headers = {"Authorization": f"Bearer {token}"}

            async with aiohttp.ClientSession() as session:
                async with session.get(poll_url, headers=headers) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.warning(
                            "Poll error %d (will retry): %s", resp.status, body
                        )
                    else:
                        result = await resp.json()
                        if result.get("done"):
                            if "error" in result:
                                raise VeoAPIError(
                                    f"Veo operation failed: {result['error']}"
                                )
                            logger.info(
                                "Operation complete after %.1fs: %s",
                                elapsed, operation_name,
                            )
                            return result.get("response", result)

                        progress = result.get("metadata", {}).get(
                            "progressPercentage", 0
                        )
                        logger.debug(
                            "Polling %s — %.0f%% (%.1fs elapsed)",
                            operation_name, progress, elapsed,
                        )

            # Backoff
            interval = min(interval * self.BACKOFF_MULTIPLIER, self.MAX_POLL_INTERVAL)

        raise VeoTimeoutError(
            f"Operation {operation_name} timed out after {self.MAX_POLL_DURATION}s"
        )

    async def _upload_to_gcs(self, local_path: str, gcs_prefix: str = "inputs") -> str:
        """Upload a local file to GCS, return the gs:// URI."""
        bucket = self.storage_client.bucket(self.bucket_name)
        filename = Path(local_path).name
        blob_name = f"{gcs_prefix}/{uuid.uuid4().hex[:8]}_{filename}"
        blob = bucket.blob(blob_name)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, blob.upload_from_filename, local_path)
        gcs_uri = f"gs://{self.bucket_name}/{blob_name}"
        logger.info("Uploaded %s → %s", local_path, gcs_uri)
        return gcs_uri

    async def _download_from_gcs(self, gcs_uri: str, local_dir: str) -> str:
        """Download a GCS file to a local directory."""
        # Parse gs://bucket/path
        parts = gcs_uri.replace("gs://", "").split("/", 1)
        bucket_name = parts[0]
        blob_name = parts[1] if len(parts) > 1 else ""

        bucket = self.storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        local_path = str(Path(local_dir) / Path(blob_name).name)
        Path(local_dir).mkdir(parents=True, exist_ok=True)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, blob.download_to_filename, local_path)
        logger.info("Downloaded %s → %s", gcs_uri, local_path)
        return local_path

    def _encode_image_base64(self, image_path: str) -> str:
        """Read an image file and return base64-encoded bytes."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _build_generation_config(
        self,
        duration: int = 8,
        resolution: str = "1080p",
        aspect: str = "16:9",
        generate_audio: bool = True,
    ) -> dict:
        """Build the generationConfig block for Veo requests."""
        config = {
            "videoDuration": f"{duration}s",
            "resolution": resolution,
            "aspectRatio": aspect,
        }
        if generate_audio:
            config["generateAudio"] = True
        return config

    async def _extract_video_result(
        self, response: dict, start_time: float, local_dir: Optional[str] = None
    ) -> VideoResult:
        """Extract video result from Veo API response."""
        generation_time = time.monotonic() - start_time

        # Veo returns videos in the response
        videos = response.get("videos", response.get("predictions", []))
        if not videos:
            raise VeoAPIError("No video generated in response")

        video_data = videos[0] if isinstance(videos, list) else videos

        # The video might be returned as a GCS URI or inline
        video_uri = video_data.get("uri", video_data.get("gcsUri", ""))
        has_audio = video_data.get("hasAudio", False)

        result = VideoResult(
            video_url=video_uri,
            duration_seconds=video_data.get("durationSeconds", 0),
            resolution=video_data.get("resolution", "1080p"),
            has_audio=has_audio,
            generation_time_seconds=generation_time,
            metadata=video_data.get("metadata", {}),
        )

        # Download locally if requested
        if local_dir and video_uri.startswith("gs://"):
            result.local_path = await self._download_from_gcs(video_uri, local_dir)

        return result

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    async def text_to_video(
        self,
        prompt: str,
        duration: int = 8,
        resolution: str = "1080p",
        aspect: str = "16:9",
        generate_audio: bool = True,
        local_dir: Optional[str] = None,
        style_modifier: Optional[str] = None,
    ) -> VideoResult:
        """Generate a video clip from a text prompt.

        Args:
            prompt: Scene description for Veo.
            duration: Clip duration in seconds (max 8 for base generation).
            resolution: Output resolution (720p, 1080p, 4k).
            aspect: Aspect ratio (16:9, 9:16, 1:1).
            generate_audio: Whether Veo should generate dialogue/SFX/ambient.
            local_dir: If set, download the result to this directory.
            style_modifier: Director style prompt suffix.

        Returns:
            VideoResult with GCS URI and optional local path.
        """
        full_prompt = prompt
        if style_modifier:
            full_prompt = f"{prompt}. {style_modifier}"

        payload = {
            "instances": [{"prompt": full_prompt}],
            "parameters": {
                "storageUri": f"gs://{self.bucket_name}/veo-outputs/",
            },
            "generationConfig": self._build_generation_config(
                duration, resolution, aspect, generate_audio
            ),
        }

        start = time.monotonic()
        async with self._semaphore:
            logger.info("Text-to-video: %.100s...", full_prompt)
            response = await self._make_request("predictLongRunning", payload)
            operation_name = response.get("name", "")
            result_data = await self._poll_operation(operation_name)

        result = await self._extract_video_result(result_data, start, local_dir)
        result.operation_id = operation_name
        return result

    async def image_to_video(
        self,
        image_path: str,
        prompt: str,
        duration: int = 8,
        resolution: str = "1080p",
        aspect: str = "16:9",
        generate_audio: bool = True,
        local_dir: Optional[str] = None,
        style_modifier: Optional[str] = None,
    ) -> VideoResult:
        """Generate a video from a key frame image + prompt.

        The image becomes the first frame, and Veo animates from there.

        Args:
            image_path: Path to the key frame image (local or GCS URI).
            prompt: Motion/action description for animation.
            duration: Clip duration in seconds.
            resolution: Output resolution.
            aspect: Aspect ratio.
            generate_audio: Whether to generate audio track.
            local_dir: Download destination.
            style_modifier: Director style prompt suffix.
        """
        full_prompt = prompt
        if style_modifier:
            full_prompt = f"{prompt}. {style_modifier}"

        # Upload image to GCS if it's a local file
        if not image_path.startswith("gs://"):
            image_gcs_uri = await self._upload_to_gcs(image_path, "key-frames")
        else:
            image_gcs_uri = image_path

        # Encode for API (Veo accepts inline base64 or GCS ref)
        image_instance = {"image": {"gcsUri": image_gcs_uri}, "prompt": full_prompt}

        payload = {
            "instances": [image_instance],
            "parameters": {
                "storageUri": f"gs://{self.bucket_name}/veo-outputs/",
            },
            "generationConfig": self._build_generation_config(
                duration, resolution, aspect, generate_audio
            ),
        }

        start = time.monotonic()
        async with self._semaphore:
            logger.info("Image-to-video: %s → %.80s...", image_path, full_prompt)
            response = await self._make_request("predictLongRunning", payload)
            operation_name = response.get("name", "")
            result_data = await self._poll_operation(operation_name)

        result = await self._extract_video_result(result_data, start, local_dir)
        result.operation_id = operation_name
        return result

    async def extend_video(
        self,
        video_path: str,
        prompt: str,
        extension_seconds: int = 7,
        generate_audio: bool = True,
        local_dir: Optional[str] = None,
        style_modifier: Optional[str] = None,
    ) -> VideoResult:
        """Extend an existing video clip by generating continuation.

        Args:
            video_path: Path to existing video (local or GCS URI).
            prompt: Description for the continuation.
            extension_seconds: How many seconds to add (max 8).
            local_dir: Download destination.
            style_modifier: Director style prompt suffix.
        """
        full_prompt = prompt
        if style_modifier:
            full_prompt = f"{prompt}. {style_modifier}"

        if not video_path.startswith("gs://"):
            video_gcs_uri = await self._upload_to_gcs(video_path, "clips")
        else:
            video_gcs_uri = video_path

        payload = {
            "instances": [
                {
                    "video": {"gcsUri": video_gcs_uri},
                    "prompt": full_prompt,
                }
            ],
            "parameters": {
                "storageUri": f"gs://{self.bucket_name}/veo-outputs/",
                "extensionMode": "continuation",
            },
            "generationConfig": self._build_generation_config(
                extension_seconds, generate_audio=generate_audio
            ),
        }

        start = time.monotonic()
        async with self._semaphore:
            logger.info("Extend video: %s + %ds", video_path, extension_seconds)
            response = await self._make_request("predictLongRunning", payload)
            operation_name = response.get("name", "")
            result_data = await self._poll_operation(operation_name)

        result = await self._extract_video_result(result_data, start, local_dir)
        result.operation_id = operation_name
        return result

    async def first_last_frame(
        self,
        first_image: str,
        last_image: str,
        prompt: str,
        duration: int = 8,
        resolution: str = "1080p",
        aspect: str = "16:9",
        generate_audio: bool = True,
        local_dir: Optional[str] = None,
        style_modifier: Optional[str] = None,
    ) -> VideoResult:
        """Generate video interpolation between first and last frames.

        Perfect for scene continuity — last frame of scene N becomes
        first frame of scene N+1.

        Args:
            first_image: Path to the starting frame.
            last_image: Path to the ending frame.
            prompt: Motion description for the interpolation.
            duration: Clip duration in seconds.
            resolution: Output resolution.
            aspect: Aspect ratio.
            generate_audio: Whether to generate audio.
            local_dir: Download destination.
            style_modifier: Director style prompt suffix.
        """
        full_prompt = prompt
        if style_modifier:
            full_prompt = f"{prompt}. {style_modifier}"

        # Upload frames if local
        if not first_image.startswith("gs://"):
            first_gcs = await self._upload_to_gcs(first_image, "key-frames")
        else:
            first_gcs = first_image

        if not last_image.startswith("gs://"):
            last_gcs = await self._upload_to_gcs(last_image, "key-frames")
        else:
            last_gcs = last_image

        payload = {
            "instances": [
                {
                    "firstFrameImage": {"gcsUri": first_gcs},
                    "lastFrameImage": {"gcsUri": last_gcs},
                    "prompt": full_prompt,
                }
            ],
            "parameters": {
                "storageUri": f"gs://{self.bucket_name}/veo-outputs/",
            },
            "generationConfig": self._build_generation_config(
                duration, resolution, aspect, generate_audio
            ),
        }

        start = time.monotonic()
        async with self._semaphore:
            logger.info(
                "First/last frame: %s → %s (%.80s...)",
                first_image, last_image, full_prompt,
            )
            response = await self._make_request("predictLongRunning", payload)
            operation_name = response.get("name", "")
            result_data = await self._poll_operation(operation_name)

        result = await self._extract_video_result(result_data, start, local_dir)
        result.operation_id = operation_name
        return result


# ──────────────────────────────────────────────
# Exceptions
# ──────────────────────────────────────────────


class VeoAPIError(Exception):
    """Raised when Veo API returns an error."""
    pass


class VeoTimeoutError(Exception):
    """Raised when polling exceeds the maximum duration."""
    pass

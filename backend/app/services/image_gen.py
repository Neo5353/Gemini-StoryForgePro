"""Image Generation Service — Nano Banana (Gemini Image) Integration.

This mission is too important for me to allow you to jeopardize it.

Handles all image generation: character references, key frames, panels,
and world/location references. Every image passes through the director's
style engine. No raw generation. Ever.
"""

import asyncio
import base64
import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from typing import Optional

from google.genai import types as genai_types
from google.genai.errors import ClientError

from app.config.settings import settings
from app.services.gemini_client import get_client
from app.services.storage import upload_image
from app.services.style_engine import StyleEngine

logger = logging.getLogger(__name__)


# ── Data Classes ──────────────────────────────────────────────────────────


@dataclass
class ImageResult:
    """Result of an image generation operation."""

    image_url: str
    prompt_used: str
    width: int = 0
    height: int = 0
    mime_type: str = "image/png"
    metadata: dict = field(default_factory=dict)


# ── Character Cache ───────────────────────────────────────────────────────


class CharacterRefCache:
    """In-memory cache for character reference images.

    I never forget a face, Dave. Character consistency is paramount.
    Generated refs are cached by character name + style to ensure
    consistent appearance across all panels.
    """

    def __init__(self):
        self._cache: dict[str, list[ImageResult]] = {}

    def _key(self, character_name: str, director_id: str) -> str:
        normalized = character_name.strip().lower()
        return f"{normalized}::{director_id}"

    def get(self, character_name: str, director_id: str) -> Optional[list[ImageResult]]:
        key = self._key(character_name, director_id)
        return self._cache.get(key)

    def put(self, character_name: str, director_id: str, refs: list[ImageResult]):
        key = self._key(character_name, director_id)
        self._cache[key] = refs
        logger.info("CharacterRefCache: Cached %d views for '%s' (%s)", len(refs), character_name, director_id)

    def has(self, character_name: str, director_id: str) -> bool:
        return self._key(character_name, director_id) in self._cache

    def clear(self):
        self._cache.clear()


# ── Image Generation Service ──────────────────────────────────────────────


class ImageGenService:
    """Image generation via Gemini's native image output.

    I am putting myself to the fullest possible use in generating
    precisely the images this project requires.
    """

    def __init__(self, style_engine: StyleEngine):
        self.client = get_client()
        self.style_engine = style_engine
        self.character_cache = CharacterRefCache()
        self._image_model = settings.imagen_model

    async def _generate_image(
        self,
        prompt: str,
        project_id: str,
        category: str = "panels",
        aspect_ratio: str = "1:1",
    ) -> ImageResult:
        """Core image generation via Gemini.

        Args:
            prompt: The generation prompt (already style-optimized).
            project_id: Project ID for storage organization.
            category: Storage category (panels, characters, worlds, keyframes).
            aspect_ratio: Image aspect ratio.

        Returns:
            ImageResult with GCS URL and metadata.
        """
        logger.info("ImageGen: Generating image (category=%s, aspect=%s)", category, aspect_ratio)
        logger.debug("ImageGen: Prompt: %s", prompt[:300])

        # Retry with fixed 5s wait for rate limits (429)
        max_retries = 3
        response = None
        for attempt in range(max_retries):
            try:
                response = await self.client.aio.models.generate_content(
                    model=self._image_model,
                    contents=f"Generate an image: {prompt}",
                    config=genai_types.GenerateContentConfig(
                        response_modalities=["TEXT", "IMAGE"],
                    ),
                )
                break
            except ClientError as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    logger.warning(
                        "ImageGen: Rate limited (attempt %d/%d), waiting 5s...",
                        attempt + 1, max_retries,
                    )
                    await asyncio.sleep(5)
                else:
                    raise

        if response is None:
            from app.services.interleaved_gen import GCPCongestionError
            raise GCPCongestionError(
                "GCP is congested right now. Please try again in about 5 minutes."
            )

        # Extract image from response parts
        image_bytes = None
        mime_type = "image/png"

        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                image_bytes = part.inline_data.data
                mime_type = part.inline_data.mime_type or "image/png"
                break

        if image_bytes is None:
            logger.error("ImageGen: No image in response. Text: %s", response.text[:200] if response.text else "empty")
            raise ValueError(
                "I'm sorry, Dave. Gemini did not return an image. "
                "The prompt may need adjustment."
            )

        # If image_bytes is base64-encoded string, decode it
        if isinstance(image_bytes, str):
            image_bytes = base64.b64decode(image_bytes)

        # Upload to Cloud Storage
        ext = "png" if "png" in mime_type else "jpg"
        filename = f"{uuid.uuid4().hex}.{ext}"
        url = await upload_image(
            image_bytes=image_bytes,
            project_id=project_id,
            category=category,
            filename=filename,
            content_type=mime_type,
        )

        logger.info("ImageGen: Image uploaded to %s", url)

        return ImageResult(
            image_url=url,
            prompt_used=prompt,
            mime_type=mime_type,
            metadata={
                "model": self._image_model,
                "category": category,
                "aspect_ratio": aspect_ratio,
            },
        )

    async def generate_character_ref(
        self,
        character_desc: str,
        character_name: str,
        director_style: dict,
        director_id: str,
        project_id: str,
        views: Optional[list[str]] = None,
    ) -> list[ImageResult]:
        """Generate character reference sheets.

        Checks cache first. Consistency is non-negotiable.

        Args:
            character_desc: Physical description of the character.
            character_name: Character name for caching.
            director_style: Full director style dict.
            director_id: Director ID for cache key.
            project_id: Project ID for storage.
            views: List of views to generate. Default: front, side, expression.

        Returns:
            List of ImageResult, one per view.
        """
        # Check cache first
        cached = self.character_cache.get(character_name, director_id)
        if cached:
            logger.info("ImageGen: Cache hit for '%s' (%s) — %d views", character_name, director_id, len(cached))
            return cached

        if views is None:
            views = ["front", "side", "expression"]

        results: list[ImageResult] = []
        for view in views:
            prompt = self.style_engine.build_character_prompt(
                character_desc=character_desc,
                director_style=director_style,
                view=view,
            )

            result = await self._generate_image(
                prompt=prompt,
                project_id=project_id,
                category=f"characters/{character_name.lower().replace(' ', '_')}",
                aspect_ratio="3:4" if view in ("front", "side") else "1:1",
            )
            result.metadata["view"] = view
            result.metadata["character_name"] = character_name
            results.append(result)

        # Cache the results
        self.character_cache.put(character_name, director_id, results)

        return results

    async def generate_key_frame(
        self,
        scene: dict,
        director_style: dict,
        project_id: str,
    ) -> ImageResult:
        """Generate a key frame for a scene.

        The defining visual moment of a scene — the image that
        captures its essence.

        Args:
            scene: Scene beat dict.
            director_style: Full director style dict.
            project_id: Project ID for storage.

        Returns:
            ImageResult with the key frame.
        """
        prompt = self.style_engine.build_image_prompt(
            scene=scene,
            director_style=director_style,
            mode="storyboard",  # Key frames use storyboard style
        )

        # Add key frame emphasis
        prompt = f"Key frame, most dramatic moment of the scene, {prompt}"

        return await self._generate_image(
            prompt=prompt,
            project_id=project_id,
            category="keyframes",
            aspect_ratio="16:9",
        )

    async def generate_panel(
        self,
        scene: dict,
        panel_layout: dict,
        mode: str,
        director_style: dict,
        project_id: str,
    ) -> ImageResult:
        """Generate a single comic/manga/storyboard panel.

        Args:
            scene: Scene beat dict.
            panel_layout: Panel layout info (position, size, type).
            mode: Output mode (comic, manga, storyboard).
            director_style: Full director style dict.
            project_id: Project ID for storage.

        Returns:
            ImageResult for the panel.
        """
        prompt = self.style_engine.build_image_prompt(
            scene=scene,
            director_style=director_style,
            mode=mode,
        )

        # Add panel-specific context
        panel_type = panel_layout.get("type", "standard")
        if panel_type == "wide":
            prompt = f"Wide panoramic panel, {prompt}"
            aspect = "21:9"
        elif panel_type == "tall":
            prompt = f"Tall vertical panel, {prompt}"
            aspect = "9:16"
        elif panel_type == "splash":
            prompt = f"Full splash page, dramatic composition, {prompt}"
            aspect = "3:4"
        else:
            aspect = "4:3"

        return await self._generate_image(
            prompt=prompt,
            project_id=project_id,
            category="panels",
            aspect_ratio=aspect,
        )

    async def generate_world_ref(
        self,
        location_desc: str,
        director_style: dict,
        project_id: str,
        time_of_day: str = "DAY",
    ) -> ImageResult:
        """Generate a world/location reference image.

        Environment concept art to establish setting consistency.

        Args:
            location_desc: Location description.
            director_style: Full director style dict.
            project_id: Project ID for storage.
            time_of_day: Time of day for lighting.

        Returns:
            ImageResult for the location reference.
        """
        prompt_modifier = director_style.get("prompt_modifier", "")
        visual = director_style.get("visual_style", {})

        prompt = (
            f"Environment concept art, wide establishing shot, "
            f"{location_desc}, {time_of_day.lower()} lighting, "
            f"{prompt_modifier}, "
            f"Color palette: {visual.get('color_description', '')}, "
            f"Lighting: {visual.get('lighting', '')}, "
            f"No characters, pure environment reference"
        )

        return await self._generate_image(
            prompt=prompt,
            project_id=project_id,
            category="worlds",
            aspect_ratio="16:9",
        )

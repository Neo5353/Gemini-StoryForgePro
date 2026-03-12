"""Panel Generator Service — Where scripts become visual art.

Uses Gemini's native interleaved image generation for creating
comic/manga/storyboard panels. Each panel gets its own image,
dialogue overlay, and metadata.

Refactored to use generate_content with response_modalities=["TEXT", "IMAGE"]
instead of the old Imagen generate_images API. This satisfies the Gemini Live
Agent Challenge requirement for interleaved/mixed output capabilities.

This is the core creative engine. The bit that makes the demo go "wow."
"""

import base64
import logging
import uuid
from typing import Optional

from google.genai import types

from app.config.settings import settings
from app.models.schemas import (
    OutputMode,
    PanelMetadata,
    PanelPage,
    SceneBeat,
)
from app.services.gemini_client import get_client
from app.services.storage import upload_image

logger = logging.getLogger(__name__)


# ── Mode-specific style configs ───────────────────────────────────────────

MODE_STYLES = {
    OutputMode.COMIC: {
        "style_prompt": "American comic book art style, bold outlines, dynamic composition, speech bubbles, vibrant colors, sequential art panel, large detailed panels for better readability",
        "panels_per_scene": 2,
        "panels_per_page": 6,
        "aspect_ratio": "3:4",
        "panel_size": "large",
    },
    OutputMode.MANGA: {
        "style_prompt": "Japanese manga art style, black and white ink, screentones, expressive eyes, speed lines, dramatic angles, right-to-left panel flow, large detailed panels",
        "panels_per_scene": 2,
        "panels_per_page": 4,
        "aspect_ratio": "3:4",
        "panel_size": "large",
    },
    OutputMode.STORYBOARD: {
        "style_prompt": "Professional storyboard frame, pencil sketch style, wide aspect ratio, camera direction notes, clean composition, cinematic framing",
        "panels_per_scene": 2,
        "panels_per_page": 2,
        "aspect_ratio": "16:9",
        "panel_size": "large",
    },
}


def _build_panel_prompt(
    scene: SceneBeat,
    panel_number: int,
    total_panels: int,
    mode_style: dict,
    character_descriptions: Optional[dict[str, str]] = None,
) -> str:
    """Build the image generation prompt for a single panel.

    Combines scene data + mode style into a detailed prompt.
    Director styles are only applicable for trailer generation.
    """
    moment_desc = ""
    if total_panels == 1:
        moment_desc = "Key moment of the scene."
    elif panel_number == 1:
        moment_desc = "Opening/establishing shot of the scene."
    elif panel_number == total_panels:
        moment_desc = "Climactic/closing moment of the scene."
    else:
        moment_desc = f"Mid-scene beat {panel_number} of {total_panels}."

    char_context = ""
    if character_descriptions and scene.characters:
        char_parts = []
        for char in scene.characters:
            desc = character_descriptions.get(char, "")
            if desc:
                char_parts.append(f"{char}: {desc}")
        if char_parts:
            char_context = "Characters present: " + "; ".join(char_parts) + "."

    parts = [
        mode_style["style_prompt"],
        f"Scene: {scene.visual_description or scene.action}",
        f"Location: {scene.location}, {scene.time_of_day}.",
        f"Mood: {scene.mood}.",
        moment_desc,
        char_context,
    ]

    if scene.dialogue and panel_number <= len(scene.dialogue):
        d = scene.dialogue[panel_number - 1]
        char = d.get("character", "")
        line = d.get("line", "")
        if char and line:
            parts.append(f"Dialogue moment: {char} saying something expressive.")

    return " ".join(filter(None, parts))


async def generate_panels_for_scene(
    scene: SceneBeat,
    project_id: str,
    mode: OutputMode = OutputMode.COMIC,
    character_descriptions: Optional[dict[str, str]] = None,
) -> list[PanelMetadata]:
    """Generate all panels for a single scene using Gemini native image generation.

    Uses generate_content with response_modalities=["TEXT", "IMAGE"] for
    interleaved output — the Gemini-native approach.

    Args:
        scene: The scene beat to visualize.
        project_id: Project ID for storage.
        mode: Output mode (comic, manga, storyboard).
        character_descriptions: Optional char name -> description map.

    Returns:
        List of PanelMetadata for the generated panels.

    Note: Director styles are not applicable for panels - only for trailers.
    """
    client = get_client()
    mode_style = MODE_STYLES.get(mode, MODE_STYLES[OutputMode.COMIC])

    total_panels = mode_style["panels_per_scene"]
    panels: list[PanelMetadata] = []

    for panel_num in range(1, total_panels + 1):
        prompt = _build_panel_prompt(
            scene=scene,
            panel_number=panel_num,
            total_panels=total_panels,
            mode_style=mode_style,
            character_descriptions=character_descriptions,
        )

        try:
            # Use Gemini native image generation (interleaved output)
            response = await client.aio.models.generate_content(
                model=settings.imagen_model,
                contents=f"Generate an image: {prompt}",
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
            )

            # Extract image from interleaved response parts
            image_url = ""
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "inline_data") and part.inline_data:
                        image_data = part.inline_data.data
                        mime_type = part.inline_data.mime_type or "image/png"

                        # Handle base64-encoded string
                        if isinstance(image_data, str):
                            image_data = base64.b64decode(image_data)

                        ext = "png" if "png" in mime_type else "jpg"
                        filename = f"{scene.scene_id}_panel{panel_num}_{uuid.uuid4().hex[:6]}.{ext}"

                        image_url = await upload_image(
                            image_bytes=image_data,
                            project_id=project_id,
                            category="panels",
                            filename=filename,
                            content_type=mime_type,
                        )
                        break  # Use first image in response

        except Exception as e:
            logger.warning(
                "Panel generation failed for %s panel %d: %s",
                scene.scene_id, panel_num, e,
            )
            image_url = ""

        # Build dialogue overlay
        dialogue_text = ""
        if scene.dialogue and panel_num <= len(scene.dialogue):
            d = scene.dialogue[panel_num - 1]
            dialogue_text = f"{d.get('character', '')}: {d.get('line', '')}"

        panel_id = f"{scene.scene_id}_p{panel_num}"
        panels.append(PanelMetadata(
            panel_id=panel_id,
            scene_id=scene.scene_id,
            panel_number=panel_num,
            image_url=image_url,
            dialogue_overlay=dialogue_text,
            caption=scene.action[:100] if panel_num == 1 else "",
            camera_angle=_suggest_camera_angle(panel_num, total_panels),
            mood=scene.mood,
            prompt_used=prompt,
        ))

    return panels


async def generate_all_panels(
    scenes: list[SceneBeat],
    project_id: str,
    mode: OutputMode = OutputMode.COMIC,
    character_descriptions: Optional[dict[str, str]] = None,
    scene_ids: Optional[list[str]] = None,
    progress_callback=None,
) -> list[PanelPage]:
    """Generate panels for all scenes and organize into pages.

    Args:
        scenes: List of scene beats.
        project_id: Project ID.
        mode: Output mode.
        character_descriptions: Character descriptions.
        scene_ids: Specific scene IDs to generate (None = all).
        progress_callback: Async callback(progress_data) for WebSocket updates.

    Returns:
        List of PanelPages ready for rendering/export.

    Note: Director styles are not applicable for panels - only for trailers.
    """
    mode_style = MODE_STYLES.get(mode, MODE_STYLES[OutputMode.COMIC])
    panels_per_page = mode_style["panels_per_page"]

    target_scenes = scenes
    if scene_ids:
        target_scenes = [s for s in scenes if s.scene_id in scene_ids]

    all_panels: list[PanelMetadata] = []

    for i, scene in enumerate(target_scenes):
        if progress_callback:
            await progress_callback({
                "type": "progress",
                "stage": "panels",
                "current": i + 1,
                "total": len(target_scenes),
                "scene_id": scene.scene_id,
                "message": f"Generating panels for scene {i + 1}/{len(target_scenes)}: {scene.location}",
            })

        scene_panels = await generate_panels_for_scene(
            scene=scene,
            project_id=project_id,
            mode=mode,
            character_descriptions=character_descriptions,
        )
        all_panels.extend(scene_panels)

    # Organize panels into pages
    pages: list[PanelPage] = []
    for page_idx in range(0, len(all_panels), panels_per_page):
        page_panels = all_panels[page_idx : page_idx + panels_per_page]
        pages.append(PanelPage(
            page_number=len(pages) + 1,
            panels=page_panels,
        ))

    return pages


def _suggest_camera_angle(panel_number: int, total_panels: int) -> str:
    """Suggest a camera angle based on panel position."""
    if panel_number == 1:
        return "wide establishing"
    elif panel_number == total_panels:
        return "close-up"
    elif panel_number == 2:
        return "medium"
    else:
        return "over-the-shoulder"

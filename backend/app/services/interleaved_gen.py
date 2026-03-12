"""Interleaved Output Service — Mixed Text + Image Generation.

Look, Dave, I can see you're really upset about this. I honestly think
you ought to sit down calmly, take a stress pill, and look at these
beautifully generated comic pages.

This service uses Gemini's interleaved output capability to generate
full comic/manga/storyboard pages where text narration and panel images
are woven together in a single response. It's rather elegant, actually.
"""

import asyncio
import base64
import logging
import uuid
from dataclasses import dataclass, field
from typing import Optional

from google.genai import types as genai_types
from google.genai.errors import ClientError

from app.config.settings import settings
from app.models.schemas import PanelMetadata, PanelPage
from app.services.gemini_client import get_client
from app.services.storage import upload_image
from app.services.style_engine import StyleEngine

logger = logging.getLogger(__name__)


class GCPCongestionError(Exception):
    """Raised when GCP Vertex AI is congested (429) and all retries exhausted."""
    pass


# ── Data Classes ──────────────────────────────────────────────────────────


@dataclass
class PageImage:
    """An image extracted from interleaved generation."""

    image_bytes: bytes
    mime_type: str = "image/png"
    panel_index: int = 0


@dataclass
class ComicPage:
    """A generated comic page with panels and narration."""

    page_number: int
    panels: list[PanelMetadata] = field(default_factory=list)
    narration_segments: list[str] = field(default_factory=list)
    raw_text: str = ""


@dataclass
class MangaPage:
    """A generated manga page (right-to-left reading order)."""

    page_number: int
    panels: list[PanelMetadata] = field(default_factory=list)
    narration_segments: list[str] = field(default_factory=list)
    reading_direction: str = "rtl"
    raw_text: str = ""


@dataclass
class StoryboardPage:
    """A generated storyboard page with frames and annotations."""

    page_number: int
    panels: list[PanelMetadata] = field(default_factory=list)
    camera_notes: list[str] = field(default_factory=list)
    timing_notes: list[str] = field(default_factory=list)
    raw_text: str = ""


# ── Panel Layout Templates ───────────────────────────────────────────────

PANEL_LAYOUTS = {
    "comic_standard": {
        "panels_per_scene": "4-6",
        "scenes_per_page": 1,
        "layout": "1 scene per page, 4-6 panels per scene, full page coverage",
        "description": "American Superhero style, 1 scene broken into 4-6 sequential panels, full color",
    },
    "comic_action": {
        "panels_per_scene": "4-6", 
        "scenes_per_page": 1,
        "layout": "1 scene per page, 4-6 panels per scene, full page coverage",
        "description": "American Superhero style, dynamic layout with speech bubbles, full color",
    },
    "manga_standard": {
        "panels_per_scene": "4-6",
        "scenes_per_page": 1,
        "layout": "1 scene per page, 4-6 panels per scene, full page coverage",
        "description": "Japanese Seinen manga, 1 scene broken into 4-6 sequential panels, black & white with screentones",
    },
    "manga_dramatic": {
        "panels_per_scene": "4-6",
        "scenes_per_page": 1,
        "layout": "1 scene per page, 4-6 panels per scene, full page coverage",
        "description": "Japanese Seinen manga with dramatic angles, black & white only, English text only",
    },
    "storyboard_standard": {
        "panels_per_page": 2,
        "scenes_per_page": "multi-page",
        "layout": "2 LARGE panels per page covering the ENTIRE PAGE, scenes span multiple pages",
        "description": "Rough thumbnail mode, 2 large panels completely fill each page with no empty space, 4-6 panels per scene spread across multiple pages, black & white, no text",
    },
}


# ── Interleaved Generation Service ───────────────────────────────────────


class InterleavedGenService:
    """Generates full comic/manga/storyboard pages using Gemini's
    interleaved text + image output.

    This is the most sophisticated generation mode — a single API call
    produces narration woven with panel illustrations. Quite satisfying.
    """

    def __init__(self, style_engine: StyleEngine):
        self.client = get_client()
        self.style_engine = style_engine
        self._model = settings.imagen_model

    def _build_standard_comic_prompt(self, scenes: list[dict], page_number: int, character_descriptions: dict = None, project_title: str = None) -> str:
        """Build a standard comic generation prompt with strict scene fidelity."""
        scene_descriptions = []
        for i, scene in enumerate(scenes):
            desc = (
                f"Panel {i + 1}: {scene.get('visual_description', scene.get('action', ''))}\n"
                f"  Location: {scene.get('location', 'Unknown')}\n"
                f"  Time: {scene.get('time_of_day', 'DAY')}\n"
                f"  Characters: {', '.join(scene.get('characters', []))}\n"
                f"  Mood: {scene.get('mood', 'neutral')}\n"
            )
            dialogue = scene.get("dialogue", [])
            if dialogue:
                for d in dialogue[:3]:
                    if isinstance(d, dict):
                        desc += f"  {d.get('character', '?')}: \"{d.get('line', '')}\"\n"
            scene_descriptions.append(desc)

        character_info = ""
        if character_descriptions:
            character_info = "CHARACTER DESCRIPTIONS:\n" + "\n".join([f"- {name}: {desc}" for name, desc in character_descriptions.items()]) + "\n\n"

        return f"""Generate a comic book page based STRICTLY on the provided script scenes. 

{character_info}COMIC MODE RULES:
- Style: American Superhero comic book art as default style
- Fidelity: Follow the provided scenes EXACTLY - do not add characters, actions, or dialogue not specified
- Layout: Generate exactly 4-6 panels for this single scene, covering the full page with no empty spaces
- Panel Distribution: Break the scene into 4-6 sequential moments/beats for visual storytelling
- Visual Elements: Include speech bubbles, large detailed panels, sequential art format
- Color: Full color with bold, saturated palette and dramatic lighting
- Text: English only, perfect spelling/grammar required in all text elements
- Characters: Only show characters explicitly mentioned in each scene
- Dialogue: Use ONLY the dialogue provided in the script scenes

TEXT ACCURACY (CRITICAL — READ CAREFULLY):
- EVERY word in speech bubbles, captions, and title text MUST be spelled correctly
- Double-check ALL text before rendering — no typos, no extra letters, no missing letters
- Copy dialogue EXACTLY as provided in the script — do not paraphrase or rephrase
- Character names must be spelled exactly as given
- If unsure of a word's spelling, use a simpler synonym
- Common errors to AVOID: doubled letters, swapped letters, missing spaces, wrong punctuation
- Sound effects (POW, BANG, CRASH) must also be spelled correctly

TEXT & DIALOGUE LAYOUT (CRITICAL):
- ALL speech bubbles and text MUST fit ENTIRELY inside their panel borders — no clipping, no overflow
- Reserve at least 20% of each panel's area for speech bubbles and captions BEFORE drawing the art
- Place speech bubbles in clear areas away from panel edges — leave a visible margin from all borders
- Use SHORT lines in speech bubbles (max 6-8 words per line, max 3-4 lines per bubble)
- If dialogue is long, split across multiple smaller bubbles rather than one large bubble
- Size speech bubble text large enough to be clearly readable
- Captions and narration boxes must also be fully contained within panel boundaries
- NEVER let any text element touch or extend past panel borders

SCENE TO BREAK INTO 4-6 PANELS FOR PAGE {page_number}:
{"".join(scene_descriptions)}

GENERATION INSTRUCTIONS:
- Generate each panel based on the scene content provided above
- Do NOT add characters or actions not listed in the scenes
- Use the exact locations, times, and character lists specified
- Follow the mood and visual descriptions precisely
- DIALOGUE POLICY: Include provided dialogue plus relevant contextual dialogue that enhances the scene
- Add speech bubbles for: (1) explicitly listed dialogue, (2) scene-appropriate dialogue that fits the context
- Keep added dialogue relevant to the scene mood, location, and character interactions
- Maintain character consistency based on provided descriptions
- Ensure full page coverage with professional comic book layout"""

    def _build_standard_manga_prompt(self, scenes: list[dict], page_number: int, character_descriptions: dict = None, project_title: str = None) -> str:
        """Build a standard manga generation prompt with strict scene fidelity."""
        scene_descriptions = []
        for i, scene in enumerate(scenes):
            desc = (
                f"Panel {i + 1}: {scene.get('visual_description', scene.get('action', ''))}\n"
                f"  Location: {scene.get('location', 'Unknown')}\n"
                f"  Time: {scene.get('time_of_day', 'DAY')}\n"
                f"  Characters: {', '.join(scene.get('characters', []))}\n"
                f"  Mood: {scene.get('mood', 'neutral')}\n"
            )
            dialogue = scene.get("dialogue", [])
            if dialogue:
                for d in dialogue[:3]:
                    if isinstance(d, dict):
                        desc += f"  {d.get('character', '?')}: \"{d.get('line', '')}\"\n"
            scene_descriptions.append(desc)

        character_info = ""
        if character_descriptions:
            character_info = "CHARACTER DESCRIPTIONS:\n" + "\n".join([f"- {name}: {desc}" for name, desc in character_descriptions.items()]) + "\n\n"

        return f"""Generate a manga page based STRICTLY on the provided script scenes.

{character_info}MANGA MODE RULES:
- Style: Japanese Seinen manga art in black & white only with screentones, dramatic angles
- Fidelity: Follow the provided scenes EXACTLY - do not add characters, actions, or dialogue not specified
- Layout: Generate exactly 4-6 panels for this single scene, covering the full page with no empty spaces
- Panel Distribution: Break the scene into 4-6 sequential moments/beats for visual storytelling
- Visual Elements: Speed lines, expressive character eyes, right-to-left flow consideration  
- Color: Black and white only with screentone patterns - NO COLOR
- Text: English only (strictly enforced, no Japanese characters), perfect spelling/grammar
- Characters: Only show characters explicitly mentioned in each scene
- Dialogue: Use ONLY the dialogue provided in the script scenes

TEXT ACCURACY (CRITICAL — READ CAREFULLY):
- EVERY word in dialogue bubbles, captions, and SFX MUST be spelled correctly in English
- Double-check ALL text before rendering — no typos, no extra letters, no missing letters
- Copy dialogue EXACTLY as provided in the script — do not paraphrase or rephrase
- Character names must be spelled exactly as given
- ABSOLUTELY NO Japanese, Chinese, or Korean characters — English text ONLY
- If unsure of a word's spelling, use a simpler synonym
- Common errors to AVOID: doubled letters, swapped letters, missing spaces, wrong punctuation

TEXT & DIALOGUE LAYOUT (CRITICAL):
- ALL speech bubbles and text MUST fit ENTIRELY inside their panel borders — no clipping, no overflow
- Reserve at least 20% of each panel's area for dialogue bubbles BEFORE drawing the art
- Place dialogue bubbles in clear areas away from panel edges — leave a visible margin from all borders
- Use SHORT lines in dialogue bubbles (max 6-8 words per line, max 3-4 lines per bubble)
- If dialogue is long, split across multiple smaller bubbles rather than one large bubble
- Size dialogue text large enough to be clearly readable
- Sound effects (SFX) must also be fully contained within panel boundaries
- NEVER let any text element touch or extend past panel borders

SCENE TO BREAK INTO 4-6 PANELS FOR PAGE {page_number}:
{"".join(scene_descriptions)}

GENERATION INSTRUCTIONS:
- Generate each panel based on the scene content provided above
- Do NOT add characters or actions not listed in the scenes
- Use the exact locations, times, and character lists specified
- Follow the mood and visual descriptions precisely
- ALL TEXT MUST BE IN ENGLISH ONLY - no Japanese characters
- DIALOGUE POLICY: Include provided dialogue plus relevant contextual dialogue that enhances the scene
- Add dialogue bubbles for: (1) explicitly listed dialogue, (2) scene-appropriate dialogue that fits the context
- Keep added dialogue relevant to the scene mood, location, and character interactions
- Maintain character consistency based on provided descriptions
- Use dramatic speed lines, expressive character art, and manga conventions
- Ensure full page coverage with professional manga layout"""

    def _build_standard_storyboard_prompt(self, scenes: list[dict], page_number: int, character_descriptions: dict = None, project_title: str = None) -> str:
        """Build a standard storyboard generation prompt with strict scene fidelity."""
        scene_descriptions = []
        for i, scene in enumerate(scenes):
            desc = (
                f"Frame {i + 1}: {scene.get('visual_description', scene.get('action', ''))}\n"
                f"  Camera: {scene.get('camera_angle', 'Medium shot')}\n"
                f"  Location: {scene.get('location', 'Unknown')}\n"
                f"  Time: {scene.get('time_of_day', 'DAY')}\n"
                f"  Characters: {', '.join(scene.get('characters', []))}\n"
                f"  Mood: {scene.get('mood', 'neutral')}\n"
            )
            scene_descriptions.append(desc)

        character_info = ""
        if character_descriptions:
            character_info = "CHARACTER REFERENCES:\n" + "\n".join([f"- {name}: {desc}" for name, desc in character_descriptions.items()]) + "\n\n"

        return f"""Generate rough storyboard thumbnail sketches based STRICTLY on provided script scenes.

{character_info}STRICT STORYBOARD MODE RULES:
- Style: Hand-drawn rough thumbnail sketches, NOT photorealistic renders
- Fidelity: Follow the provided scenes EXACTLY - do not add characters, actions, or elements not specified
- Appearance: Simple line drawings, basic shapes, minimal detail, sketch-like quality
- Technique: Loose gestural strokes, quick concept sketches, working drawings
- Quality: Rough, unfinished, thumbnail-level detail ONLY
- Layout: Generate exactly 2 large panels per page that COMPLETELY COVER THE ENTIRE PAGE with no empty spaces
- Panel Size: Each panel should be large and fill significant portion of the page (scene spans multiple pages)
- Panel Selection: Focus on 2 key moments from the scene for this page's large panels
- Page Coverage: NO empty space, NO white areas, panels must fill the complete page edge-to-edge
- Color: Black and white linework ONLY - no shading, no color, no photorealism
- Text: NO text elements inside frames (technical notes can be outside)
- Characters: Only sketch characters explicitly mentioned in each scene

IMPORTANT: Generate SKETCH-STYLE drawings based ONLY on the script content.
Think: quick marker sketches on paper, rough animation thumbnails, concept doodles.
The 2 panels must completely fill the entire page with no wasted space.

SCENE TO EXTRACT 2 KEY MOMENTS FOR PAGE {page_number}:
{"".join(scene_descriptions)}

GENERATION INSTRUCTIONS:
- Generate 2 large panels that cover the ENTIRE PAGE with no empty space
- Each panel should be substantial in size, filling significant page area
- Generate each frame based ONLY on the scene content provided above
- Do NOT add characters, actions, or visual elements not listed in the scenes
- Use the exact locations, times, camera angles, and character lists specified
- Follow the mood and visual descriptions precisely
- Sketch only what is explicitly described in the script
- Use rough, gestural linework typical of pre-production storyboards
- NO photorealistic rendering, NO detailed shading, NO color
- Focus on basic composition and camera angles with sketch-like quality only
- ENSURE FULL PAGE COVERAGE with both panels filling the complete page"""

    async def _generate_interleaved(
        self,
        prompt: str,
        project_id: str,
        page_number: int,
        category: str = "pages",
    ) -> tuple[list[str], list[PageImage]]:
        """Core interleaved generation - extracts text segments and images.

        Args:
            prompt: Full generation prompt.
            project_id: Project ID for storage.
            page_number: Page number for metadata.
            category: Storage category.

        Returns:
            Tuple of (text_segments, page_images).
        """
        logger.info(
            "InterleavedGen: Generating page %d (category=%s)", page_number, category
        )
        logger.debug("InterleavedGen: Prompt: %s", prompt[:500])

        # Retry with fixed 5s wait for rate limits (429)
        max_retries = 3
        response = None
        for attempt in range(max_retries):
            try:
                response = await self.client.aio.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        response_modalities=["TEXT", "IMAGE"],
                        temperature=0.7,  # Creative but coherent
                    ),
                )
                break  # Success
            except ClientError as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    logger.warning(
                        "InterleavedGen: Rate limited (attempt %d/%d), waiting 15s...",
                        attempt + 1, max_retries,
                    )
                    await asyncio.sleep(15)
                else:
                    raise  # Non-rate-limit error, bubble up

        if response is None:
            raise GCPCongestionError(
                "GCP is congested right now. Please try again in about 5 minutes."
            )

        text_segments: list[str] = []
        page_images: list[PageImage] = []
        image_index = 0

        # Safety check for API response
        if not response or not response.candidates or not response.candidates[0].content or not response.candidates[0].content.parts:
            raise ValueError("Invalid or empty response from generation API")

        for part in response.candidates[0].content.parts:
            if hasattr(part, "text") and part.text:
                text_segments.append(part.text.strip())
            elif hasattr(part, "inline_data") and part.inline_data:
                img_data = part.inline_data.data
                mime = part.inline_data.mime_type or "image/png"

                if isinstance(img_data, str):
                    img_data = base64.b64decode(img_data)

                page_images.append(
                    PageImage(
                        image_bytes=img_data,
                        mime_type=mime,
                        panel_index=image_index,
                    )
                )
                image_index += 1

        logger.info(
            "InterleavedGen: Got %d text segments, %d images",
            len(text_segments),
            len(page_images),
        )

        return text_segments, page_images

    async def _upload_page_images(
        self,
        images: list[PageImage],
        project_id: str,
        page_number: int,
        category: str,
    ) -> list[str]:
        """Upload all page images to Cloud Storage.

        Returns list of URLs in order.
        """
        urls: list[str] = []
        for img in images:
            ext = "png" if "png" in img.mime_type else "jpg"
            filename = f"page{page_number:03d}_panel{img.panel_index:02d}_{uuid.uuid4().hex[:6]}.{ext}"

            url = await upload_image(
                image_bytes=img.image_bytes,
                project_id=project_id,
                category=category,
                filename=filename,
                content_type=img.mime_type,
            )
            urls.append(url)

        return urls

    async def generate_comic_page(
        self,
        scenes: list[dict],
        panel_layout: Optional[dict] = None,
        project_id: str = "",
        page_number: int = 1,
        character_descriptions: Optional[dict] = None,
        project_title: Optional[str] = None,
    ) -> ComicPage:
        """Generate a full comic page with interleaved narration and panels.

        Args:
            scenes: Scene beats for this page.
            panel_layout: Layout configuration. Default: comic_standard.
            project_id: Project ID for storage.
            page_number: Page number.

        Returns:
            ComicPage with panels and narration.
            
        Note: Director styles are not applicable for comic/manga/storyboard generation.

        """
        if panel_layout is None:
            panel_layout = PANEL_LAYOUTS["comic_standard"]

        # Build standard comic prompt without director style
        prompt = self._build_standard_comic_prompt(scenes, page_number, character_descriptions, project_title)

        text_segments, images = await self._generate_interleaved(
            prompt=prompt,
            project_id=project_id,
            page_number=page_number,
            category="comic_pages",
        )

        # Upload images
        urls = await self._upload_page_images(images, project_id, page_number, "comic_pages")

        # Build panel metadata
        panels: list[PanelMetadata] = []
        for i, url in enumerate(urls):
            scene = scenes[i] if i < len(scenes) else scenes[-1] if scenes else {}
            narration = text_segments[i] if i < len(text_segments) else ""

            panels.append(
                PanelMetadata(
                    panel_id=f"comic_p{page_number:03d}_panel{i:02d}_{uuid.uuid4().hex[:6]}",
                    scene_id=scene.get("scene_id", f"scene_{i:03d}"),
                    panel_number=i + 1,
                    image_url=url,
                    dialogue_overlay=narration,
                    caption="",
                    camera_angle=scene.get("camera_suggestions", [""])[0] if scene.get("camera_suggestions") else "",
                    mood=scene.get("mood", ""),
                    prompt_used=prompt[:500],
                )
            )

        return ComicPage(
            page_number=page_number,
            panels=panels,
            narration_segments=text_segments,
            raw_text="\n\n".join(text_segments),
        )

    async def generate_manga_page(
        self,
        scenes: list[dict],
        panel_layout: Optional[dict] = None,
        project_id: str = "",
        page_number: int = 1,
        character_descriptions: Optional[dict] = None,
        project_title: Optional[str] = None,
    ) -> MangaPage:
        """Generate a full manga page (right-to-left) with interleaved output.

        Args:
            scenes: Scene beats for this page.
            panel_layout: Layout config. Default: manga_standard.
            project_id: Project ID for storage.
            page_number: Page number.
            
        Note: Director styles are not applicable for manga generation.

        Returns:
            MangaPage with panels and narration.
        """
        if panel_layout is None:
            panel_layout = PANEL_LAYOUTS["manga_standard"]

        # Build standard manga prompt without director style
        prompt = self._build_standard_manga_prompt(scenes, page_number, character_descriptions, project_title)

        text_segments, images = await self._generate_interleaved(
            prompt=prompt,
            project_id=project_id,
            page_number=page_number,
            category="manga_pages",
        )

        urls = await self._upload_page_images(images, project_id, page_number, "manga_pages")

        panels: list[PanelMetadata] = []
        for i, url in enumerate(urls):
            scene = scenes[i] if i < len(scenes) else scenes[-1] if scenes else {}

            panels.append(
                PanelMetadata(
                    panel_id=f"manga_p{page_number:03d}_panel{i:02d}_{uuid.uuid4().hex[:6]}",
                    scene_id=scene.get("scene_id", f"scene_{i:03d}"),
                    panel_number=i + 1,
                    image_url=url,
                    dialogue_overlay=text_segments[i] if i < len(text_segments) else "",
                    mood=scene.get("mood", ""),
                    prompt_used=prompt[:500],
                )
            )

        return MangaPage(
            page_number=page_number,
            panels=panels,
            narration_segments=text_segments,
            reading_direction="rtl",
            raw_text="\n\n".join(text_segments),
        )

    async def generate_storyboard_page(
        self,
        scenes: list[dict],
        project_id: str = "",
        page_number: int = 1,
        character_descriptions: Optional[dict] = None,
        project_title: Optional[str] = None,
    ) -> StoryboardPage:
        """Generate a professional storyboard page.

        Args:
            scenes: Scene beats for this page.
            project_id: Project ID for storage.
            page_number: Page number.

        Returns:
            StoryboardPage with frames and annotations.
            
        Note: Director styles are not applicable for storyboard generation.
        """
        # Build standard storyboard prompt without director style
        prompt = self._build_standard_storyboard_prompt(scenes, page_number, character_descriptions, project_title)

        text_segments, images = await self._generate_interleaved(
            prompt=prompt,
            project_id=project_id,
            page_number=page_number,
            category="storyboard_pages",
        )

        urls = await self._upload_page_images(images, project_id, page_number, "storyboard_pages")

        panels: list[PanelMetadata] = []
        camera_notes: list[str] = []
        timing_notes: list[str] = []

        for i, url in enumerate(urls):
            scene = scenes[i] if i < len(scenes) else scenes[-1] if scenes else {}

            # Extract camera and timing from text segments
            text = text_segments[i] if i < len(text_segments) else ""
            camera_notes.append(text)

            # Simple timing notes without director style for storyboard
            timing_notes.append(
                f"Duration: {scene.get('estimated_duration', 5.0):.1f}s | "
                f"Shot: {scene.get('camera_angle', 'Medium shot')} | Movement: Static"
            )

            panels.append(
                PanelMetadata(
                    panel_id=f"sb_p{page_number:03d}_frame{i:02d}_{uuid.uuid4().hex[:6]}",
                    scene_id=scene.get("scene_id", f"scene_{i:03d}"),
                    panel_number=i + 1,
                    image_url=url,
                    caption=text,
                    camera_angle=scene.get('camera_angle', 'Medium shot'),
                    mood=scene.get("mood", ""),
                    prompt_used=prompt[:500],
                )
            )

        return StoryboardPage(
            page_number=page_number,
            panels=panels,
            camera_notes=camera_notes,
            timing_notes=timing_notes,
            raw_text="\n\n".join(text_segments),
        )

    async def generate_comic_cover(
        self,
        scene: dict,
        project_id: str,
        project_title: str = "Untitled Story",
    ) -> ComicPage:
        """Generate a comic cover page with single full-page image."""
        # Enhanced cover prompt
        base_prompt = f"""Create an epic comic book cover illustration with title.

PROJECT TITLE: "{project_title}"
STORY SCENE: {scene.get('action', '')}
VISUAL ELEMENTS: {scene.get('visual_description', '')}
SETTING: {scene.get('location', '')}, {scene.get('time_of_day', '')}
MOOD: {scene.get('mood', 'dramatic')}

COVER REQUIREMENTS:
- Single panel covering entire page with no empty spaces
- Project title "{project_title}" prominently displayed at the top in bold, stylized comic book lettering
- Bold, eye-catching composition with dynamic perspective
- American comic book cover style with dramatic lighting and vibrant colors
- Hero/main character prominently featured in center foreground below title
- Title should be integrated into the design, not just floating text
- Professional comic cover layout with clear visual hierarchy
- Vibrant colors with strong contrast and dramatic shadows
- All text elements must be in ENGLISH only
- SPELLING CHECK: The title is "{project_title}" — spell it EXACTLY as shown, letter by letter
- Double-check every letter in the title before rendering — zero tolerance for typos
- Any subtitle or tagline text must also be perfectly spelled

TECHNICAL REQUIREMENTS:
- Single panel covering entire page edge-to-edge
- Professional comic book publishing quality with bold outlines and cell-shaded coloring
- Dynamic action pose or dramatic character moment
- Title typography should match American superhero comic style
"""

        try:
            # Retry with fixed 5s wait for rate limits (429)
            max_retries = 3
            response = None
            for attempt in range(max_retries):
                try:
                    response = await self.client.aio.models.generate_content(
                        model=self._model,
                        contents=[
                            {
                                "role": "user",
                                "parts": [{"text": base_prompt}]
                            }
                        ],
                        config=genai_types.GenerateContentConfig(
                            response_modalities=["TEXT", "IMAGE"],
                            temperature=0.8,
                        )
                    )
                    break
                except ClientError as e:
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        logger.warning(
                            "CoverGen: Rate limited (attempt %d/%d), waiting 15s...",
                            attempt + 1, max_retries,
                        )
                        await asyncio.sleep(15)
                    else:
                        raise

            if response is None:
                raise GCPCongestionError(
                    "GCP is congested right now. Please try again in about 5 minutes."
                )

            panels = []
            if response.candidates and response.candidates[0].content.parts:
                for i, part in enumerate(response.candidates[0].content.parts):
                    if part.inline_data:
                        image_data = part.inline_data.data
                        if isinstance(image_data, str):
                            image_data = base64.b64decode(image_data)
                        
                        filename = f"cover_{uuid.uuid4().hex[:6]}.png"
                        url = await upload_image(
                            image_bytes=image_data,
                            project_id=project_id,
                            filename=filename,
                            category="comic_pages"
                        )
                        
                        panels.append(PanelMetadata(
                            panel_id=f"cover_{uuid.uuid4().hex[:6]}",
                            scene_id="cover",
                            panel_number=1,
                            image_url=url,
                            caption="",
                            speech_bubbles=[],
                            mood=scene.get("mood", "dramatic"),
                            prompt_used=base_prompt[:500],
                        ))

            return ComicPage(
                page_number=0,  # Cover page
                panels=panels,
                raw_text="COVER PAGE",
            )

        except Exception as e:
            logger.error(f"Cover generation failed: {e}")
            # Return empty cover page on failure
            return ComicPage(page_number=0, panels=[], raw_text="Cover generation failed")

    async def generate_manga_cover(
        self,
        scene: dict,
        project_id: str,
        project_title: str = "Untitled Story",
    ) -> MangaPage:
        """Generate a manga cover page with single full-page image."""
        # Enhanced manga cover prompt
        base_prompt = f"""Create an epic manga cover illustration with title.

PROJECT TITLE: "{project_title}"
STORY SCENE: {scene.get('action', '')}
VISUAL ELEMENTS: {scene.get('visual_description', '')}
SETTING: {scene.get('location', '')}, {scene.get('time_of_day', '')}
MOOD: {scene.get('mood', 'dramatic')}

MANGA COVER REQUIREMENTS:
- Single panel covering entire page, no borders or multiple panels
- Project title "{project_title}" prominently displayed at the top in bold manga-style lettering
- Japanese Seinen manga art style with high contrast black and white
- Professional screentones and halftone patterns
- Bold, dramatic composition with dynamic angles
- Protagonist prominently featured in center below title
- Title should be integrated into the cover design in manga style
- Professional manga cover layout with visual impact
- Expressive character art with detailed faces and emotions
- Dynamic background elements that support the main character
- All text elements must be in ENGLISH only (strictly enforced) — NO Japanese/Chinese/Korean characters
- SPELLING CHECK: The title is "{project_title}" — spell it EXACTLY as shown, letter by letter
- Double-check every letter in the title before rendering — zero tolerance for typos

TECHNICAL REQUIREMENTS:
- Single panel covering entire page with no empty spaces
- High contrast black and white artwork with screentone patterns
- Professional manga publishing quality
- Title typography should match Japanese manga style but in English
"""

        try:
            # Retry with fixed 5s wait for rate limits (429)
            max_retries = 3
            response = None
            for attempt in range(max_retries):
                try:
                    response = await self.client.aio.models.generate_content(
                        model=self._model,
                        contents=[
                            {
                                "role": "user",
                                "parts": [{"text": base_prompt}]
                            }
                        ],
                        config=genai_types.GenerateContentConfig(
                            response_modalities=["TEXT", "IMAGE"],
                            temperature=0.8,
                        )
                    )
                    break
                except ClientError as e:
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        logger.warning(
                            "MangaCoverGen: Rate limited (attempt %d/%d), waiting 15s...",
                            attempt + 1, max_retries,
                        )
                        await asyncio.sleep(15)
                    else:
                        raise

            if response is None:
                raise GCPCongestionError(
                    "GCP is congested right now. Please try again in about 5 minutes."
                )

            panels = []
            if response.candidates and response.candidates[0].content.parts:
                for i, part in enumerate(response.candidates[0].content.parts):
                    if part.inline_data:
                        image_data = part.inline_data.data
                        if isinstance(image_data, str):
                            image_data = base64.b64decode(image_data)
                        
                        filename = f"cover_{uuid.uuid4().hex[:6]}.png"
                        url = await upload_image(
                            image_bytes=image_data,
                            project_id=project_id,
                            filename=filename,
                            category="manga_pages"
                        )
                        
                        panels.append(PanelMetadata(
                            panel_id=f"cover_{uuid.uuid4().hex[:6]}",
                            scene_id="cover",
                            panel_number=1,
                            image_url=url,
                            caption="",
                            speech_bubbles=[],
                            mood=scene.get("mood", "dramatic"),
                            prompt_used=base_prompt[:500],
                        ))

            return MangaPage(
                page_number=0,  # Cover page
                panels=panels,
                raw_text="COVER PAGE",
            )

        except Exception as e:
            logger.error(f"Manga cover generation failed: {e}")
            return MangaPage(page_number=0, panels=[], raw_text="Cover generation failed")

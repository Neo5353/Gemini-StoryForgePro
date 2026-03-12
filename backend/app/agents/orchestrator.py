"""C-3PO — Master Orchestrator Agent

Coordinates all sub-agents for the StoryForge Pro pipeline.
Routes tasks to the appropriate specialist agent.

Now fully wired with HAL 9000's AI integration layer.
"Sir, the possibility of successfully navigating this pipeline
is approximately 3,720 to 1." — But HAL never fails.
"""

import asyncio
import logging
from typing import Callable, Coroutine, Any, Optional

from app.agents.hal import ScriptAnalyzer
from app.agents.editor import EditAgent
from app.services.content_sanitizer import sanitize_scenes
from app.models.schemas import (
    CharacterSheet,
    CharacterView,
    OutputMode,
    PanelPage,
    ParsedScript,
    ProjectStatus,
    SceneBeat,
    TrailerProject,
    TrailerClip,
)
from app.services.image_gen import ImageGenService
from app.services.interleaved_gen import InterleavedGenService
from app.services.style_engine import StyleEngine
from app.services import firestore

# Type alias for progress callbacks
ProgressCallback = Optional[Callable[[dict], Coroutine[Any, Any, None]]]

logger = logging.getLogger(__name__)

# Sub-agent definitions
AGENTS = {
    "hal": "Script analysis, AI generation, director style application",
    "wall_e": "Video pipeline — Veo generation, ffmpeg assembly",
    "r2d2": "Data storage — Firestore, Cloud Storage",
    "tars": "Backend services — export, API logic",
    "sonny": "Frontend rendering instructions",
    "baymax": "UX polish and accessibility",
}

# Panel layout rules (for reference - actual logic enforces these rules in generation loop)
PANEL_LAYOUT_RULES = {
    "comic": "1 scene per page, 4-6 panels per scene (scene broken into sequential moments)",
    "manga": "1 scene per page, 4-6 panels per scene (scene broken into sequential moments)", 
    "storyboard": "2 LARGE panels per page covering ENTIRE PAGE, scenes span multiple pages (4-6 panels per scene total)",
}

# Legacy constant (not used in new logic)
PANELS_PER_PAGE = {
    "comic": 6,  # Legacy - actual logic: 1 scene = 1 page with 4-6 panels
    "manga": 4,  # Legacy - actual logic: 1 scene = 1 page with 4-6 panels
    "storyboard": 2,  # Still used: 2 panels per page, scenes span multiple pages
}


class StoryForgeOrchestrator:
    """C-3PO: The protocol droid that keeps everyone in line.

    Now properly wired to HAL 9000 for script analysis,
    the StyleEngine for director vision, ImageGenService for
    Nano Banana generation, InterleavedGenService for full pages,
    and the EditAgent for conversational edits.
    """

    def __init__(self, director_styles: dict):
        self.director_styles = director_styles

        # Initialize the AI integration layer
        self.style_engine = StyleEngine()
        self.script_analyzer = ScriptAnalyzer()
        self.image_gen = ImageGenService(style_engine=self.style_engine)
        self.interleaved_gen = InterleavedGenService(style_engine=self.style_engine)
        self.editor = EditAgent(
            style_engine=self.style_engine,
            image_gen=self.image_gen,
        )

        logger.info(
            "C-3PO: Orchestrator initialized with %d director styles. "
            "All sub-agents online.",
            len(director_styles),
        )

    def _resolve_director(self, director_id: Optional[str]) -> tuple[str, dict]:
        """Resolve director ID to full style dict.

        Returns:
            Tuple of (director_id, director_style_dict).

        Falls back to 'nolan' if director_id is not a known director
        (e.g., it's a visual style ID like 'american', 'shonen', etc.)
        """
        if not director_id:
            director_id = "nolan"
            logger.info("C-3PO: No director specified, defaulting to '%s'", director_id)

        try:
            style = self.style_engine.get_style(director_id)
            return director_id, style
        except KeyError:
            # director_id is probably a visual style (comic/manga/storyboard),
            # not a director. Fall back to nolan for camera/composition guidance.
            logger.info(
                "C-3PO: '%s' is not a director, treating as visual style. "
                "Using 'nolan' for composition guidance.", director_id,
            )
            fallback_style = self.style_engine.get_style("nolan")
            # Inject the visual style ID so downstream can use it
            fallback_style = {**fallback_style, "_visual_style": director_id}
            return "nolan", fallback_style

    async def process_script(
        self,
        script: str,
        format: str,
        director_id: Optional[str] = None,
    ) -> ParsedScript:
        """Phase 1: Parse script into scene beats.

        Delegates to HAL for script analysis with director-style-aware
        camera suggestions.

        Args:
            script: Raw script text.
            format: Output format (comic, manga, storyboard, trailer).
            director_id: Director style ID. Defaults to 'nolan'.

        Returns:
            ParsedScript with enriched scene beats.
        """
        director_id, director_style = self._resolve_director(director_id)

        logger.info(
            "C-3PO: Phase 1 — Script analysis. Director: %s, Mode: %s",
            director_style.get("name", "?"),
            format,
        )

        parsed = await self.script_analyzer.analyze_script(
            script_text=script,
            director_style=director_style,
            output_mode=format,
        )

        logger.info(
            "C-3PO: Script parsed — %d scenes, %d characters, %d locations, "
            "total duration: %.1fs",
            len(parsed.scenes),
            len(parsed.characters),
            len(parsed.locations),
            parsed.total_estimated_duration,
        )

        return parsed

    async def generate_characters(
        self,
        project_id: str,
        characters: list,
        director_id: Optional[str] = None,
        script_context: str = "",
        progress_callback: ProgressCallback = None,
    ) -> list[CharacterSheet]:
        """Phase 2: Generate character reference sheets.

        Delegates to HAL/ImageGen for Nano Banana Pro generation.
        Results are cached for consistency across all subsequent panels.

        Args:
            project_id: Project ID for storage.
            characters: List of character dicts or character name strings.
            director_id: Director style ID.
            script_context: Full script text for generating visual descriptions.
            progress_callback: Async callback for WebSocket progress updates.

        Returns:
            List of CharacterSheet with reference images.
        """
        director_id, director_style = self._resolve_director(director_id)

        # Normalize characters to list of dicts
        char_dicts: list[dict] = []
        for c in characters:
            if isinstance(c, str):
                char_dicts.append({"name": c, "description": c})
            elif isinstance(c, dict):
                char_dicts.append(c)
            else:
                char_dicts.append({"name": str(c), "description": str(c)})

        logger.info(
            "C-3PO: Phase 2 — Character generation. %d characters, Director: %s",
            len(char_dicts),
            director_style.get("name", "?"),
        )

        # If characters lack descriptions, use Gemini to generate them
        needs_desc = [c for c in char_dicts if not c.get("physical_description") and not c.get("description")]
        if needs_desc and script_context:
            from app.services.character_designer import generate_character_descriptions
            desc_map = await generate_character_descriptions(
                [c.get("name", "Unknown") for c in needs_desc],
                script_context,
            )
            for c in char_dicts:
                name = c.get("name", "")
                if name in desc_map and not c.get("physical_description"):
                    c["physical_description"] = desc_map[name]

        sheets: list[CharacterSheet] = []

        for i, char in enumerate(char_dicts):
            name = char.get("name", "Unknown")
            desc = char.get("physical_description", char.get("description", name))

            if progress_callback:
                await progress_callback({
                    "type": "progress",
                    "stage": "characters",
                    "current": i + 1,
                    "total": len(char_dicts),
                    "message": f"Generating character sheet for {name}...",
                })

            refs = await self.image_gen.generate_character_ref(
                character_desc=desc,
                character_name=name,
                director_style=director_style,
                director_id=director_id,
                project_id=project_id,
                views=["front", "side", "expression"],
            )

            views = [
                CharacterView(
                    view_type=r.metadata.get("view", "unknown"),
                    image_url=r.image_url,
                    prompt_used=r.prompt_used,
                )
                for r in refs
            ]

            sheets.append(
                CharacterSheet(
                    character_name=name,
                    description=desc,
                    views=views,
                    style_applied=director_style.get("name", ""),
                )
            )

            logger.info("C-3PO: Character '%s' — %d views generated", name, len(views))

        return sheets

    async def generate_panels(
        self,
        project_id: str,
        scenes: list,
        mode: str,
        director_id: Optional[str] = None,
        character_descriptions: Optional[dict] = None,
        scene_ids: Optional[list[str]] = None,
        progress_callback: ProgressCallback = None,
        project_title: Optional[str] = None,
        page_callback: Optional[ProgressCallback] = None,
    ) -> list[PanelPage]:
        """Phase 3: Generate visual panels (comic/manga/storyboard).

        Uses interleaved generation for full pages with narration
        woven between panel images.

        Args:
            project_id: Project ID for storage.
            scenes: List of scene beat dicts or SceneBeat objects.
            mode: Output mode (comic, manga, storyboard).
            director_id: Director style ID (ignored for comic/manga/storyboard).
            character_descriptions: Optional dict mapping character name to description.
            scene_ids: If provided, only generate panels for these scene IDs.
            progress_callback: Async callback for WebSocket progress updates.

        Returns:
            List of PanelPage objects.
            
        Note: Director styles are only applicable for trailers, not panels.
        """
        # Director styles are not used for comic/manga/storyboard generation
        panels_per_page = PANELS_PER_PAGE.get(mode, 6)

        # Convert SceneBeat objects to dicts if needed
        scene_list = []
        for s in scenes:
            if hasattr(s, "model_dump"):
                scene_list.append(s.model_dump())
            elif isinstance(s, dict):
                scene_list.append(s)
            else:
                scene_list.append({"action": str(s)})

        # Filter by scene_ids if provided
        if scene_ids:
            scene_list = [s for s in scene_list if s.get("scene_id") in scene_ids]

        # Ensure we have scenes to work with
        if not scene_list:
            logger.warning("No scenes available for panel generation")
            return []

        # Content sanitization — rephrase blocked content for safe image generation
        if progress_callback:
            await progress_callback({
                "type": "progress",
                "stage": "sanitize",
                "current": 0,
                "total": len(scene_list),
                "message": "Scanning script for content safety...",
            })

        scene_list = await sanitize_scenes(scene_list)

        logger.info(
            "C-3PO: Phase 3 — Panel generation. %d scenes, mode=%s, %d panels/page",
            len(scene_list),
            mode,
            panels_per_page,
        )

        pages: list[PanelPage] = []
        page_number = 0  # Start at 0 for cover page

        # Generate cover page for comics and manga
        if mode in ["comic", "manga"] and scene_list:
            if progress_callback:
                await progress_callback({
                    "type": "progress",
                    "stage": "cover",
                    "current": 1,
                    "total": 1,
                    "overall_progress_pct": 5,
                    "message": f"Generating cover page...",
                })

            # Create cover scene from first scene or story title
            first_scene = scene_list[0]
            cover_scene = {
                "scene_id": "cover",
                "action": f"Cover art for the story. {first_scene.get('visual_description', first_scene.get('action', ''))}",
                "visual_description": f"Epic cover illustration showcasing the main theme and mood of the story",
                "location": first_scene.get('location', 'Unknown'),
                "mood": "dramatic, eye-catching, heroic",
                "time_of_day": first_scene.get('time_of_day', 'day'),
                "characters": first_scene.get('characters', [])
            }

            if mode == "comic":
                cover_result = await self.interleaved_gen.generate_comic_cover(
                    scene=cover_scene,
                    project_id=project_id,
                    project_title=project_title or "Untitled Story",
                )
            else:  # manga
                cover_result = await self.interleaved_gen.generate_manga_cover(
                    scene=cover_scene,
                    project_id=project_id,
                    project_title=project_title or "Untitled Story",
                )

            cover_page = PanelPage(
                page_number=0,  # Cover page
                panels=cover_result.panels,
            )
            pages.append(cover_page)
            if page_callback:
                await page_callback(cover_page)

            logger.info("C-3PO: Cover page generated — %d panels", len(cover_result.panels))

            # Brief cooldown after cover generation
            logger.info("C-3PO: Waiting 5s before content pages...")
            await asyncio.sleep(5)

        # Generate content pages
        page_number = 1

        # Apply user's specific layout rules
        if mode in ["comic", "manga"]:
            # RULE: 1 scene per page, 4-6 panels per scene
            for i, scene in enumerate(scene_list):
                scene_dicts = [scene]  # One scene per page

                # Fixed 5s delay between pages
                if i > 0:
                    logger.info("C-3PO: Waiting 5s before page %d...", page_number)
                    await asyncio.sleep(5)

                total_pages = len(scene_list) + (1 if mode in ["comic", "manga"] else 0)  # +1 for cover
                if progress_callback:
                    await progress_callback({
                        "type": "progress",
                        "stage": "panels",
                        "current": page_number,
                        "total": len(scene_list),
                        "overall_progress_pct": int((page_number / total_pages) * 100) if total_pages else 0,
                        "message": f"Page {page_number}/{len(scene_list)} — {scene.get('title', 'Untitled')}",
                    })

                if mode == "comic":
                    result = await self.interleaved_gen.generate_comic_page(
                        scenes=scene_dicts,
                        project_id=project_id,
                        page_number=page_number,
                        character_descriptions=character_descriptions,
                        project_title=project_title,
                    )
                else:  # manga
                    result = await self.interleaved_gen.generate_manga_page(
                        scenes=scene_dicts,
                        project_id=project_id,
                        page_number=page_number,
                        character_descriptions=character_descriptions,
                        project_title=project_title,
                    )

                new_page = PanelPage(
                    page_number=page_number,
                    panels=result.panels,
                )
                pages.append(new_page)
                if page_callback:
                    await page_callback(new_page)

                total_panels = sum(len(p.panels) for p in pages)
                if progress_callback:
                    await progress_callback({
                        "type": "progress",
                        "stage": "panels",
                        "current": page_number,
                        "total": len(scene_list),
                        "overall_progress_pct": int(((page_number) / total_pages) * 100) if total_pages else 0,
                        "message": f"Page {page_number}/{len(scene_list)} done — {total_panels} panels so far",
                    })

                logger.info(
                    "C-3PO: Page %d generated — %d panels (Scene: %s)",
                    page_number,
                    len(result.panels),
                    scene.get('title', scene.get('scene_id', 'Unknown'))
                )
                page_number += 1

        elif mode == "storyboard":
            # RULE: 4-6 panels per scene, only 2 LARGE panels per page covering entire page
            storyboard_page_idx = 0
            for scene in scene_list:
                scene_panels_needed = 4
                pages_per_scene = (scene_panels_needed + 1) // 2

                for page_in_scene in range(pages_per_scene):
                    scene_dicts = [scene]

                    # Fixed 5s delay between pages
                    if storyboard_page_idx > 0:
                        logger.info("C-3PO: Waiting 5s before storyboard page %d...", page_number)
                        await asyncio.sleep(5)
                    storyboard_page_idx += 1

                    total_storyboard_pages = len(scene_list) * pages_per_scene
                    if progress_callback:
                        pct = int((storyboard_page_idx / total_storyboard_pages) * 100) if total_storyboard_pages else 0
                        await progress_callback({
                            "type": "progress",
                            "stage": "storyboard",
                            "current": page_number,
                            "total": total_storyboard_pages,
                            "overall_progress_pct": pct,
                            "message": f"Page {storyboard_page_idx}/{total_storyboard_pages} — {scene.get('title', 'Untitled')}",
                        })

                    result = await self.interleaved_gen.generate_storyboard_page(
                        scenes=scene_dicts,
                        project_id=project_id,
                        page_number=page_number,
                        character_descriptions=character_descriptions,
                        project_title=project_title,
                    )

                    new_page = PanelPage(
                        page_number=page_number,
                        panels=result.panels,
                    )
                    pages.append(new_page)
                    if page_callback:
                        await page_callback(new_page)

                    total_panels = sum(len(p.panels) for p in pages)
                    if progress_callback:
                        pct = int((storyboard_page_idx / total_storyboard_pages) * 100) if total_storyboard_pages else 0
                        await progress_callback({
                            "type": "progress",
                            "stage": "storyboard",
                            "current": storyboard_page_idx,
                            "total": total_storyboard_pages,
                            "overall_progress_pct": pct,
                            "message": f"Page {storyboard_page_idx}/{total_storyboard_pages} done — {total_panels} panels",
                        })

                    logger.info(
                        "C-3PO: Storyboard page %d generated — %d panels (Scene: %s)",
                        page_number,
                        len(result.panels),
                        scene.get('title', scene.get('scene_id', 'Unknown'))
                    )
                    page_number += 1

        else:
            # Fallback for other modes
            for scene in scene_list:
                scene_dicts = [scene]
                
                result = await self.interleaved_gen.generate_comic_page(
                    scenes=scene_dicts,
                    project_id=project_id,
                    page_number=page_number,
                    character_descriptions=character_descriptions,
                    project_title=project_title,
                )

                pages.append(
                    PanelPage(
                        page_number=page_number,
                        panels=result.panels,
                    )
                )
                page_number += 1

        return pages

    async def generate_trailer(
        self,
        project_id: str,
        scenes: list,
        director_id: Optional[str] = None,
        scene_ids: Optional[list[str]] = None,
        progress_callback: ProgressCallback = None,
    ):
        """Phase 4: Generate cinematic trailer (max 3 min).

        Delegates to WALL-E for Veo pipeline.
        HAL provides key frames and style direction.

        Args:
            project_id: Project ID.
            scenes: Scene beats (dicts or SceneBeat objects).
            director_id: Director style ID.
            scene_ids: Specific scene IDs to include.
            progress_callback: Async callback for progress updates.
        """
        director_id, director_style = self._resolve_director(director_id)

        # Normalize to dicts
        scene_dicts = []
        for s in scenes:
            if hasattr(s, "model_dump"):
                scene_dicts.append(s.model_dump())
            elif isinstance(s, dict):
                scene_dicts.append(s)
            else:
                scene_dicts.append({"action": str(s)})

        # Filter by scene_ids if provided
        if scene_ids:
            scene_dicts = [s for s in scene_dicts if s.get("scene_id") in scene_ids]

        logger.info(
            "C-3PO: Phase 4 — Trailer generation. %d scenes, Director: %s",
            len(scene_dicts),
            director_style.get("name", "?"),
        )

        # Generate key frames for each scene (HAL's contribution to trailer)
        key_frames = []
        for i, scene_dict in enumerate(scene_dicts):
            if progress_callback:
                await progress_callback({
                    "type": "progress",
                    "stage": "trailer_keyframes",
                    "current": i + 1,
                    "total": len(scene_dicts),
                    "message": f"Generating key frame {i + 1}/{len(scene_dicts)}...",
                })
            kf = await self.image_gen.generate_key_frame(
                scene=scene_dict,
                director_style=director_style,
                project_id=project_id,
            )
            key_frames.append(kf)

        # Build video prompts for each scene
        video_prompts = []
        for scene_dict in scene_dicts:
            prompt = self.style_engine.build_video_prompt(
                scene=scene_dict,
                director_style=director_style,
            )
            video_prompts.append(prompt)

        # Try WALL-E's full pipeline if available, fallback to basic generation
        try:
            from app.services.trailer_pipeline import TrailerPipeline
            pipeline = TrailerPipeline()
            trailer_scenes = []
            for i, sd in enumerate(scene_dicts):
                trailer_scenes.append({
                    "scene_id": sd.get("scene_id", f"scene_{i}"),
                    "description": sd.get("visual_description", sd.get("action", "")),
                    "dialogue": "",
                    "sfx": "",
                    "ambient": "",
                    "duration_target": sd.get("estimated_duration", 20.0),
                    "transition": "dissolve",
                    "key_frame_path": key_frames[i].image_url if i < len(key_frames) else None,
                })

            async def pipeline_progress(pid, data):
                if progress_callback:
                    await progress_callback(data)

            result = await pipeline.generate_trailer(
                project_id=project_id,
                scenes=trailer_scenes,
                director_style=director_id,
                progress_callback=pipeline_progress,
            )

            return TrailerProject(
                clips=[
                    TrailerClip(
                        clip_id=sr.scene_id,
                        scene_id=sr.scene_id,
                        video_url=sr.video_path,
                        duration=sr.duration_seconds,
                        status="ready" if sr.video_path else "failed",
                    )
                    for sr in result.scenes
                ],
                total_duration=result.duration_seconds,
                final_video_url=result.output_path,
                status="complete",
            )
        except Exception as e:
            logger.warning("C-3PO: Full trailer pipeline unavailable (%s), returning key frames", e)
            return TrailerProject(
                clips=[],
                total_duration=0.0,
                final_video_url="",
                status="key_frames_ready",
            )

    async def generate_trailer_pipeline(
        self,
        project_id: str,
        scenes: list,
        director_id: Optional[str] = None,
        scene_ids: Optional[list[str]] = None,
        progress_callback: ProgressCallback = None,
    ) -> TrailerProject:
        """Alias for generate_trailer — used by route handlers."""
        return await self.generate_trailer(
            project_id=project_id,
            scenes=scenes,
            director_id=director_id,
            scene_ids=scene_ids,
            progress_callback=progress_callback,
        )

    async def full_pipeline(
        self,
        project_id: str,
        script: str,
        script_format: str = "freeform",
        output_mode: str = "comic",
        director_id: Optional[str] = None,
        progress_callback: ProgressCallback = None,
    ):
        """Run the full StoryForge pipeline end-to-end.

        Phase 1: Parse script → Phase 2: Characters → Phase 3: Panels/Trailer

        Called by project creation route to run everything in background.
        """
        from app.services import firestore

        try:
            # Phase 1: Parse script
            if progress_callback:
                await progress_callback({
                    "type": "progress",
                    "stage": "parsing",
                    "message": "Analyzing script...",
                })
            await firestore.update_project_status(project_id, ProjectStatus.PARSING)

            parsed = await self.process_script(
                script=script,
                format=output_mode,
                director_id=director_id,
            )
            await firestore.save_parsed_script(project_id, parsed)

            if progress_callback:
                await progress_callback({
                    "type": "progress",
                    "stage": "parsing",
                    "message": f"Script parsed: {len(parsed.scenes)} scenes, {len(parsed.characters)} characters",
                })

            # Phase 2: Generate characters
            await firestore.update_project_status(
                project_id, ProjectStatus.GENERATING_CHARACTERS
            )
            characters_input = parsed.characters_detailed or [
                {"name": c} for c in parsed.characters
            ]
            sheets = await self.generate_characters(
                project_id=project_id,
                characters=characters_input,
                director_id=director_id,
                script_context=script,
                progress_callback=progress_callback,
            )
            await firestore.save_characters(project_id, sheets)

            # Phase 3: Generate output based on mode
            if output_mode == "trailer":
                await firestore.update_project_status(
                    project_id, ProjectStatus.GENERATING_TRAILER
                )
                trailer = await self.generate_trailer(
                    project_id=project_id,
                    scenes=parsed.scenes,
                    director_id=director_id,
                    progress_callback=progress_callback,
                )
                await firestore.save_trailer(project_id, trailer)
            else:
                await firestore.update_project_status(
                    project_id, ProjectStatus.GENERATING_PANELS
                )
                # Build character description map for panel context
                char_descs = {s.character_name: s.description for s in sheets}
                
                # Get project title for cover generation
                project_data = await firestore.get_project_raw(project_id)
                project_title = project_data.get("title", "Untitled Story") if project_data else "Untitled Story"
                
                pages = await self.generate_panels(
                    project_id=project_id,
                    scenes=parsed.scenes,
                    mode=output_mode,
                    director_id=director_id,
                    character_descriptions=char_descs,
                    progress_callback=progress_callback,
                    project_title=project_title,
                )
                await firestore.save_pages(project_id, pages)

            # Done!
            await firestore.update_project_status(project_id, ProjectStatus.COMPLETE)
            if progress_callback:
                await progress_callback({
                    "type": "complete",
                    "message": "Pipeline complete!",
                })

        except Exception as e:
            logger.error("C-3PO: Pipeline failed — %s", e, exc_info=True)
            await firestore.update_project_status(project_id, ProjectStatus.FAILED)
            if progress_callback:
                await progress_callback({
                    "type": "error",
                    "message": f"Pipeline failed: {str(e)}",
                })
            raise

    async def edit_scene(
        self,
        project_id: str,
        scene_id: str,
        instruction: str,
        scenes: list[dict],
        panels: list[dict],
        director_id: Optional[str] = None,
        mode: str = "comic",
    ) -> dict:
        """Handle conversational edit requests.

        Parses the instruction, determines scope, and routes to
        the appropriate regeneration pipeline.

        Args:
            project_id: Project ID.
            scene_id: Target scene ID (may be overridden by edit parsing).
            instruction: Natural language edit instruction.
            scenes: Current scene beats.
            panels: Current panel metadata.
            director_id: Director style ID.
            mode: Output mode.

        Returns:
            Edit result dict with regenerated assets.
        """
        director_id, director_style = self._resolve_director(director_id)

        logger.info(
            "C-3PO: Edit request — '%s' (scene: %s, director: %s)",
            instruction[:80],
            scene_id,
            director_style.get("name", "?"),
        )

        # Step 1: Parse the edit instruction
        edit_intent = await self.editor.parse_edit_instruction(
            instruction=instruction,
            scenes=scenes,
            panels=panels,
            director_style=director_style,
        )

        # If no target IDs parsed but we have a scene_id, use it
        if not edit_intent.get("target_ids") and scene_id:
            edit_intent["target_ids"] = [scene_id]

        # Step 2: Apply the edit
        result = await self.editor.apply_edit(
            edit_intent=edit_intent,
            scenes=scenes,
            panels=panels,
            director_style=director_style,
            director_id=director_id,
            project_id=project_id,
            mode=mode,
        )

        logger.info(
            "C-3PO: Edit applied — %d panels regenerated, %d characters regenerated",
            len(result.get("regenerated_panels", [])),
            len(result.get("regenerated_characters", [])),
        )

        return result

"""Trailer Pipeline — WALL-E's masterpiece assembler.

End-to-end orchestrator that takes parsed scenes and a director style,
then generates key frames, Veo video clips, extends them, and assembles
the final cinematic trailer via ffmpeg.

Pipeline:
  Script scenes → Key frames → Veo clips → Extend → FFmpeg assembly → Final MP4
"""

import asyncio
import json
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional

from app.config.settings import settings
from app.services.ffmpeg_service import FFmpegService, SceneClip, TransitionType
from app.services.progress_tracker import GenerationPhase, ProgressTracker
from app.services.veo_service import VeoService, VeoAPIError, VeoTimeoutError

logger = logging.getLogger("storyforge.pipeline")

# Type aliases
ProgressCallback = Callable[[str, dict], Coroutine[Any, Any, None]]


@dataclass
class SceneSpec:
    """Specification for a single trailer scene."""
    scene_id: str
    description: str
    dialogue: str = ""
    sfx: str = ""
    ambient: str = ""
    duration_target: float = 20.0  # Target duration in seconds
    transition: str = "dissolve"
    key_frame_path: Optional[str] = None  # Pre-generated key frame
    character_refs: List[str] = field(default_factory=list)


@dataclass
class SceneResult:
    """Result of generating a single scene."""
    scene_id: str
    video_path: str
    duration_seconds: float
    key_frame_path: str
    last_frame_path: Optional[str] = None
    has_audio: bool = False
    error: Optional[str] = None


@dataclass
class TrailerResult:
    """Final trailer generation result."""
    output_path: str
    duration_seconds: float
    scene_count: int
    resolution: str = "1080p"
    has_audio: bool = True
    scenes: List[SceneResult] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class TrailerPipeline:
    """End-to-end trailer generation pipeline.

    WALL-E patiently collects each beautiful piece —
    key frames, video clips, extensions — and assembles
    them into a cinematic whole. If something breaks,
    WALL-E tries again. If it still breaks, WALL-E
    gently moves on and makes the best of what's there.
    """

    # Limits
    MAX_TRAILER_DURATION = 180  # 3 minutes
    MAX_SCENES = 8
    BASE_CLIP_DURATION = 8  # Veo generates 8s base clips
    MAX_EXTENSIONS = 3  # Max extend calls per scene
    EXTENSION_DURATION = 7  # Seconds per extension
    MAX_RETRY = 1  # Retry once on failure

    def __init__(
        self,
        veo_service: Optional[VeoService] = None,
        ffmpeg_service: Optional[FFmpegService] = None,
        progress_tracker: Optional[ProgressTracker] = None,
        work_dir: Optional[str] = None,
    ):
        self.veo = veo_service or VeoService()
        self.work_dir = work_dir or tempfile.mkdtemp(prefix="storyforge_trailer_")
        self.ffmpeg = ffmpeg_service or FFmpegService(
            work_dir=os.path.join(self.work_dir, "ffmpeg")
        )
        self.progress = progress_tracker or ProgressTracker()

        Path(self.work_dir).mkdir(parents=True, exist_ok=True)

    def _load_director_style(self, director_style: Optional[str]) -> dict:
        """Load director style config from director_styles.json."""
        if not director_style:
            return {}

        styles_path = Path(__file__).parent.parent / "config" / "director_styles.json"
        try:
            with open(styles_path) as f:
                styles = json.load(f).get("directors", {})
            return styles.get(director_style, {})
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning("Failed to load director styles: %s", e)
            return {}

    def _build_veo_prompt(
        self,
        scene: SceneSpec,
        style: dict,
        is_continuation: bool = False,
    ) -> str:
        """Build a rich Veo prompt from scene spec and director style.

        Includes visual description, dialogue cues, SFX, and style modifier.
        """
        parts = [scene.description]

        # Audio instructions for Veo's native audio generation
        if scene.dialogue:
            parts.append(f"Dialogue: {scene.dialogue}")
        if scene.sfx:
            parts.append(f"Sound effects: {scene.sfx}")
        if scene.ambient:
            parts.append(f"Ambient audio: {scene.ambient}")

        # Camera/editing hints from director style
        if style:
            camera_style = style.get("camera_style", {})
            if camera_style.get("movements"):
                parts.append(f"Camera: {camera_style['movements'][0]}")

            audio_mood = style.get("audio_mood", {})
            if audio_mood.get("score_feel") and not is_continuation:
                parts.append(f"Musical mood: {audio_mood['score_feel'][:100]}")

        prompt = ". ".join(parts)

        # Append director's visual style modifier
        style_modifier = style.get("prompt_modifier", "")
        if style_modifier:
            prompt = f"{prompt}. {style_modifier}"

        return prompt

    def _map_transition(self, transition_str: str) -> TransitionType:
        """Map scene transition string to TransitionType enum."""
        mapping = {
            "cut": TransitionType.CUT,
            "dissolve": TransitionType.DISSOLVE,
            "fade_in": TransitionType.FADE_IN,
            "fade_out": TransitionType.FADE_OUT,
            "cross_fade": TransitionType.CROSS_FADE,
        }
        return mapping.get(transition_str, TransitionType.DISSOLVE)

    async def _generate_key_frame(
        self,
        scene: SceneSpec,
        style: dict,
        project_id: str,
    ) -> str:
        """Generate a key frame image for a scene.

        Uses Gemini image generation (placeholder — HAL agent handles this).
        For now, returns the pre-set key_frame_path or raises.
        """
        if scene.key_frame_path:
            return scene.key_frame_path

        # TODO: Integration with HAL agent's image generation
        # For now, this would be called by the orchestrator which provides key frames
        raise ValueError(
            f"Scene {scene.scene_id} has no key frame. "
            "Key frame generation should be handled by the image generation service."
        )

    async def _generate_scene_video(
        self,
        scene: SceneSpec,
        style: dict,
        project_id: str,
        prev_last_frame: Optional[str] = None,
    ) -> SceneResult:
        """Generate a full video clip for a single scene.

        Steps:
        1. Use image-to-video with key frame (or first/last frame for continuity)
        2. Extend clip to reach target duration
        3. Extract last frame for next scene's continuity

        WALL-E retries once if something goes wrong.
        """
        scene_dir = os.path.join(self.work_dir, f"scene_{scene.scene_id}")
        Path(scene_dir).mkdir(parents=True, exist_ok=True)

        prompt = self._build_veo_prompt(scene, style)
        style_modifier = style.get("prompt_modifier", "")

        await self.progress.update(
            project_id,
            GenerationPhase.VIDEO_GEN.value,
            scene.scene_id,
            10.0,
            f"Generating base clip for scene {scene.scene_id}...",
        )

        # Step 1: Generate base clip (8 seconds)
        base_clip_path = None
        for attempt in range(self.MAX_RETRY + 1):
            try:
                if prev_last_frame and scene.key_frame_path:
                    # Use first/last frame for smooth continuity
                    result = await self.veo.first_last_frame(
                        first_image=prev_last_frame,
                        last_image=scene.key_frame_path,
                        prompt=prompt,
                        duration=self.BASE_CLIP_DURATION,
                        local_dir=scene_dir,
                        style_modifier=style_modifier,
                    )
                elif scene.key_frame_path:
                    # Image-to-video from key frame
                    result = await self.veo.image_to_video(
                        image_path=scene.key_frame_path,
                        prompt=prompt,
                        duration=self.BASE_CLIP_DURATION,
                        local_dir=scene_dir,
                        style_modifier=style_modifier,
                    )
                else:
                    # Text-to-video fallback
                    result = await self.veo.text_to_video(
                        prompt=prompt,
                        duration=self.BASE_CLIP_DURATION,
                        local_dir=scene_dir,
                        style_modifier=style_modifier,
                    )

                base_clip_path = result.local_path or result.video_url
                break

            except (VeoAPIError, VeoTimeoutError) as e:
                if attempt < self.MAX_RETRY:
                    logger.warning(
                        "Scene %s attempt %d failed, retrying: %s",
                        scene.scene_id, attempt + 1, e,
                    )
                    await asyncio.sleep(2)
                else:
                    logger.error("Scene %s failed after retry: %s", scene.scene_id, e)
                    return SceneResult(
                        scene_id=scene.scene_id,
                        video_path="",
                        duration_seconds=0,
                        key_frame_path=scene.key_frame_path or "",
                        error=str(e),
                    )

        await self.progress.update(
            project_id,
            GenerationPhase.VIDEO_GEN.value,
            scene.scene_id,
            50.0,
            f"Base clip ready. Extending scene {scene.scene_id}...",
        )

        # Step 2: Extend to target duration if needed
        current_path = base_clip_path
        current_duration = self.BASE_CLIP_DURATION
        extensions_done = 0

        while (
            current_duration < scene.duration_target
            and extensions_done < self.MAX_EXTENSIONS
        ):
            remaining = scene.duration_target - current_duration
            ext_seconds = min(self.EXTENSION_DURATION, int(remaining) + 1)

            continuation_prompt = self._build_veo_prompt(
                scene, style, is_continuation=True
            )

            try:
                ext_result = await self.veo.extend_video(
                    video_path=current_path,
                    prompt=continuation_prompt,
                    extension_seconds=ext_seconds,
                    local_dir=scene_dir,
                    style_modifier=style_modifier,
                )
                current_path = ext_result.local_path or ext_result.video_url
                current_duration += ext_seconds
                extensions_done += 1

                pct = 50 + (extensions_done / self.MAX_EXTENSIONS) * 40
                await self.progress.update(
                    project_id,
                    GenerationPhase.VIDEO_GEN.value,
                    scene.scene_id,
                    pct,
                    f"Extended to ~{current_duration}s ({extensions_done} extensions)",
                )

            except (VeoAPIError, VeoTimeoutError) as e:
                logger.warning(
                    "Extension %d for scene %s failed: %s. Using current clip.",
                    extensions_done + 1, scene.scene_id, e,
                )
                break

        # Step 3: Extract last frame for next scene continuity
        last_frame_path = None
        try:
            last_frame_path = await self.ffmpeg.extract_last_frame(
                current_path,
                os.path.join(scene_dir, "last_frame.png"),
            )
        except Exception as e:
            logger.warning(
                "Failed to extract last frame for scene %s: %s",
                scene.scene_id, e,
            )

        await self.progress.update(
            project_id,
            GenerationPhase.VIDEO_GEN.value,
            scene.scene_id,
            100.0,
            f"Scene {scene.scene_id} complete ({current_duration}s)",
        )

        return SceneResult(
            scene_id=scene.scene_id,
            video_path=current_path,
            duration_seconds=current_duration,
            key_frame_path=scene.key_frame_path or "",
            last_frame_path=last_frame_path,
            has_audio=True,
        )

    async def generate_trailer(
        self,
        project_id: str,
        scenes: List[Dict[str, Any]],
        director_style: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        music_path: Optional[str] = None,
        resolution: str = "1080p",
    ) -> TrailerResult:
        """Generate a complete cinematic trailer.

        This is the main entry point — WALL-E's magnum opus.

        Args:
            project_id: Unique project identifier.
            scenes: List of scene dicts with keys:
                - scene_id, description, dialogue, sfx, ambient,
                  duration_target, transition, key_frame_path
            director_style: Director style ID (e.g., "nolan", "cameron").
            progress_callback: Async callback for progress updates.
            title: Optional title card text.
            subtitle: Optional subtitle for title card.
            music_path: Optional background music track path.
            resolution: Output resolution.

        Returns:
            TrailerResult with path to final MP4 and metadata.
        """
        # Set up progress callback
        if progress_callback:
            self.progress = ProgressTracker(ws_callback=progress_callback)

        # Load director style
        style = self._load_director_style(director_style)
        logger.info(
            "Starting trailer generation for project %s (%d scenes, style=%s)",
            project_id, len(scenes), director_style or "default",
        )

        # Parse scene specs
        scene_specs = [
            SceneSpec(
                scene_id=s.get("scene_id", f"scene_{i}"),
                description=s.get("description", ""),
                dialogue=s.get("dialogue", ""),
                sfx=s.get("sfx", ""),
                ambient=s.get("ambient", ""),
                duration_target=min(
                    s.get("duration_target", 20.0),
                    self.MAX_TRAILER_DURATION / max(len(scenes), 1),
                ),
                transition=s.get("transition", "dissolve"),
                key_frame_path=s.get("key_frame_path"),
                character_refs=s.get("character_refs", []),
            )
            for i, s in enumerate(scenes[:self.MAX_SCENES])
        ]

        # ── Phase 1: Key Frames ──
        await self.progress.update(
            project_id, GenerationPhase.KEY_FRAMES.value,
            progress_pct=0, message="Preparing key frames...",
        )

        for spec in scene_specs:
            if not spec.key_frame_path:
                try:
                    spec.key_frame_path = await self._generate_key_frame(
                        spec, style, project_id
                    )
                except ValueError as e:
                    logger.warning("No key frame for scene %s: %s", spec.scene_id, e)

        # ── Phase 2: Video Generation (parallelized) ──
        await self.progress.update(
            project_id, GenerationPhase.VIDEO_GEN.value,
            progress_pct=0, message="Generating video clips...",
        )

        # Generate scenes — parallel but respecting continuity ordering
        # We generate in groups: scenes that need the previous scene's last frame
        # must wait, but independent scenes can run in parallel.
        scene_results: List[SceneResult] = []
        prev_last_frame: Optional[str] = None

        # Strategy: generate in batches of up to 4 concurrent,
        # but the first scene of each batch uses prev_last_frame from prior batch
        batch_size = min(4, self.veo.MAX_CONCURRENT)

        for batch_start in range(0, len(scene_specs), batch_size):
            batch = scene_specs[batch_start:batch_start + batch_size]
            tasks = []

            for i, spec in enumerate(batch):
                # Only the first scene in batch gets continuity frame
                frame_for_continuity = prev_last_frame if i == 0 else None
                tasks.append(
                    self._generate_scene_video(
                        spec, style, project_id, frame_for_continuity
                    )
                )

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error("Scene generation exception: %s", result)
                    scene_results.append(
                        SceneResult(
                            scene_id="unknown",
                            video_path="",
                            duration_seconds=0,
                            key_frame_path="",
                            error=str(result),
                        )
                    )
                else:
                    scene_results.append(result)
                    # Track last frame for continuity
                    if result.last_frame_path:
                        prev_last_frame = result.last_frame_path

        # Filter out failed scenes
        valid_scenes = [r for r in scene_results if r.video_path and not r.error]
        if not valid_scenes:
            await self.progress.mark_failed(project_id, "All scenes failed to generate")
            raise VeoAPIError("No scenes were successfully generated")

        logger.info(
            "%d/%d scenes generated successfully",
            len(valid_scenes), len(scene_specs),
        )

        # ── Phase 3: Assembly ──
        await self.progress.update(
            project_id, GenerationPhase.ASSEMBLY.value,
            progress_pct=0, message="Assembling trailer...",
        )

        # Build clip list for ffmpeg
        clips = []
        for i, result in enumerate(valid_scenes):
            spec = next(
                (s for s in scene_specs if s.scene_id == result.scene_id),
                scene_specs[min(i, len(scene_specs) - 1)],
            )
            clips.append(
                SceneClip(
                    path=result.video_path,
                    scene_id=result.scene_id,
                    duration_seconds=result.duration_seconds,
                    transition_in=self._map_transition(spec.transition),
                    transition_duration=1.0,
                )
            )

        # First clip gets fade_in
        if clips:
            clips[0].transition_in = TransitionType.FADE_IN

        output_dir = os.path.join(self.work_dir, "output")
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Stitch scenes
        stitched_path = os.path.join(output_dir, "stitched.mp4")
        current_path = await self.ffmpeg.stitch_scenes(clips, output_path=stitched_path)

        await self.progress.update(
            project_id, GenerationPhase.ASSEMBLY.value,
            progress_pct=40, message="Scenes stitched. Adding finishing touches...",
        )

        # Add title card if provided
        if title:
            current_path = await self.ffmpeg.add_title_card(
                current_path,
                title=title,
                subtitle=subtitle or "",
                output_path=os.path.join(output_dir, "titled.mp4"),
            )

        # Add music bed if provided
        if music_path and os.path.exists(music_path):
            current_path = await self.ffmpeg.add_music_bed(
                current_path,
                music_path=music_path,
                output_path=os.path.join(output_dir, "with_music.mp4"),
            )

        await self.progress.update(
            project_id, GenerationPhase.ASSEMBLY.value,
            progress_pct=70, message="Final encoding...",
        )

        # Final encode
        final_path = os.path.join(output_dir, f"trailer_{project_id}.mp4")
        final_path = await self.ffmpeg.encode_final(
            current_path,
            resolution=resolution,
            output_path=final_path,
        )

        # Get final duration
        final_duration = await self.ffmpeg.get_duration(final_path)

        await self.progress.mark_complete(project_id)

        logger.info(
            "Trailer complete: %s (%.1fs, %d scenes)",
            final_path, final_duration, len(valid_scenes),
        )

        return TrailerResult(
            output_path=final_path,
            duration_seconds=final_duration,
            scene_count=len(valid_scenes),
            resolution=resolution,
            has_audio=True,
            scenes=scene_results,
            metadata={
                "director_style": director_style,
                "total_scenes_attempted": len(scene_specs),
                "scenes_succeeded": len(valid_scenes),
                "scenes_failed": len(scene_specs) - len(valid_scenes),
            },
        )

    def cleanup(self):
        """Clean up all temporary files."""
        self.ffmpeg.cleanup()
        import shutil
        if self.work_dir and Path(self.work_dir).exists():
            shutil.rmtree(self.work_dir, ignore_errors=True)
            logger.info("Pipeline cleanup complete: %s", self.work_dir)

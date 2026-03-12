"""Video Generator Service — WALL-E's domain.

Uses Veo (via Vertex AI) to generate video clips from scene beats,
then assembles them into a cinematic trailer.

Max trailer length: ~3 minutes. Each clip: 5-8 seconds.
"""

import asyncio
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
import aiohttp
from google.cloud import aiplatform
from google import genai
from google.genai import types

from app.config.settings import settings
from app.models.schemas import SceneBeat, TrailerClip, TrailerProject
from app.services.gemini_client import get_client
from app.services.storage import upload_video


def _build_video_prompt(
    scene: SceneBeat,
    director_modifier: str = "",
    story_position: str = "",
    character_descriptions: Optional[dict] = None,
) -> str:
    """Build a Veo-optimized prompt for video generation with strict scene fidelity."""
    
    # Core scene content - stick strictly to what's provided
    parts = [
        f"Generate video clip based STRICTLY on this script scene: {scene.visual_description or scene.action}",
        f"Exact setting: {scene.location}, {scene.time_of_day}.",
        f"Required mood: {scene.mood}.",
    ]
    
    # Add character information if provided
    if hasattr(scene, 'characters') and scene.characters:
        parts.append(f"Characters present: {', '.join(scene.characters)}.")
        if character_descriptions:
            char_details = [f"{name}: {character_descriptions.get(name, 'no description')}" for name in scene.characters if name in character_descriptions]
            if char_details:
                parts.append(f"Character details: {'; '.join(char_details)}.")
    
    # Add fidelity requirements
    parts.append("SCENE FIDELITY: Show what is described in the scene plus contextually relevant enhancements.")
    parts.append("Do NOT add characters or major actions not mentioned in the script.")
    parts.append("DIALOGUE POLICY: Include scene-appropriate dialogue that enhances the story context.")
    parts.append("TEXT & SPELLING (CRITICAL): Any text shown on screen — signs, titles, subtitles, captions, dialogue — MUST be spelled perfectly in English. Double-check every word. No typos, no extra letters, no missing letters. Copy any dialogue EXACTLY as provided.")
    parts.append("Follow the exact location, time, mood, and character list provided.")
    
    # Add story position context for better narrative flow but within script bounds
    if story_position == "opening":
        parts.append("Establishing shot style, but only show what's described in the scene.")
    elif story_position == "middle":
        parts.append("Character development tone, but strictly follow the provided scene content.")
    elif story_position == "climax":
        parts.append("Peak tension style, but only show the actions explicitly described.")
    elif story_position == "resolution":
        parts.append("Resolution tone, but strictly adhere to the scene description.")
    
    parts.append("Professional cinematography within the scene constraints.")
    
    if director_modifier:
        parts.append(f"Director style: {director_modifier}")

    return " ".join(parts)


async def _generate_single_clip(
    scene: SceneBeat,
    project_id: str,
    prompt: str,
    clip_id: str,
) -> str:
    """Attempt a single Veo generation. Returns video_url or empty string."""
    import logging
    logger = logging.getLogger("storyforge.veo")

    client = get_client()
    operation = await client.aio.models.generate_videos(
        model=settings.veo_model,
        prompt=prompt,
        config=types.GenerateVideosConfig(
            number_of_videos=1,
            duration_seconds=8,
            aspect_ratio="16:9",
        ),
    )

    # Poll for completion
    poll_count = 0
    while not operation.done:
        await asyncio.sleep(10)
        poll_count += 1
        operation = await client.aio.operations.get(operation)
        if poll_count > 60:  # 10 min timeout
            logger.warning("Veo: Timeout polling for %s after %ds", scene.scene_id, poll_count * 10)
            return ""

    if operation.result and operation.result.generated_videos:
        video = operation.result.generated_videos[0]
        if hasattr(video, "video") and video.video:
            video_bytes = video.video.video_bytes
            if video_bytes:
                filename = f"{clip_id}.mp4"
                return await upload_video(
                    video_bytes=video_bytes,
                    project_id=project_id,
                    filename=filename,
                )

    logger.warning("Veo: No video returned for %s", scene.scene_id)
    return ""


async def generate_clip_with_position(
    scene: SceneBeat,
    project_id: str,
    director_style: Optional[dict] = None,
    story_position: str = "",
    character_descriptions: Optional[dict] = None,
    max_retries: int = 3,
) -> TrailerClip:
    """Generate a single video clip with retry logic and backoff."""
    import logging
    logger = logging.getLogger("storyforge.veo")

    director_modifier = ""
    if director_style:
        director_modifier = director_style.get("prompt_modifier", "")

    prompt = _build_video_prompt(scene, director_modifier, story_position, character_descriptions)
    clip_id = f"clip_{scene.scene_id}_{uuid.uuid4().hex[:6]}_{story_position[:6]}"

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            video_url = await _generate_single_clip(scene, project_id, prompt, clip_id)
            if video_url:
                if attempt > 1:
                    logger.info("Veo: %s succeeded on attempt %d", scene.scene_id, attempt)
                return TrailerClip(
                    clip_id=clip_id,
                    scene_id=scene.scene_id,
                    video_url=video_url,
                    duration=8.0,
                    status="ready",
                    prompt_used=prompt,
                )
            else:
                logger.warning("Veo: %s returned empty on attempt %d/%d", scene.scene_id, attempt, max_retries)
        except Exception as e:
            last_error = e
            logger.warning("Veo: %s failed attempt %d/%d: %s", scene.scene_id, attempt, max_retries, e)

        if attempt < max_retries:
            backoff = 15 * attempt  # 15s, 30s
            logger.info("Veo: Retrying %s in %ds...", scene.scene_id, backoff)
            await asyncio.sleep(backoff)

    logger.error("Veo: %s failed after %d attempts. Last error: %s", scene.scene_id, max_retries, last_error)
    return TrailerClip(
        clip_id=clip_id,
        scene_id=scene.scene_id,
        video_url="",
        duration=0.0,
        status="failed",
        prompt_used=prompt,
    )


async def generate_clip(
    scene: SceneBeat,
    project_id: str,
    director_style: Optional[dict] = None,
) -> TrailerClip:
    """Generate a single video clip for a scene using Veo (legacy function)."""
    return await generate_clip_with_position(scene, project_id, director_style, "")


async def _download_video(url: str, local_path: str) -> bool:
    """Download a video file from URL to local path."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    async with aiofiles.open(local_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                    return True
        return False
    except Exception as e:
        print(f"⚠️ Failed to download video {url}: {e}")
        return False


async def _assemble_trailer_ffmpeg(clips: list[TrailerClip], project_id: str) -> str:
    """Assemble video clips into final trailer using ffmpeg."""
    if not clips or not any(c.video_url for c in clips):
        return ""

    ready_clips = [c for c in clips if c.status == "ready" and c.video_url]
    if not ready_clips:
        return ""

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Resolve clips — use local files if available, download if remote
            from app.services.storage import LOCAL_ASSETS_DIR
            input_files = []
            for i, clip in enumerate(ready_clips):
                local_file = temp_path / f"clip_{i:02d}.mp4"
                # Check if video_url is a local asset path
                local_asset = LOCAL_ASSETS_DIR / clip.video_url.lstrip("/assets/")
                if local_asset.exists():
                    input_files.append(str(local_asset))
                elif clip.video_url.startswith("http"):
                    success = await _download_video(clip.video_url, str(local_file))
                    if success:
                        input_files.append(str(local_file))
                else:
                    # Try as absolute path
                    abs_path = Path(clip.video_url)
                    if abs_path.exists():
                        input_files.append(str(abs_path))
                    else:
                        print(f"⚠️ Cannot resolve clip: {clip.video_url}")

            if len(input_files) < len(ready_clips):
                print(f"⚠️ Only {len(input_files)}/{len(ready_clips)} clips downloaded")
            
            if not input_files:
                return ""

            # Create ffmpeg concat file
            concat_file = temp_path / "concat.txt"
            with open(concat_file, "w") as f:
                for file_path in input_files:
                    f.write(f"file '{file_path}'\n")

            # Output file
            output_file = temp_path / "trailer.mp4"

            # ffmpeg command to concatenate videos
            cmd = [
                "ffmpeg", "-y",  # Overwrite output
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",  # Copy streams without re-encoding
                "-movflags", "+faststart",  # Optimize for web playback
                str(output_file)
            ]

            # Run ffmpeg
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"⚠️ ffmpeg failed: {result.stderr}")
                return ""

            if not output_file.exists():
                print(f"⚠️ Output file not created: {output_file}")
                return ""

            # Upload assembled trailer
            with open(output_file, "rb") as f:
                video_bytes = f.read()
                
            trailer_filename = f"trailer_{project_id}_{uuid.uuid4().hex[:8]}.mp4"
            final_url = await upload_video(
                video_bytes=video_bytes,
                project_id=project_id,
                filename=trailer_filename,
            )

            return final_url

    except Exception as e:
        print(f"⚠️ Trailer assembly failed: {e}")
        return ""


async def generate_trailer(
    scenes: list[SceneBeat],
    project_id: str,
    director_style: Optional[dict] = None,
    max_duration: float = 180.0,
    scene_ids: Optional[list[str]] = None,
    progress_callback=None,
    character_descriptions: Optional[dict] = None,
) -> TrailerProject:
    """Generate a full trailer from scene beats.

    Args:
        scenes: All scene beats.
        project_id: Project ID.
        director_style: Director profile.
        max_duration: Maximum trailer length in seconds (default 3 min).
        scene_ids: Specific scenes to include (None = all).
        progress_callback: Async callback for progress updates.

    Returns:
        TrailerProject with all clips and metadata.
    """
    target_scenes = scenes
    if scene_ids:
        target_scenes = [s for s in scenes if s.scene_id in scene_ids]

    # Intelligent scene selection for better story coverage
    max_clips = int(max_duration / 8)
    if len(target_scenes) > max_clips:
        # Ensure we cover beginning, middle, and end effectively
        scene_count = len(target_scenes)
        selected_scenes = []
        
        if max_clips >= 3:
            # Always include opening scene
            selected_scenes.append((target_scenes[0], "opening"))
            
            # Include climactic/peak tension scenes from middle-to-end
            mid_start = scene_count // 3
            climax_start = int(scene_count * 0.7)  # Last 30% for climax
            
            # Fill remaining slots with key story beats
            remaining_clips = max_clips - 1  # -1 for opening
            if remaining_clips >= 2:
                # Add middle conflict scene
                mid_scene = target_scenes[mid_start + (climax_start - mid_start) // 2]
                selected_scenes.append((mid_scene, "middle"))
                remaining_clips -= 1
                
                # Add climax scene
                climax_scene = target_scenes[min(climax_start, scene_count - 1)]
                selected_scenes.append((climax_scene, "climax"))
                remaining_clips -= 1
                
                # Fill remaining with spread scenes
                if remaining_clips > 0:
                    step = scene_count / (remaining_clips + 3)  # +3 for already selected
                    for i in range(remaining_clips):
                        idx = int((i + 2) * step)  # +2 to skip opening
                        if idx < scene_count and idx not in [0, mid_start + (climax_start - mid_start) // 2, climax_start]:
                            position = "middle" if idx < climax_start else "resolution"
                            selected_scenes.append((target_scenes[idx], position))
            else:
                # Just add one key scene from the end
                end_scene = target_scenes[-1]
                selected_scenes.append((end_scene, "resolution"))
        else:
            # Fewer clips available, just spread evenly with positions
            step = len(target_scenes) / max_clips
            for i in range(max_clips):
                idx = int(i * step)
                if i == 0:
                    position = "opening"
                elif i == max_clips - 1:
                    position = "resolution"
                else:
                    position = "middle"
                selected_scenes.append((target_scenes[idx], position))
        
        target_scenes = selected_scenes
    else:
        # All scenes fit, assign positions
        all_scenes = list(target_scenes)
        target_scenes = []
        for i, scene in enumerate(all_scenes):
            if i == 0:
                position = "opening"
            elif i == len(all_scenes) - 1:
                position = "resolution"
            else:
                position = "middle"
            target_scenes.append((scene, position))

    # Load existing trailer to reuse completed clips (skip if scene unchanged)
    import hashlib
    from app.services import firestore

    def _scene_hash(scene: SceneBeat) -> str:
        """Hash scene content to detect modifications."""
        content = f"{scene.action}|{scene.visual_description}|{scene.location}|{scene.mood}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    existing_clips_by_scene: dict[str, TrailerClip] = {}
    existing_scene_hashes: dict[str, str] = {}
    try:
        raw = await firestore.get_project_raw(project_id)
        if raw and raw.get("trailer"):
            existing_trailer = TrailerProject(**raw["trailer"])
            for c in existing_trailer.clips:
                if c.status == "ready" and c.video_url:
                    existing_clips_by_scene[c.scene_id] = c
        # Load previous scene hashes if stored
        existing_scene_hashes = raw.get("_scene_hashes", {}) if raw else {}
    except Exception:
        pass  # No existing trailer, generate all

    # Compute current scene hashes
    current_scene_hashes: dict[str, str] = {}
    for scene, _ in target_scenes:
        current_scene_hashes[scene.scene_id] = _scene_hash(scene)

    clips: list[TrailerClip] = []
    total_duration = 0.0
    total_clips = len(target_scenes)

    for i, (scene, position) in enumerate(target_scenes):
        # Check if this scene already has a completed clip AND scene is unchanged
        existing = existing_clips_by_scene.get(scene.scene_id)
        scene_modified = (
            existing_scene_hashes.get(scene.scene_id) != current_scene_hashes.get(scene.scene_id)
        )
        if existing and not scene_modified:
            from app.services.storage import LOCAL_ASSETS_DIR
            # Verify the file still exists
            asset_path = LOCAL_ASSETS_DIR / existing.video_url.lstrip("/assets/")
            if asset_path.exists():
                clips.append(existing)
                total_duration += existing.duration
                completed = sum(1 for c in clips if c.status == "ready")
                if progress_callback:
                    await progress_callback({
                        "type": "progress",
                        "stage": "trailer",
                        "current": i + 1,
                        "total": total_clips,
                        "clips_done": completed,
                        "clips_total": total_clips,
                        "scene_id": scene.scene_id,
                        "message": f"Clip {i + 1}/{total_clips} — reusing existing ({completed}/{total_clips} clips done)",
                    })
                continue

        if progress_callback:
            completed = sum(1 for c in clips if c.status == "ready")
            await progress_callback({
                "type": "progress",
                "stage": "trailer",
                "current": i + 1,
                "total": total_clips,
                "clips_done": completed,
                "clips_total": total_clips,
                "scene_id": scene.scene_id,
                "message": f"Generating clip {i + 1}/{total_clips}: {scene.location} ({completed}/{total_clips} clips done)",
            })

        clip = await generate_clip_with_position(
            scene=scene,
            project_id=project_id,
            director_style=director_style,
            story_position=position,
            character_descriptions=character_descriptions,
        )
        clips.append(clip)
        total_duration += clip.duration

        # Save clip immediately to DB so progress is preserved
        completed = sum(1 for c in clips if c.status == "ready")
        partial_trailer = TrailerProject(
            clips=list(clips),
            total_duration=total_duration,
            final_video_url="",
            status="generating",
        )
        try:
            await firestore.save_trailer(project_id, partial_trailer)
        except Exception as e:
            print(f"⚠️ Failed to save partial trailer: {e}")

        if progress_callback:
            await progress_callback({
                "type": "progress",
                "stage": "trailer",
                "current": i + 1,
                "total": total_clips,
                "clips_done": completed,
                "clips_total": total_clips,
                "scene_id": scene.scene_id,
                "message": f"Clip {i + 1}/{total_clips} {'✅ done' if clip.status == 'ready' else '❌ failed'} ({completed}/{total_clips} clips done)",
            })

    # Assemble clips into final trailer
    final_video_url = ""
    if any(c.status == "ready" for c in clips):
        if progress_callback:
            completed = sum(1 for c in clips if c.status == "ready")
            await progress_callback({
                "type": "progress", 
                "stage": "assembly",
                "clips_done": completed,
                "clips_total": total_clips,
                "message": f"Assembling {completed} clips into final trailer...",
            })
        final_video_url = await _assemble_trailer_ffmpeg(clips, project_id)

    # Save scene hashes for future change detection
    try:
        await firestore.update_project(project_id, {"_scene_hashes": current_scene_hashes})
    except Exception:
        pass

    return TrailerProject(
        clips=clips,
        total_duration=total_duration,
        final_video_url=final_video_url,
        status="complete" if final_video_url or any(c.status == "ready" for c in clips) else "failed",
    )

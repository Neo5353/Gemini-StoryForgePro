"""Project CRUD endpoints — frontend-compatible response shapes.

R2-D2 handles the filing. C-3PO handles the pipeline.
These routes are the front door.
"""

import time
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request

from app.models.schemas import (
    ProjectCreate,
    ProjectResponse,
    OutputMode,
    ScriptFormat,
    ProjectStatus,
)
from app.config.settings import settings
from app.services import firestore
from app.agents.orchestrator import StoryForgeOrchestrator
from app.services.ws_manager import ConnectionManager

router = APIRouter()


def _get_manager() -> ConnectionManager:
    from app.main import manager
    return manager


async def _project_to_frontend(proj: ProjectResponse, raw_script: str = "") -> dict:
    """Transform backend ProjectResponse → frontend Project shape."""
    parsed = proj.parsed_script
    scenes = []
    if parsed and parsed.scenes:
        for s in parsed.scenes:
            scenes.append({
                "id": s.scene_id,
                "scene_number": s.scene_number,
                "title": f"Scene {s.scene_number}: {s.location}",
                "description": s.visual_description or s.action,
                "characters": s.characters,
                "location": s.location,
                "time_of_day": s.time_of_day,
                "mood": s.mood,
            })

    characters = []
    for c in (proj.characters or []):
        ref_url = c.views[0].image_url if c.views else None
        characters.append({
            "id": c.character_name.lower().replace(" ", "_"),
            "name": c.character_name,
            "description": c.description,
            "ref_sheet_url": ref_url,
            "expressions": [v.view_type for v in c.views],
            "thumbnail_url": ref_url,
        })

    pages = []
    for p in (proj.pages or []):
        if not p.panels:
            continue  # Skip empty pages (incomplete generation)
        panels = []
        for panel in p.panels:
            panels.append({
                "id": panel.panel_id,
                "scene_id": panel.scene_id,
                "image_url": panel.image_url,
                "position": {"row": (panel.panel_number - 1) // 2, "col": (panel.panel_number - 1) % 2},
                "span": {"rows": 1, "cols": 1},
                "bubbles": [],
                "caption": panel.caption or panel.dialogue_overlay,
            })
        pages.append({
            "id": f"page_{p.page_number}",
            "page_number": p.page_number,
            "layout": "2x3",
            "panels": panels,
        })

    # Get raw project data for storyboard_frames and video
    from app.services import firestore
    raw_data = await firestore.get_project_raw(proj.id)
    
    # Get storyboard_frames from raw data
    storyboard_frames = raw_data.get("storyboard_frames", [])
    
    # Get video from raw data or structured trailer
    video = None
    if raw_data.get("video"):
        video = raw_data["video"]
    elif proj.trailer:
        chapters = []
        clips_data = []
        offset = 0.0
        for clip in proj.trailer.clips:
            if clip.status == "ready" and clip.video_url:
                chapters.append({
                    "scene_id": clip.scene_id,
                    "title": clip.scene_id,
                    "start_time": offset,
                    "end_time": offset + clip.duration,
                    "thumbnail_url": None,
                })
                clips_data.append({
                    "clip_id": clip.clip_id,
                    "scene_id": clip.scene_id,
                    "video_url": clip.video_url,
                    "duration": clip.duration,
                    "status": clip.status,
                })
                offset += clip.duration
        video = {
            "video_url": proj.trailer.final_video_url or None,
            "duration": proj.trailer.total_duration,
            "chapters": chapters,
            "clips": clips_data,
        }

    return {
        "id": proj.id,
        "title": proj.title,
        "status": proj.status.value if hasattr(proj.status, 'value') else str(proj.status),
        "script": {
            "raw_text": raw_script,
            "format": proj.script_format.value if proj.script_format else "freeform",
            "scenes": scenes,
        },
        "director_style_id": proj.director_style,
        "output_mode": proj.output_mode.value if proj.output_mode else "comic",
        "characters": characters,
        "pages": pages,
        "storyboard_frames": storyboard_frames,
        "video": video,
        "created_at": proj.created_at or "",
        "updated_at": proj.updated_at or "",
    }


def _wrap(data, message="ok"):
    return {"data": data, "message": message, "success": True}


async def _run_pipeline(
    project_id: str,
    script: str,
    script_format: ScriptFormat,
    output_mode: OutputMode,
    director_style: str | None,
    director_styles: dict,
):
    """Background task: run the full StoryForge pipeline."""
    
    import logging
    logger = logging.getLogger(__name__)

    use_local = settings.storyforge_local
    if use_local:
        logger.info(f"📦 Local mode: skipping background pipeline for project {project_id}")
        return

    ws = _get_manager()

    async def progress_callback(data: dict):
        await ws.send_progress(project_id, data)

    orchestrator = StoryForgeOrchestrator(director_styles)
    try:
        await orchestrator.full_pipeline(
            project_id=project_id,
            script=script,
            script_format=script_format,
            output_mode=output_mode,
            director_id=director_style,
            progress_callback=progress_callback,
        )
    except Exception as e:
        await ws.send_progress(project_id, {
            "type": "error",
            "message": f"Pipeline failed: {str(e)}",
        })
        await firestore.update_project_status(project_id, "failed")


@router.post("/")
async def create_project(
    project: ProjectCreate,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """Create a new StoryForge project and kick off pipeline."""
    result = await firestore.create_project(project)

    background_tasks.add_task(
        _run_pipeline,
        project_id=result.id,
        script=project.script,
        script_format=project.script_format,
        output_mode=project.output_mode,
        director_style=project.director_style,
        director_styles=request.app.state.director_styles,
    )

    return _wrap(await _project_to_frontend(result))


@router.get("/{project_id}")
async def get_project(project_id: str):
    """Get project details."""
    project = await firestore.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get raw script text for frontend
    raw_project = await firestore.get_project_raw(project_id)
    script_text = raw_project.get("script", "") if raw_project else ""
    
    return _wrap(await _project_to_frontend(project, script_text))


@router.get("/")
async def list_projects(limit: int = 50):
    """List all projects, newest first."""
    projects = await firestore.list_projects(limit)
    frontend_projects = []
    for p in projects:
        frontend_projects.append(await _project_to_frontend(p))
    return _wrap(frontend_projects)


@router.patch("/{project_id}")
async def patch_project(project_id: str, request: Request):
    """Auto-save: update any project fields (title, script, style, mode, scenes)."""
    body = await request.json()
    project = await firestore.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update: dict = {}

    if "title" in body:
        update["title"] = body["title"]
    if "director_style" in body:
        update["director_style"] = body["director_style"]
    if "output_mode" in body:
        update["output_mode"] = body["output_mode"]
    if "script" in body:
        update["script"] = body["script"]
        # Clear old parsed script — forces re-analysis with new content
        update["parsed_script"] = None
        update["status"] = ProjectStatus.CREATED.value

    # Scene-level edits: patch individual scenes in parsed_script
    if "scenes" in body:
        raw = await firestore.get_project_raw(project_id)
        parsed = raw.get("parsed_script") or {}
        existing_scenes = parsed.get("scenes", [])

        # Build lookup by scene_id
        scene_map = {s.get("scene_id", s.get("id", "")): s for s in existing_scenes}
        for incoming in body["scenes"]:
            sid = incoming.get("id") or incoming.get("scene_id")
            if sid and sid in scene_map:
                # Map frontend field names to backend SceneBeat fields
                if "description" in incoming:
                    scene_map[sid]["visual_description"] = incoming["description"]
                if "title" in incoming:
                    scene_map[sid]["title"] = incoming["title"]
                if "mood" in incoming:
                    scene_map[sid]["mood"] = incoming["mood"]
                if "location" in incoming:
                    scene_map[sid]["location"] = incoming["location"]
                if "time_of_day" in incoming:
                    scene_map[sid]["time_of_day"] = incoming["time_of_day"]
                if "characters" in incoming:
                    scene_map[sid]["characters"] = incoming["characters"]

        parsed["scenes"] = list(scene_map.values())
        update["parsed_script"] = parsed

    if update:
        await firestore.update_project(project_id, update)

    project = await firestore.get_project(project_id)
    return _wrap(await _project_to_frontend(project), "Saved")


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """Delete a project and all its assets."""
    deleted = await firestore.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")

    # Clean up all stored assets (images, videos, characters)
    from app.services.storage import LOCAL_ASSETS_DIR
    import shutil
    project_dir = LOCAL_ASSETS_DIR / "projects" / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir)
        import logging
        logging.getLogger(__name__).info("Deleted assets for project %s", project_id)

    return _wrap({"deleted": True, "project_id": project_id})


@router.post("/{project_id}/analyze")
async def analyze_script(project_id: str, request: Request):
    """Analyze / parse the script for a project. Always re-parses the current script text."""
    project = await firestore.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Always re-parse — user may have edited the script
    raw_project = await firestore.get_project_raw(project_id)
    script_text = raw_project.get("script", "") if raw_project else ""
    if not script_text:
        raise HTTPException(status_code=400, detail="Project has no script text")

    
    use_local = settings.storyforge_local
    t0 = time.monotonic()

    if use_local:
        # Generate mock parsed script for local dev
        parsed = _mock_parse_script(script_text, project.title)
    else:
        from app.services.script_parser import parse_script
        parsed = await parse_script(script_text)

    await firestore.save_parsed_script(project_id, parsed)
    elapsed = round(time.monotonic() - t0, 1)
    print(f"⏱️  analyze_script [{project_id}]: {elapsed}s ({len(parsed.scenes)} scenes)")

    # Reload
    project = await firestore.get_project(project_id)
    return _wrap(await _project_to_frontend(project))


def _mock_parse_script(script_text: str, title: str):
    """Generate a reasonable mock parsed script for local development."""
    from app.models.schemas import ParsedScript, SceneBeat
    import re

    # Split into ~3-4 scenes based on sentences
    sentences = [s.strip() for s in re.split(r'[.!?]+', script_text) if s.strip()]
    num_scenes = min(max(len(sentences), 2), 5)

    # Extract character names (capitalize words that look like names)
    words = script_text.split()
    char_candidates = [w for w in words if w[0].isupper() and len(w) > 2 and w.isalpha()]
    characters = list(dict.fromkeys(char_candidates))[:5]  # dedupe, max 5
    if not characters:
        characters = ["Protagonist", "Antagonist"]

    locations = ["INT. APARTMENT - NIGHT", "EXT. CITY STREET - DAY", "INT. MUSEUM VAULT - NIGHT",
                 "EXT. ROOFTOP - DAWN", "INT. WAREHOUSE - NIGHT"]
    moods = ["tense", "mysterious", "action-packed", "suspenseful", "dramatic"]

    scenes = []
    for i in range(num_scenes):
        chunk = sentences[i] if i < len(sentences) else f"Scene {i+1} continues the story..."
        scenes.append(SceneBeat(
            scene_id=f"sc_{i+1:03d}",
            scene_number=i + 1,
            location=locations[i % len(locations)],
            time_of_day=["NIGHT", "DAY", "NIGHT", "DAWN", "NIGHT"][i % 5],
            characters=characters[:2] if i == 0 else [characters[i % len(characters)]],
            action=chunk,
            mood=moods[i % len(moods)],
            visual_description=f"A cinematic shot establishing the mood of scene {i+1}. {chunk}",
            estimated_duration=8.0 + (i * 2),
        ))

    return ParsedScript(
        scenes=scenes,
        characters=characters,
        locations=locations[:num_scenes],
        tone="dramatic thriller",
        genre="thriller",
        total_estimated_duration=sum(s.estimated_duration for s in scenes),
    )


@router.post("/{project_id}/generate/panels")
async def generate_panels_for_project(
    project_id: str,
    request: Request,
):
    """Generate panels for a project (synchronous — waits for Gemini).

    For the hackathon demo, we run generation inline so the frontend
    gets the actual pages back in the response. Takes ~30-90s for 6 panels.
    """
    import json
    import logging
    logger = logging.getLogger(__name__)

    project = await firestore.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    use_local = settings.storyforge_local
    t0 = time.monotonic()
    if use_local:
        mock_pages = _mock_generate_pages(project)
        await firestore.save_pages(project_id, mock_pages)
        elapsed = round(time.monotonic() - t0, 1)
        print(f"⏱️  generate_panels [{project_id}]: {elapsed}s (local mock)")
        project = await firestore.get_project(project_id)
        frontend_project = await _project_to_frontend(project)
        return _wrap(frontend_project["pages"], "Panels generated (local mock)")

    # Delete old images before regenerating (keep only latest set)
    from app.services.storage import delete_project_images
    mode_str = (project.output_mode.value if hasattr(project.output_mode, 'value')
                else project.output_mode) or "comic"
    await delete_project_images(project_id)
    # Clear existing pages in DB
    await firestore.save_pages(project_id, [])

    # Run generation synchronously
    raw = await firestore.get_project_raw(project_id)
    parsed = raw.get("parsed_script", {})
    scenes_data = parsed.get("scenes", [])
    if not scenes_data:
        raise HTTPException(status_code=400, detail="No parsed scenes")

    from app.models.schemas import SceneBeat
    scenes = [SceneBeat(**s) for s in scenes_data]

    orchestrator = StoryForgeOrchestrator(request.app.state.director_styles)
    ws = _get_manager()

    async def progress_cb(data):
        await ws.send_progress(project_id, data)

    try:
        char_descs = {}
        for char in raw.get("characters", []):
            char_descs[char.get("character_name", "")] = char.get("description", "")

        pages = await orchestrator.generate_panels(
            project_id=project_id,
            scenes=scenes,
            mode=mode_str,
            director_id=project.director_style,
            character_descriptions=char_descs,
            progress_callback=progress_cb,
            project_title=project.title,
        )

        await firestore.save_pages(project_id, pages)
        await firestore.update_project_status(project_id, ProjectStatus.COMPLETE)
        elapsed = round(time.monotonic() - t0, 1)
        total_panels = sum(len(p.panels) for p in pages)
        print(f"⏱️  generate_panels [{project_id}]: {elapsed}s ({total_panels} panels)")

        project = await firestore.get_project(project_id)
        fe = await _project_to_frontend(project)
        return _wrap(fe["pages"], f"Generated {total_panels} panels in {elapsed}s")

    except Exception as e:
        from app.services.interleaved_gen import GCPCongestionError
        # On failure: don't save anything, revert to parsed state
        await firestore.save_pages(project_id, [])
        await firestore.update_project_status(project_id, ProjectStatus.PARSED)

        if isinstance(e, GCPCongestionError):
            logger.warning("GCP congestion for project %s: %s", project_id, e)
            raise HTTPException(
                status_code=429,
                detail="GCP is congested right now. Please try again in about 5 minutes."
            )
        logger.error("Panel generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.post("/{project_id}/generate/storyboard")
async def generate_storyboard_for_project(
    project_id: str,
    request: Request,
):
    """Generate storyboard frames for a project (synchronous)."""
    import logging
    logger = logging.getLogger(__name__)

    project = await firestore.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete old images before regenerating
    from app.services.storage import delete_project_images
    await delete_project_images(project_id)
    await firestore.save_pages(project_id, [])

    # Use same generation pipeline as comics but with storyboard mode
    raw = await firestore.get_project_raw(project_id)
    parsed = raw.get("parsed_script", {})
    scenes_data = parsed.get("scenes", [])
    if not scenes_data:
        raise HTTPException(status_code=400, detail="No parsed scenes")

    from app.models.schemas import SceneBeat
    scenes = [SceneBeat(**s) for s in scenes_data]

    orchestrator = StoryForgeOrchestrator(request.app.state.director_styles)
    ws = _get_manager()
    t0 = time.monotonic()

    async def progress_cb(data):
        await ws.send_progress(project_id, data)

    try:
        char_descs = {}
        for char in raw.get("characters", []):
            char_descs[char.get("character_name", "")] = char.get("description", "")

        mode_str = project.output_mode.value if hasattr(project.output_mode, 'value') else (project.output_mode or "storyboard")
        pages = await orchestrator.generate_panels(
            project_id=project_id,
            scenes=scenes,
            mode=mode_str,
            director_id=project.director_style,
            character_descriptions=char_descs,
            progress_callback=progress_cb,
            project_title=project.title,
        )

        await firestore.save_pages(project_id, pages)
        await firestore.update_project_status(project_id, ProjectStatus.COMPLETE)
        elapsed = round(time.monotonic() - t0, 1)
        total_frames = sum(len(p.panels) for p in pages)
        print(f"⏱️  generate_storyboard [{project_id}]: {elapsed}s ({total_frames} frames)")

        project = await firestore.get_project(project_id)
        fe = await _project_to_frontend(project)
        return _wrap(fe.get("storyboard_frames", fe.get("pages", [])),
                     f"Generated {total_frames} frames in {elapsed}s")

    except Exception as e:
        from app.services.interleaved_gen import GCPCongestionError
        # On failure: don't save anything, revert to parsed state
        await firestore.save_pages(project_id, [])
        await firestore.update_project_status(project_id, ProjectStatus.PARSED)

        if isinstance(e, GCPCongestionError):
            logger.warning("GCP congestion for storyboard %s: %s", project_id, e)
            raise HTTPException(status_code=429, detail="GCP is congested right now. Please try again in about 5 minutes.")

        logger.error("Storyboard generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


async def _trailer_background_task(
    project_id: str,
    director_style: dict | None,
    char_descs: dict,
):
    """Background task: generate trailer, save to DB, clean up clips."""
    import logging
    import glob
    logger = logging.getLogger(__name__)
    t0 = time.monotonic()

    try:
        from app.services.video_generator import generate_trailer
        from app.services.storage import LOCAL_ASSETS_DIR
        from app.main import manager as ws

        from app.models.schemas import SceneBeat
        raw = await firestore.get_project_raw(project_id)
        parsed = raw.get("parsed_script", {})
        scenes_data = parsed.get("scenes", [])
        scenes = [SceneBeat(**s) for s in scenes_data]

        async def progress_cb(data):
            await ws.send_progress(project_id, data)

        trailer = await generate_trailer(
            scenes=scenes,
            project_id=project_id,
            director_style=director_style,
            character_descriptions=char_descs,
            progress_callback=progress_cb,
        )

        # Save in frontend-compatible format
        ready_clips = [c for c in trailer.clips if c.status == "ready" and c.video_url]
        video_data = {
            "video_url": trailer.final_video_url or None,
            "duration": trailer.total_duration,
            "chapters": [],
            "clips": [],
        }
        # Build chapters and clips from ready clips
        offset = 0.0
        for clip in trailer.clips:
            if clip.status == "ready" and clip.video_url:
                video_data["chapters"].append({
                    "scene_id": clip.scene_id,
                    "title": clip.scene_id,
                    "start_time": offset,
                    "end_time": offset + clip.duration,
                    "thumbnail_url": None,
                })
                video_data["clips"].append({
                    "clip_id": clip.clip_id,
                    "scene_id": clip.scene_id,
                    "video_url": clip.video_url,
                    "duration": clip.duration,
                    "status": clip.status,
                })
                offset += clip.duration

        await firestore.update_project(project_id, {
            "video": video_data,
            "trailer": trailer.model_dump(),
        })
        await firestore.update_project_status(project_id, ProjectStatus.COMPLETE)

        elapsed = round(time.monotonic() - t0, 1)
        print(f"⏱️  generate_trailer [{project_id}]: {elapsed}s ({len(trailer.clips)} clips)")

        # Clean up older clips and trailers — keep only latest versions
        clips_dir = LOCAL_ASSETS_DIR / "projects" / project_id / "videos"
        if clips_dir.exists():
            # Get current clip filenames from trailer
            current_clip_files = set()
            for clip in trailer.clips:
                if clip.video_url and clip.status == "ready":
                    fname = clip.video_url.split("/")[-1]
                    current_clip_files.add(fname)
            current_trailer_file = trailer.final_video_url.split("/")[-1] if trailer.final_video_url else ""

            removed = 0
            for f in clips_dir.iterdir():
                if not f.name.endswith(".mp4"):
                    continue
                # Keep current clips and current trailer
                if f.name in current_clip_files or f.name == current_trailer_file:
                    continue
                # Delete old clips and old trailers
                try:
                    f.unlink()
                    removed += 1
                except Exception:
                    pass
            if removed:
                print(f"🧹 Cleaned up {removed} old files for [{project_id}]")

    except Exception as e:
        logger.error("Trailer generation failed: %s", e, exc_info=True)
        await firestore.update_project_status(project_id, ProjectStatus.FAILED)
        await firestore.update_project(project_id, {
            "video": {"video_url": None, "duration": 0, "chapters": []},
        })


@router.post("/{project_id}/generate/trailer")
async def generate_trailer_for_project(
    project_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Generate trailer video using Veo 3.1 (async background task)."""
    project = await firestore.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    raw = await firestore.get_project_raw(project_id)
    parsed = raw.get("parsed_script", {})
    scenes_data = parsed.get("scenes", [])
    if not scenes_data:
        raise HTTPException(status_code=400, detail="No parsed scenes")

    # Get director style
    director_styles = request.app.state.director_styles
    director_style = None
    if isinstance(director_styles, list) and len(director_styles) > 0:
        if isinstance(director_styles[0], dict):
            for ds in director_styles:
                if ds.get("id") == project.director_style:
                    director_style = ds
                    break

    # Prepare character descriptions
    char_descs = {}
    for char in raw.get("characters", []):
        char_descs[char.get("character_name", "")] = char.get("description", "")

    # Mark as generating
    await firestore.update_project_status(project_id, ProjectStatus.GENERATING_TRAILER)
    await firestore.update_project(project_id, {
        "video": {"video_url": None, "duration": 0, "chapters": []},
    })

    # Launch background task — returns immediately to frontend
    import asyncio
    asyncio.create_task(_trailer_background_task(
        project_id=project_id,
        director_style=director_style,
        char_descs=char_descs,
    ))

    return _wrap(
        {"video_url": None, "duration": 0, "chapters": []},
        "Trailer generation started. Progress updates via WebSocket.",
    )


@router.post("/{project_id}/characters")
async def get_characters(project_id: str):
    """Get characters for a project."""
    project = await firestore.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    fe = await _project_to_frontend(project)
    return _wrap(fe["characters"])


@router.post("/{project_id}/characters/{character_id}/edit")
async def edit_character_endpoint(
    project_id: str,
    character_id: str,
    request: Request,
):
    """Edit a character via natural language instruction."""
    body = await request.json()
    instruction = body.get("instruction", "")
    # For now return the character unchanged with a note
    project = await firestore.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    fe = await _project_to_frontend(project)
    char = next((c for c in fe["characters"] if c["id"] == character_id), None)
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    return _wrap(char)


def _mock_generate_pages(project):
    """Generate mock panel pages for local dev."""
    from app.models.schemas import PanelPage, PanelMetadata
    pages = []
    scenes = project.parsed_script.scenes if project.parsed_script else []
    panel_num = 0
    for page_idx in range(max(1, len(scenes))):
        panels = []
        for p in range(6):  # 6 panels per page
            panel_num += 1
            scene = scenes[page_idx] if page_idx < len(scenes) else None
            panels.append(PanelMetadata(
                panel_id=f"panel_{panel_num}",
                scene_id=scene.scene_id if scene else f"sc_{page_idx+1:03d}",
                panel_number=panel_num,
                image_url="",
                dialogue_overlay="" if p % 3 != 0 else f"Panel {panel_num} dialogue",
                caption=scene.visual_description[:60] if scene and p == 0 else "",
                camera_angle=["Wide", "Close-up", "Medium", "OTS", "Low angle", "Bird's eye"][p % 6],
                mood=scene.mood if scene else "dramatic",
            ))
        pages.append(PanelPage(page_number=page_idx + 1, panels=panels))
    return pages


def _mock_generate_storyboard(project):
    """Generate mock storyboard frames for local dev."""
    from app.models.schemas import PanelPage, PanelMetadata
    # Reuse panel pages structure for storyboard
    return _mock_generate_pages(project)


@router.post("/{project_id}/edit")
async def edit_project(project_id: str, request: Request):
    """Conversational edit for scenes/panels."""
    body = await request.json()
    instruction = body.get("instruction", "")

    return _wrap({
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": f"Edit received: '{instruction}'. Processing...",
        "before_url": None,
        "after_url": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

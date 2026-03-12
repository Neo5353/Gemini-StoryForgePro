"""Generation endpoints — panels, storyboards, trailers, characters.

The creative assembly line. Every endpoint kicks off background
generation and streams progress via WebSocket.
"""

import asyncio

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from typing import Optional

from app.models.schemas import (
    GenerateRequest,
    ReshootRequest,
    OutputMode,
    ProjectStatus,
    SceneBeat,
)
from app.services import firestore
from app.agents.orchestrator import StoryForgeOrchestrator

router = APIRouter()


def _get_manager():
    from app.main import manager
    return manager


async def _generate_panels_task(
    project_id: str,
    mode: OutputMode,
    director_id: Optional[str],
    scene_ids: Optional[list[str]],
    director_styles: dict,
):
    """Background: generate panels for a project."""
    ws = _get_manager()
    project = await firestore.get_project_raw(project_id)
    if not project or not project.get("parsed_script"):
        await ws.send_progress(project_id, {
            "type": "error",
            "message": "Project has no parsed script. Create a project first.",
        })
        return

    parsed = project["parsed_script"]
    scenes = [SceneBeat(**s) for s in parsed.get("scenes", [])]

    orchestrator = StoryForgeOrchestrator(director_styles)

    async def progress_cb(data):
        await ws.send_progress(project_id, data)

    try:
        # Get character descriptions for context
        char_descs = {}
        for char in project.get("characters", []):
            char_descs[char.get("character_name", "")] = char.get("description", "")

        pages = await orchestrator.generate_panels(
            project_id=project_id,
            scenes=scenes,
            mode=mode.value if isinstance(mode, OutputMode) else mode,
            director_id=director_id,
            character_descriptions=char_descs,
            scene_ids=scene_ids,
            progress_callback=progress_cb,
            project_title=project.get("title", "Untitled Story"),
        )

        await ws.send_progress(project_id, {
            "type": "complete",
            "stage": "panels",
            "message": f"Generated {sum(len(p.panels) for p in pages)} panels across {len(pages)} pages",
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        await ws.send_progress(project_id, {
            "type": "error",
            "message": f"Panel generation failed: {str(e)}",
        })


async def _generate_trailer_task(
    project_id: str,
    director_id: Optional[str],
    scene_ids: Optional[list[str]],
    director_styles: dict,
):
    """Background: generate trailer for a project."""
    ws = _get_manager()
    project = await firestore.get_project_raw(project_id)
    if not project or not project.get("parsed_script"):
        await ws.send_progress(project_id, {
            "type": "error",
            "message": "Project has no parsed script.",
        })
        return

    parsed = project["parsed_script"]
    scenes = [SceneBeat(**s) for s in parsed.get("scenes", [])]

    orchestrator = StoryForgeOrchestrator(director_styles)

    async def progress_cb(data):
        await ws.send_progress(project_id, data)

    try:
        trailer = await orchestrator.generate_trailer_pipeline(
            project_id=project_id,
            scenes=scenes,
            director_id=director_id,
            scene_ids=scene_ids,
            progress_callback=progress_cb,
        )

        clips_count = len(trailer.clips) if hasattr(trailer, 'clips') else 0
        total_dur = trailer.total_duration if hasattr(trailer, 'total_duration') else 0
        await ws.send_progress(project_id, {
            "type": "complete",
            "stage": "trailer",
            "message": f"Generated {clips_count} clips, total {total_dur}s",
        })
    except Exception as e:
        await ws.send_progress(project_id, {
            "type": "error",
            "message": f"Trailer generation failed: {str(e)}",
        })


async def _generate_characters_task(
    project_id: str,
    director_styles: dict,
):
    """Background: generate character sheets."""
    ws = _get_manager()
    project = await firestore.get_project_raw(project_id)
    if not project or not project.get("parsed_script"):
        await ws.send_progress(project_id, {
            "type": "error",
            "message": "Project has no parsed script.",
        })
        return

    parsed = project["parsed_script"]
    characters = parsed.get("characters", [])
    director_id = project.get("director_style")

    orchestrator = StoryForgeOrchestrator(director_styles)

    async def progress_cb(data):
        await ws.send_progress(project_id, data)

    try:
        # Use detailed character data if available, else character names
        detailed = parsed.get("characters_detailed", [])
        char_input = detailed if detailed else [{"name": c} for c in characters]

        sheets = await orchestrator.generate_characters(
            project_id=project_id,
            characters=char_input,
            director_id=director_id,
            script_context=project.get("script", ""),
            progress_callback=progress_cb,
        )

        await ws.send_progress(project_id, {
            "type": "complete",
            "stage": "characters",
            "message": f"Generated sheets for {len(sheets)} characters",
        })
    except Exception as e:
        await ws.send_progress(project_id, {
            "type": "error",
            "message": f"Character generation failed: {str(e)}",
        })


@router.post("/panels")
async def generate_panels(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """Generate comic/manga panels for a project."""
    project = await firestore.get_project(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Use asyncio.create_task instead of BackgroundTasks to ensure
    # async sleep/retry works properly in the background
    asyncio.create_task(
        _generate_panels_task(
            project_id=req.project_id,
            mode=req.mode,
            director_id=req.director_style,
            scene_ids=req.scene_ids,
            director_styles=request.app.state.director_styles,
        )
    )

    return {
        "status": "queued",
        "project_id": req.project_id,
        "mode": req.mode.value,
        "message": "Panel generation started. Connect to WebSocket for progress.",
    }


@router.post("/storyboard")
async def generate_storyboard(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """Generate storyboard frames with annotations."""
    req.mode = OutputMode.STORYBOARD

    background_tasks.add_task(
        _generate_panels_task,
        project_id=req.project_id,
        mode=OutputMode.STORYBOARD,
        director_id=req.director_style,
        scene_ids=req.scene_ids,
        director_styles=request.app.state.director_styles,
    )

    return {
        "status": "queued",
        "project_id": req.project_id,
        "mode": "storyboard",
    }


@router.post("/trailer")
async def generate_trailer_endpoint(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """Generate cinematic trailer (up to 3 min)."""
    project = await firestore.get_project(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    background_tasks.add_task(
        _generate_trailer_task,
        project_id=req.project_id,
        director_id=req.director_style,
        scene_ids=req.scene_ids,
        director_styles=request.app.state.director_styles,
    )

    return {
        "status": "queued",
        "project_id": req.project_id,
        "mode": "trailer",
        "message": "Trailer generation started. This may take a while.",
    }


@router.post("/characters")
async def generate_characters(
    project_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """Generate character reference sheets."""
    project = await firestore.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    background_tasks.add_task(
        _generate_characters_task,
        project_id=project_id,
        director_styles=request.app.state.director_styles,
    )

    return {
        "status": "queued",
        "project_id": project_id,
        "message": "Character generation started.",
    }


@router.post("/reshoot")
async def reshoot_scene(
    req: ReshootRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """Reshoot a specific scene with new instructions.

    Re-generates panels for a single scene using the provided
    instruction to modify the prompt.
    """
    project = await firestore.get_project(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # For reshoot, we generate just the specified scene
    background_tasks.add_task(
        _generate_panels_task,
        project_id=req.project_id,
        mode=project.output_mode,
        director_id=project.director_style,
        scene_ids=[req.scene_id],
        director_styles=request.app.state.director_styles,
    )

    return {
        "status": "queued",
        "project_id": req.project_id,
        "scene_id": req.scene_id,
        "instruction": req.instruction,
        "message": "Reshoot queued.",
    }

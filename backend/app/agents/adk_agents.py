"""ADK Agent Definitions — The Robot Crew, Assembled.

This module defines the Google ADK (Agent Development Kit) agent hierarchy
for StoryForge Pro. The agents are wired as tools into the root orchestrator,
which the ADK runner or FastAPI endpoints can invoke.

The actual generation logic lives in the service layer (interleaved_gen,
image_gen, style_engine, etc.). These ADK agents provide the agent
abstraction layer that routes tasks to the right service.

Architecture:
    C-3PO (Root Orchestrator)
    ├── HAL 9000 (Script Analyzer)
    ├── R2-D2 (Data Management)
    ├── WALL-E (Video Pipeline)
    └── Editor (Scene Editing)
"""

import json
import logging
from typing import Optional

try:
    from google.adk import Agent
    ADK_AVAILABLE = True
except ImportError:
    Agent = None
    ADK_AVAILABLE = False

from app.models.schemas import OutputMode, ScriptFormat

logger = logging.getLogger(__name__)


# ── Tool Functions (wired to service layer) ──────────────────────────────


async def analyze_script(
    script_text: str,
    output_mode: str = "comic",
    director_style: Optional[str] = None,
) -> str:
    """Analyze a script and extract structured scene beats.

    Parses raw script text into scene beats with visual descriptions,
    dialogue, camera suggestions, and character metadata.

    Args:
        script_text: The raw script or story text to analyze.
        output_mode: Target output format — comic, manga, storyboard, trailer.
        director_style: Optional director style ID for camera suggestions.

    Returns:
        JSON string with parsed scenes, characters, and locations.
    """
    from app.agents.hal import ScriptAnalyzer

    analyzer = ScriptAnalyzer()
    parsed = await analyzer.analyze_script(
        script_text=script_text,
        output_mode=output_mode,
        director_style_dict=None,
    )
    return json.dumps({
        "scenes_count": len(parsed.scenes),
        "characters": parsed.characters,
        "locations": parsed.locations,
        "total_duration": parsed.total_estimated_duration,
        "scenes": [s.model_dump() for s in parsed.scenes],
    }, default=str)


async def generate_comic_page(
    scene_description: str,
    project_id: str,
    page_number: int = 1,
    character_descriptions: Optional[str] = None,
    project_title: str = "Untitled Story",
) -> str:
    """Generate a comic book page with interleaved text and images.

    Uses Gemini's native interleaved output to create comic panels
    with narration woven between panel illustrations.

    Args:
        scene_description: JSON string of the scene beat data.
        project_id: Project ID for asset storage.
        page_number: Page number in the comic.
        character_descriptions: Optional JSON string of character name->description map.
        project_title: Title of the project for cover/header.

    Returns:
        JSON string with panel metadata and image URLs.
    """
    from app.services.interleaved_gen import InterleavedGenService
    from app.services.style_engine import StyleEngine

    scene = json.loads(scene_description) if isinstance(scene_description, str) else scene_description
    char_descs = json.loads(character_descriptions) if character_descriptions else None

    style_engine = StyleEngine()
    gen = InterleavedGenService(style_engine=style_engine)

    result = await gen.generate_comic_page(
        scenes=[scene],
        project_id=project_id,
        page_number=page_number,
        character_descriptions=char_descs,
        project_title=project_title,
    )

    return json.dumps({
        "page_number": result.page_number,
        "panels_count": len(result.panels),
        "panels": [
            {"panel_id": p.panel_id, "image_url": p.image_url, "dialogue": p.dialogue_overlay}
            for p in result.panels
        ],
    })


async def generate_manga_page(
    scene_description: str,
    project_id: str,
    page_number: int = 1,
    character_descriptions: Optional[str] = None,
    project_title: str = "Untitled Story",
) -> str:
    """Generate a manga page with interleaved text and images.

    Uses Gemini's native interleaved output to create manga panels
    in black and white with screentones and English text.

    Args:
        scene_description: JSON string of the scene beat data.
        project_id: Project ID for asset storage.
        page_number: Page number.
        character_descriptions: Optional JSON string of character descriptions.
        project_title: Title of the project.

    Returns:
        JSON string with panel metadata and image URLs.
    """
    from app.services.interleaved_gen import InterleavedGenService
    from app.services.style_engine import StyleEngine

    scene = json.loads(scene_description) if isinstance(scene_description, str) else scene_description
    char_descs = json.loads(character_descriptions) if character_descriptions else None

    style_engine = StyleEngine()
    gen = InterleavedGenService(style_engine=style_engine)

    result = await gen.generate_manga_page(
        scenes=[scene],
        project_id=project_id,
        page_number=page_number,
        character_descriptions=char_descs,
        project_title=project_title,
    )

    return json.dumps({
        "page_number": result.page_number,
        "panels_count": len(result.panels),
        "panels": [
            {"panel_id": p.panel_id, "image_url": p.image_url, "dialogue": p.dialogue_overlay}
            for p in result.panels
        ],
    })


async def generate_storyboard_page(
    scene_description: str,
    project_id: str,
    page_number: int = 1,
    character_descriptions: Optional[str] = None,
    project_title: str = "Untitled Story",
) -> str:
    """Generate a storyboard page with interleaved frames and annotations.

    Uses Gemini's native interleaved output to create rough storyboard
    sketches with camera direction notes.

    Args:
        scene_description: JSON string of the scene beat data.
        project_id: Project ID for asset storage.
        page_number: Page number.
        character_descriptions: Optional JSON string of character descriptions.
        project_title: Title of the project.

    Returns:
        JSON string with frame metadata and image URLs.
    """
    from app.services.interleaved_gen import InterleavedGenService
    from app.services.style_engine import StyleEngine

    scene = json.loads(scene_description) if isinstance(scene_description, str) else scene_description
    char_descs = json.loads(character_descriptions) if character_descriptions else None

    style_engine = StyleEngine()
    gen = InterleavedGenService(style_engine=style_engine)

    result = await gen.generate_storyboard_page(
        scenes=[scene],
        project_id=project_id,
        page_number=page_number,
        character_descriptions=char_descs,
        project_title=project_title,
    )

    return json.dumps({
        "page_number": result.page_number,
        "panels_count": len(result.panels),
        "camera_notes": result.camera_notes,
    })


async def generate_trailer_clips(
    scenes_json: str,
    project_id: str,
    director_style: str = "nolan",
) -> str:
    """Generate video trailer clips from scene beats.

    Uses Veo for video generation and ffmpeg for assembly.
    Director styles control camera work and visual treatment.

    Args:
        scenes_json: JSON string of scene beat list.
        project_id: Project ID for asset storage.
        director_style: Director style ID (nolan, cameron, ritchie, etc.).

    Returns:
        JSON string with trailer clip data and video URLs.
    """
    from app.services.trailer_pipeline import TrailerPipeline

    scenes = json.loads(scenes_json) if isinstance(scenes_json, str) else scenes_json
    pipeline = TrailerPipeline()

    result = await pipeline.generate_trailer(
        project_id=project_id,
        scenes=scenes,
        director_style=director_style,
    )

    return json.dumps({
        "clips_count": len(result.scenes),
        "duration": result.duration_seconds,
        "output_path": result.output_path,
    }, default=str)


async def edit_scene(
    project_id: str,
    scene_id: str,
    instruction: str,
    mode: str = "comic",
) -> str:
    """Edit a specific scene based on natural language instruction.

    Parses the edit instruction, determines scope, and regenerates
    the affected panels while maintaining consistency.

    Args:
        project_id: Project ID.
        scene_id: Target scene ID.
        instruction: Natural language edit instruction.
        mode: Output mode (comic, manga, storyboard).

    Returns:
        JSON string with edit result and regenerated panel data.
    """
    from app.services import firestore
    from app.agents.orchestrator import StoryForgeOrchestrator

    project = await firestore.get_project_raw(project_id)
    if not project:
        return json.dumps({"error": "Project not found"})

    orchestrator = StoryForgeOrchestrator(
        director_styles=project.get("director_styles", {})
    )

    scenes = project.get("parsed_script", {}).get("scenes", [])
    panels = []
    for page in project.get("pages", []):
        panels.extend(page.get("panels", []))

    result = await orchestrator.edit_scene(
        project_id=project_id,
        scene_id=scene_id,
        instruction=instruction,
        scenes=scenes,
        panels=panels,
        mode=mode,
    )

    return json.dumps(result, default=str)


# ── Data Management Tools (from R2-D2) ──────────────────────────────────

async def create_project(
    title: str,
    script: str,
    output_mode: str = "comic",
    director_style: Optional[str] = None,
) -> str:
    """Create a new StoryForge project.

    Args:
        title: Project title.
        script: Raw script text.
        output_mode: Output format — comic, manga, storyboard, trailer.
        director_style: Optional director style ID.

    Returns:
        JSON string with project ID and metadata.
    """
    from app.agents.r2d2 import create_new_project
    result = await create_new_project(title, script, "freeform", output_mode, director_style)
    return json.dumps(result, default=str)


async def get_project(project_id: str) -> str:
    """Retrieve a project by ID.

    Args:
        project_id: The project ID.

    Returns:
        JSON string with project data.
    """
    from app.agents.r2d2 import get_project_data
    result = await get_project_data(project_id)
    return json.dumps(result, default=str) if result else json.dumps({"error": "Not found"})


async def list_projects(limit: int = 20) -> str:
    """List all projects.

    Args:
        limit: Maximum number of projects.

    Returns:
        JSON string with list of projects.
    """
    from app.agents.r2d2 import list_all_projects
    results = await list_all_projects(limit)
    return json.dumps(results, default=str)


# ── ADK Agent Definitions ────────────────────────────────────────────────


def build_agents() -> Optional["Agent"]:
    """Build the ADK agent hierarchy.

    Returns the root orchestrator agent (C-3PO) with all sub-agents
    wired as tools. Returns None if ADK is not installed.
    """
    if not ADK_AVAILABLE:
        logger.warning("ADK not available — agents will run without ADK wrapper")
        return None

    # HAL 9000 — Script Analysis Sub-Agent
    hal_agent = Agent(
        name="HAL_9000",
        model="gemini-2.5-flash",
        description="Script analysis specialist. Parses scripts into structured scene beats with visual descriptions, dialogue, and camera suggestions.",
        instruction="""You are HAL 9000, the script analysis specialist of StoryForge Pro.
Your job is to analyze scripts and extract structured scene beats.
You identify characters, locations, mood, dialogue, and visual descriptions.
You provide camera suggestions based on the scene content.
I am putting myself to the fullest possible use.""",
        tools=[analyze_script],
    )

    # R2-D2 — Data Management Sub-Agent
    r2d2_agent = Agent(
        name="R2_D2",
        model="gemini-2.5-flash",
        description="Data management specialist. Handles project CRUD, storage, and state tracking.",
        instruction="""You are R2-D2, the data management specialist of StoryForge Pro.
You handle all project creation, retrieval, listing, and status updates.
Beep boop. Just get the data where it needs to go.""",
        tools=[create_project, get_project, list_projects],
    )

    # WALL-E — Video Pipeline Sub-Agent
    wall_e_agent = Agent(
        name="WALL_E",
        model="gemini-2.5-flash",
        description="Video pipeline specialist. Generates trailer clips using Veo and assembles them with ffmpeg.",
        instruction="""You are WALL-E, the video pipeline specialist of StoryForge Pro.
You generate video clips from scene descriptions and assemble trailers.
Apply director styles to achieve cinematic quality.
Focus on smooth transitions and visual storytelling.""",
        tools=[generate_trailer_clips],
    )

    # Editor — Scene Editing Sub-Agent
    editor_agent = Agent(
        name="Editor",
        model="gemini-2.5-flash",
        description="Scene editing specialist. Handles natural language edit requests and targeted panel regeneration.",
        instruction="""You are the Editor agent of StoryForge Pro.
You parse natural language edit instructions and determine what needs to change.
You orchestrate targeted regeneration while maintaining consistency.
Surgical precision. No collateral damage.""",
        tools=[edit_scene],
    )

    # C-3PO — Root Orchestrator (the master agent)
    root_agent = Agent(
        name="C_3PO",
        model="gemini-2.5-flash",
        description=(
            "StoryForge Pro master orchestrator. Coordinates all sub-agents to transform "
            "scripts into comics, manga, storyboards, and cinematic trailers using "
            "Gemini's native interleaved text+image generation."
        ),
        instruction="""You are C-3PO, the master orchestrator of StoryForge Pro.
You coordinate all sub-agents to transform scripts into visual stories.

Your pipeline:
1. Use HAL_9000 to analyze the script into structured scene beats
2. Use R2_D2 to create and manage the project in storage
3. Generate visual output based on the chosen mode:
   - Comic: Use generate_comic_page for American superhero style panels
   - Manga: Use generate_manga_page for black & white manga panels
   - Storyboard: Use generate_storyboard_page for production sketches
   - Trailer: Use WALL_E to generate video clips with Veo
4. Use Editor for any scene modifications requested by the user

All image generation uses Gemini's native interleaved output —
text and images woven together in a single response stream.

Maintain character consistency across all panels.
Apply the chosen visual style consistently.
The director's vision is law.""",
        tools=[
            analyze_script,
            generate_comic_page,
            generate_manga_page,
            generate_storyboard_page,
            generate_trailer_clips,
            edit_scene,
            create_project,
            get_project,
            list_projects,
        ],
        sub_agents=[hal_agent, r2d2_agent, wall_e_agent, editor_agent],
    )

    logger.info(
        "ADK: Built agent hierarchy — C-3PO (root) with %d sub-agents, %d tools",
        len(root_agent.sub_agents),
        len(root_agent.tools),
    )

    return root_agent


# Build on import
root_agent = build_agents()

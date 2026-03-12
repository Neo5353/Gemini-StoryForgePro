"""WALL-E — Video Pipeline Agent.

The tireless little robot that builds trailers frame by frame.
Handles Veo video generation and ffmpeg assembly.

WALL-E doesn't talk much, but delivers results.
"""

from typing import Optional

try:
    from google.adk import Agent
except ImportError:
    Agent = None  # ADK not installed — agent wrapper unavailable

from app.models.schemas import SceneBeat, TrailerProject
from app.services.video_generator import generate_trailer, generate_clip


async def create_trailer(
    scenes: list[dict],
    project_id: str,
    director_style: Optional[dict] = None,
    max_duration: float = 180.0,
    scene_ids: Optional[list[str]] = None,
    progress_callback=None,
) -> dict:
    """Generate a cinematic trailer from scene beats.

    Args:
        scenes: List of scene beat dicts.
        project_id: Project ID.
        director_style: Director style profile.
        max_duration: Max trailer length in seconds.
        scene_ids: Specific scenes to include.
        progress_callback: Progress callback for WebSocket updates.

    Returns:
        Trailer project data with clips and URLs.
    """
    scene_beats = [SceneBeat(**s) for s in scenes]

    trailer = await generate_trailer(
        scenes=scene_beats,
        project_id=project_id,
        director_style=director_style,
        max_duration=max_duration,
        scene_ids=scene_ids,
        progress_callback=progress_callback,
    )

    return trailer.model_dump()


async def create_single_clip(
    scene: dict,
    project_id: str,
    director_style: Optional[dict] = None,
) -> dict:
    """Generate a single video clip for a scene.

    Args:
        scene: Scene beat dict.
        project_id: Project ID.
        director_style: Director style profile.

    Returns:
        Clip data with video URL.
    """
    scene_beat = SceneBeat(**scene)
    clip = await generate_clip(
        scene=scene_beat,
        project_id=project_id,
        director_style=director_style,
    )
    return clip.model_dump()


# ADK Agent definition (only available when google-adk is installed)
wall_e_agent = None
if Agent is not None:
    wall_e_agent = Agent(
        name="WALL-E",
        model="gemini-2.5-flash",
        description="Video pipeline agent. Generates video clips using Veo and assembles trailers.",
        instruction="""You are WALL-E, the video pipeline specialist of StoryForge Pro.
Your job is to generate video clips from scene descriptions and assemble them into trailers.
You use Veo for video generation.
Focus on cinematic quality and smooth transitions.
Apply director styles to video generation prompts.""",
        tools=[create_trailer, create_single_clip],
    )

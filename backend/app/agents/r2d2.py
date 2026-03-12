"""R2-D2 — Data Management Agent.

Beep boop. Handles all data operations — Firestore CRUD,
Cloud Storage management, project state tracking.

R2 doesn't need fancy words. Just gets the data where it needs to go.
"""

from typing import Optional

try:
    from google.adk import Agent
except ImportError:
    Agent = None  # ADK not installed — agent wrapper unavailable

from app.models.schemas import (
    ProjectCreate,
    ProjectStatus,
    ParsedScript,
    CharacterSheet,
    PanelPage,
    TrailerProject,
    ScriptFormat,
    OutputMode,
)
from app.services import firestore


async def create_new_project(
    title: str,
    script: str,
    script_format: str = "freeform",
    output_mode: str = "comic",
    director_style: Optional[str] = None,
) -> dict:
    """Create a new project in Firestore.

    Args:
        title: Project title.
        script: Raw script text.
        script_format: Format — screenplay, prose, freeform.
        output_mode: Output — comic, manga, storyboard, trailer.
        director_style: Director style ID.

    Returns:
        Created project data.
    """
    project = ProjectCreate(
        title=title,
        script=script,
        script_format=ScriptFormat(script_format),
        output_mode=OutputMode(output_mode),
        director_style=director_style,
    )
    result = await firestore.create_project(project)
    return result.model_dump()


async def get_project_data(project_id: str) -> Optional[dict]:
    """Retrieve project data by ID.

    Args:
        project_id: The project ID.

    Returns:
        Project data dict, or None if not found.
    """
    result = await firestore.get_project(project_id)
    if result:
        return result.model_dump()
    return None


async def list_all_projects(limit: int = 50) -> list[dict]:
    """List all projects.

    Args:
        limit: Max number of projects to return.

    Returns:
        List of project data dicts.
    """
    results = await firestore.list_projects(limit)
    return [r.model_dump() for r in results]


async def update_status(project_id: str, status: str) -> dict:
    """Update a project's status.

    Args:
        project_id: Project ID.
        status: New status value.

    Returns:
        Confirmation dict.
    """
    await firestore.update_project_status(project_id, ProjectStatus(status))
    return {"project_id": project_id, "status": status, "updated": True}


async def store_parsed_script(project_id: str, parsed_data: dict) -> dict:
    """Save parsed script data to a project.

    Args:
        project_id: Project ID.
        parsed_data: Parsed script dict.

    Returns:
        Confirmation.
    """
    parsed = ParsedScript(**parsed_data)
    await firestore.save_parsed_script(project_id, parsed)
    return {"project_id": project_id, "scenes_count": len(parsed.scenes)}


async def store_characters(project_id: str, characters_data: list[dict]) -> dict:
    """Save character sheets to a project.

    Args:
        project_id: Project ID.
        characters_data: List of character sheet dicts.

    Returns:
        Confirmation.
    """
    characters = [CharacterSheet(**c) for c in characters_data]
    await firestore.save_characters(project_id, characters)
    return {"project_id": project_id, "characters_count": len(characters)}


async def store_pages(project_id: str, pages_data: list[dict]) -> dict:
    """Save panel pages to a project.

    Args:
        project_id: Project ID.
        pages_data: List of panel page dicts.

    Returns:
        Confirmation.
    """
    pages = [PanelPage(**p) for p in pages_data]
    await firestore.save_pages(project_id, pages)
    return {"project_id": project_id, "pages_count": len(pages)}


async def store_trailer(project_id: str, trailer_data: dict) -> dict:
    """Save trailer data to a project.

    Args:
        project_id: Project ID.
        trailer_data: Trailer project dict.

    Returns:
        Confirmation.
    """
    trailer = TrailerProject(**trailer_data)
    await firestore.save_trailer(project_id, trailer)
    return {"project_id": project_id, "clips_count": len(trailer.clips)}


async def remove_project(project_id: str) -> dict:
    """Delete a project.

    Args:
        project_id: Project ID.

    Returns:
        Success/failure dict.
    """
    existed = await firestore.delete_project(project_id)
    return {"project_id": project_id, "deleted": existed}


# ADK Agent definition (only available when google-adk is installed)
r2d2_agent = None
if Agent is not None:
    r2d2_agent = Agent(
        name="R2-D2",
        model="gemini-2.5-flash",
        description="Data management agent. Handles Firestore CRUD and Cloud Storage operations.",
        instruction="""You are R2-D2, the data management specialist of StoryForge Pro.
Your job is to store, retrieve, and manage project data in Firestore.
You handle all CRUD operations and ensure data integrity.
Beep boop. Just get the data where it needs to go.""",
        tools=[
            create_new_project,
            get_project_data,
            list_all_projects,
            update_status,
            store_parsed_script,
            store_characters,
            store_pages,
            store_trailer,
            remove_project,
        ],
    )

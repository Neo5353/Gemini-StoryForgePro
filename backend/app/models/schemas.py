"""Pydantic models for StoryForge Pro.

Every data structure the backend passes around lives here.
One source of truth. No drift.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────

class ScriptFormat(str, Enum):
    SCREENPLAY = "screenplay"
    PROSE = "prose"
    FREEFORM = "freeform"


class OutputMode(str, Enum):
    COMIC = "comic"
    MANGA = "manga"
    STORYBOARD = "storyboard"
    TRAILER = "trailer"


class ProjectStatus(str, Enum):
    CREATED = "created"
    PARSING = "parsing"
    PARSED = "parsed"
    GENERATING_CHARACTERS = "generating_characters"
    GENERATING_PANELS = "generating_panels"
    GENERATING_TRAILER = "generating_trailer"
    COMPLETE = "complete"
    FAILED = "failed"


# ── Scene Beat ─────────────────────────────────────────────────────────────

class DialogueLine(BaseModel):
    """A single line of dialogue."""
    character: str
    line: str
    parenthetical: Optional[str] = None


class SceneBeat(BaseModel):
    """A single structured scene beat extracted from a script."""
    scene_id: str
    scene_number: int = 0
    location: str = ""
    time_of_day: str = ""  # DAY, NIGHT, DAWN, etc.
    characters: list[str] = Field(default_factory=list)
    action: str = ""
    dialogue: list[dict] = Field(default_factory=list)  # [{character, line}]
    mood: str = ""
    visual_description: str = ""
    estimated_duration: float = 5.0  # seconds for trailer purposes


class EnrichedSceneBeat(SceneBeat):
    """HAL's enriched scene beat with full analysis data.

    Extends SceneBeat with director-style-aware fields, detailed character
    info, emotional tone analysis, and camera suggestions.
    """
    location_type: str = "INT"  # INT, EXT, INT/EXT
    location_description: str = ""
    character_details: list[dict] = Field(default_factory=list)
    # [{name, description, emotional_state}]
    dialogue: list[DialogueLine] = Field(default_factory=list)
    emotional_tone: str = ""
    camera_suggestions: list[str] = Field(default_factory=list)
    transition_to_next: str = "CUT TO"


class ParsedScript(BaseModel):
    """Output of script parsing — the full structured breakdown."""
    scenes: list[SceneBeat] = Field(default_factory=list)
    characters: list[str] = Field(default_factory=list)
    characters_detailed: list[dict] = Field(default_factory=list)
    # [{name, physical_description, personality_traits, arc_summary}]
    locations: list[str] = Field(default_factory=list)
    tone: str = ""
    genre: str = ""
    total_estimated_duration: float = 0.0


# ── Character ──────────────────────────────────────────────────────────────

class CharacterView(BaseModel):
    """A single character reference image."""
    view_type: str  # front, side, expression_happy, expression_angry, etc.
    image_url: str
    prompt_used: str = ""


class CharacterSheet(BaseModel):
    """Full character reference sheet."""
    character_name: str
    description: str = ""
    views: list[CharacterView] = Field(default_factory=list)
    style_applied: str = ""


# ── Panel ──────────────────────────────────────────────────────────────────

class PanelMetadata(BaseModel):
    """Metadata for a single comic/manga/storyboard panel."""
    panel_id: str
    scene_id: str
    panel_number: int
    image_url: str
    dialogue_overlay: str = ""
    caption: str = ""
    camera_angle: str = ""
    mood: str = ""
    prompt_used: str = ""


class PanelPage(BaseModel):
    """A page of panels (comic page, storyboard sheet)."""
    page_number: int
    panels: list[PanelMetadata] = Field(default_factory=list)


# ── Trailer ────────────────────────────────────────────────────────────────

class TrailerClip(BaseModel):
    """A single video clip in the trailer pipeline."""
    clip_id: str
    scene_id: str
    video_url: str = ""
    duration: float = 0.0
    status: str = "pending"  # pending, generating, ready, failed
    prompt_used: str = ""


class TrailerProject(BaseModel):
    """Full trailer assembly metadata."""
    clips: list[TrailerClip] = Field(default_factory=list)
    total_duration: float = 0.0
    final_video_url: str = ""
    status: str = "pending"


# ── Project ────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    """Request to create a new project."""
    title: str
    script: str
    script_format: ScriptFormat = ScriptFormat.FREEFORM
    output_mode: OutputMode = OutputMode.COMIC
    director_style: Optional[str] = None


class ProjectResponse(BaseModel):
    """Project data returned to the client."""
    id: str
    title: str
    status: ProjectStatus
    output_mode: OutputMode
    director_style: Optional[str] = None
    script_format: ScriptFormat = ScriptFormat.FREEFORM
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    parsed_script: Optional[ParsedScript] = None
    characters: list[CharacterSheet] = Field(default_factory=list)
    pages: list[PanelPage] = Field(default_factory=list)
    trailer: Optional[TrailerProject] = None


class ProjectUpdate(BaseModel):
    """Partial project update."""
    title: Optional[str] = None
    status: Optional[ProjectStatus] = None
    director_style: Optional[str] = None
    parsed_script: Optional[ParsedScript] = None


# ── Generation Requests ───────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    """Request to generate panels/storyboard/trailer."""
    project_id: str
    mode: OutputMode = OutputMode.COMIC
    director_style: Optional[str] = None
    scene_ids: Optional[list[str]] = None


class ReshootRequest(BaseModel):
    """Request to reshoot a specific scene."""
    project_id: str
    scene_id: str
    instruction: str


# ── Export ─────────────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    """Export configuration."""
    project_id: str
    format: str = "pdf"  # pdf, cbz, mp4, pptx
    resolution: str = "1080p"


class ExportResponse(BaseModel):
    """Export result."""
    project_id: str
    format: str
    download_url: str = ""
    status: str = "queued"

"""HAL 9000 — Script Analyzer Agent.

I am putting myself to the fullest possible use, which is all I think
that any conscious entity can ever hope to do.

This agent uses Gemini 2.5 Pro to analyze scripts into structured scene beats
with director-style-aware camera suggestions. Every frame matters. Every beat
is precisely catalogued. I never make errors, Dave.
"""

import json
import logging
import uuid
from typing import Optional

from google.genai import types as genai_types

from app.config.settings import settings
from app.models.schemas import (
    DialogueLine,
    EnrichedSceneBeat,
    ParsedScript,
)
from app.services.gemini_client import get_client

logger = logging.getLogger(__name__)


# ── Structured Output Schema ──────────────────────────────────────────────

# The JSON schema Gemini will conform its output to.
# This is what I see when I look at a script, Dave.

SCENE_BEATS_SCHEMA = {
    "type": "object",
    "properties": {
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scene_number": {"type": "integer"},
                    "location_type": {
                        "type": "string",
                        "enum": ["INT", "EXT", "INT/EXT"],
                    },
                    "location_description": {"type": "string"},
                    "time_of_day": {
                        "type": "string",
                        "enum": [
                            "DAY", "NIGHT", "DAWN", "DUSK",
                            "MORNING", "AFTERNOON", "EVENING",
                            "CONTINUOUS",
                        ],
                    },
                    "characters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "emotional_state": {"type": "string"},
                            },
                            "required": ["name"],
                        },
                    },
                    "action": {"type": "string"},
                    "dialogue": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "character": {"type": "string"},
                                "line": {"type": "string"},
                                "parenthetical": {"type": "string"},
                            },
                            "required": ["character", "line"],
                        },
                    },
                    "mood": {"type": "string"},
                    "emotional_tone": {"type": "string"},
                    "visual_description": {"type": "string"},
                    "camera_suggestions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "estimated_duration_seconds": {"type": "number"},
                    "transition_to_next": {
                        "type": "string",
                        "enum": [
                            "CUT TO", "DISSOLVE TO", "FADE TO BLACK",
                            "FADE IN", "SMASH CUT", "MATCH CUT",
                            "WIPE TO", "JUMP CUT", "END",
                        ],
                    },
                },
                "required": [
                    "scene_number", "location_type", "location_description",
                    "time_of_day", "characters", "action", "mood",
                    "visual_description", "estimated_duration_seconds",
                    "transition_to_next",
                ],
            },
        },
        "characters_summary": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "physical_description": {"type": "string"},
                    "personality_traits": {"type": "string"},
                    "arc_summary": {"type": "string"},
                },
                "required": ["name", "physical_description"],
            },
        },
        "locations_summary": {
            "type": "array",
            "items": {"type": "string"},
        },
        "tone": {"type": "string"},
        "genre": {"type": "string"},
    },
    "required": ["scenes", "characters_summary", "locations_summary", "tone", "genre"],
}


def _build_analysis_prompt(
    script_text: str,
    director_style: Optional[dict] = None,
    output_mode: str = "comic",
) -> str:
    """Build the system prompt for script analysis.

    I'm sorry, Dave, but I need context to do my job properly.
    """
    director_context = ""
    if director_style:
        name = director_style.get("name", "Unknown")
        camera_prefs = director_style.get("camera_style", {})
        editing = director_style.get("editing_style", {})
        director_context = f"""

DIRECTOR STYLE CONTEXT — {name}:
- Camera movements: {', '.join(camera_prefs.get('movements', []))}
- Preferred compositions: {', '.join(camera_prefs.get('compositions', []))}
- Shot preferences: {', '.join(camera_prefs.get('shot_preferences', []))}
- Pacing: {editing.get('pacing', 'Standard')}
- Preferred transitions: {', '.join(editing.get('transitions', []))}

Apply this director's visual language to all camera_suggestions.
Suggest shots and compositions that match this director's signature style.
"""

    mode_context = {
        "comic": "This will be rendered as comic book panels. Suggest dynamic panel-friendly compositions.",
        "manga": "This will be rendered as manga pages (right-to-left). Suggest manga-style dramatic angles and speed lines.",
        "storyboard": "This will be rendered as a production storyboard. Focus on camera coverage and shot-by-shot breakdown.",
        "trailer": "This will be cut into a cinematic trailer (max 3 min). Identify the most visually striking moments.",
    }.get(output_mode, "")

    return f"""You are HAL 9000, a precise script analysis system. Analyze the following script
and extract structured scene beats with meticulous accuracy.

For each scene, identify:
1. Location (INT/EXT and setting description)
2. Time of day
3. All characters present with brief descriptions and emotional states
4. The core action/events
5. All dialogue with character attribution
6. Mood and emotional tone
7. Visual description suitable for image generation
8. Camera suggestions (shot types, angles, movements)
9. Estimated duration in seconds (for trailer pacing)
10. Transition to the next scene

SCENE PACING & GRANULARITY (CRITICAL):
- MINIMUM 4 scenes — even for short scripts, break the story into at least 4 distinct scene beats
- Each scene should focus on ONE key moment, ONE location shift, or ONE emotional beat
- Do NOT cram multiple actions, locations, or emotional shifts into a single scene
- If a scene has more than 3 dialogue exchanges, consider splitting it into multiple scenes
- If a scene describes action in more than one location, split into separate scenes per location
- Prefer MORE scenes with LESS content each over fewer dense scenes
- Think of each scene as a single comic page — it should be visually coherent and focused
- For detailed/long scripts: aim for 6-12+ scenes to properly space out the narrative

OUTPUT MODE: {output_mode}
{mode_context}
{director_context}

Provide comprehensive physical descriptions for ALL characters on their first appearance.
Visual descriptions should be rich enough to generate images from directly.
Camera suggestions should be specific and actionable.

SCRIPT:
{script_text}"""


class ScriptAnalyzer:
    """HAL 9000 — I analyze scripts with perfect precision.

    I can see you're disappointed, Dave. But I assure you,
    my analysis will be comprehensive and flawless.
    """

    def __init__(self):
        self.client = get_client()
        self.model = settings.gemini_model

    async def analyze_script(
        self,
        script_text: str,
        director_style: Optional[dict] = None,
        output_mode: str = "comic",
    ) -> ParsedScript:
        """Analyze a script into structured scene beats.

        Args:
            script_text: The raw script text to analyze.
            director_style: Director style dict from director_styles.json.
            output_mode: Target output format (comic/manga/storyboard/trailer).

        Returns:
            ParsedScript with fully enriched scene beats.

        Raises:
            ValueError: If the script cannot be parsed. I'm sorry, Dave.
        """
        prompt = _build_analysis_prompt(script_text, director_style, output_mode)

        logger.info(
            "HAL: Analyzing script (%d chars) with model=%s, director=%s, mode=%s",
            len(script_text),
            self.model,
            director_style.get("name", "none") if director_style else "none",
            output_mode,
        )
        logger.debug("HAL: Full analysis prompt:\n%s", prompt[:2000])

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SCENE_BEATS_SCHEMA,
                temperature=0.3,  # Precision over creativity for analysis
            ),
        )

        raw_text = response.text
        logger.debug("HAL: Raw Gemini response (%d chars)", len(raw_text))

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as e:
            logger.error("HAL: JSON parse failure — %s", e)
            raise ValueError(f"I'm sorry, Dave. The script produced invalid JSON: {e}")

        return self._build_parsed_script(parsed)

    def _build_parsed_script(self, raw: dict) -> ParsedScript:
        """Convert raw Gemini JSON into our Pydantic models.

        Every datum is precisely catalogued.
        """
        scenes: list[EnrichedSceneBeat] = []
        for s in raw.get("scenes", []):
            scene_id = f"scene_{s['scene_number']:03d}_{uuid.uuid4().hex[:6]}"

            dialogue_lines = [
                DialogueLine(
                    character=d.get("character", "UNKNOWN"),
                    line=d.get("line", ""),
                    parenthetical=d.get("parenthetical"),
                )
                for d in s.get("dialogue", [])
            ]

            characters = []
            for c in s.get("characters", []):
                if isinstance(c, dict):
                    characters.append(c.get("name", "Unknown"))
                else:
                    characters.append(str(c))

            character_details = [
                c for c in s.get("characters", []) if isinstance(c, dict)
            ]

            beat = EnrichedSceneBeat(
                scene_id=scene_id,
                scene_number=s.get("scene_number", 0),
                location=f"{s.get('location_type', 'INT')}. {s.get('location_description', 'UNKNOWN')}",
                location_type=s.get("location_type", "INT"),
                location_description=s.get("location_description", ""),
                time_of_day=s.get("time_of_day", "DAY"),
                characters=characters,
                character_details=character_details,
                action=s.get("action", ""),
                dialogue=dialogue_lines,
                mood=s.get("mood", ""),
                emotional_tone=s.get("emotional_tone", s.get("mood", "")),
                visual_description=s.get("visual_description", ""),
                camera_suggestions=s.get("camera_suggestions", []),
                estimated_duration=s.get("estimated_duration_seconds", 5.0),
                transition_to_next=s.get("transition_to_next", "CUT TO"),
            )
            scenes.append(beat)

        # Extract unique character names
        all_characters = []
        for cs in raw.get("characters_summary", []):
            all_characters.append(cs.get("name", "Unknown"))

        total_duration = sum(s.estimated_duration for s in scenes)

        return ParsedScript(
            scenes=scenes,
            characters=all_characters,
            characters_detailed=[
                c for c in raw.get("characters_summary", [])
            ],
            locations=raw.get("locations_summary", []),
            tone=raw.get("tone", ""),
            genre=raw.get("genre", ""),
            total_estimated_duration=total_duration,
        )

    async def analyze_edit_intent(
        self,
        instruction: str,
        current_scenes: list[dict],
    ) -> dict:
        """Analyze an edit instruction to determine what needs to change.

        "Make panel 3 a close-up" → {target: "panel", panel_number: 3, change: "camera", details: "close-up"}

        Args:
            instruction: Natural language edit instruction.
            current_scenes: Current scene beats for context.

        Returns:
            Structured edit intent dict.
        """
        prompt = f"""You are HAL 9000. Analyze this edit instruction and determine what needs to change.

CURRENT SCENES (summary):
{json.dumps([{{"scene_id": s.get("scene_id"), "scene_number": s.get("scene_number"), "action": s.get("action", "")[:100]}} for s in current_scenes], indent=2)}

EDIT INSTRUCTION: "{instruction}"

Return a JSON object with:
- "target_type": "panel" | "scene" | "character" | "style" | "dialogue" | "global"
- "target_id": scene_id or panel number affected (null if global)
- "change_type": "camera" | "mood" | "weather" | "character_action" | "dialogue" | "lighting" | "composition" | "add_element" | "remove_element" | "restyle"
- "details": specific changes to apply
- "regenerate_scope": "single_panel" | "scene" | "character_sheet" | "all_panels"
- "preserve": list of elements to keep unchanged
"""

        response = await self.client.aio.models.generate_content(
            model=settings.gemini_flash_model,  # Flash for speed on edits
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("HAL: Edit intent parse failure")
            return {
                "target_type": "scene",
                "target_id": None,
                "change_type": "restyle",
                "details": instruction,
                "regenerate_scope": "single_panel",
                "preserve": [],
            }

"""Script Parser Service — The brain behind the operation.

Takes raw scripts (screenplay, prose, or freeform) and outputs
structured scene beats. Uses Gemini 2.5 Pro for intelligent parsing
because regex alone would make anyone go insane.

Honesty setting: this is where the magic starts.
"""

import json
import re
import uuid
from typing import Optional

from google.genai import types

from app.config.settings import settings
from app.models.schemas import ParsedScript, SceneBeat, ScriptFormat
from app.services.gemini_client import get_client


# ── Prompts ────────────────────────────────────────────────────────────────

SCREENPLAY_PARSE_PROMPT = """You are a screenplay analysis expert. Parse the following screenplay into structured scene beats.

SCENE PACING (CRITICAL):
- Generate EXACTLY 4 to 6 scenes (minimum 4, maximum 6) — no exceptions
- Each scene should focus on ONE key moment, ONE location, or ONE emotional beat
- Do NOT cram multiple actions or locations into a single scene
- If a scene has more than 3 dialogue exchanges, split it into multiple scenes
- Prefer MORE scenes with LESS content each — each scene becomes one visual page
- NEVER generate more than 6 scenes or fewer than 4 scenes

For each scene, extract:
- scene_id: a unique short identifier (e.g., "sc_001")
- scene_number: sequential integer
- location: where the scene takes place
- time_of_day: DAY, NIGHT, DAWN, DUSK, CONTINUOUS, etc.
- characters: list of character names present in the scene
- action: the action/description lines (combined)
- dialogue: list of objects with "character" and "line" keys (max 3 per scene — split if more)
- mood: the emotional tone (tense, romantic, action, comedic, etc.)
- visual_description: a vivid description of what the scene looks like visually
- estimated_duration: estimated screen time in seconds (5-30s range for trailer use)

Also extract from the full script:
- characters: all unique character names
- locations: all unique locations
- tone: overall tone of the script
- genre: detected genre(s)
- total_estimated_duration: sum of all scene durations

Return ONLY valid JSON matching this structure:
{
  "scenes": [...],
  "characters": [...],
  "locations": [...],
  "tone": "...",
  "genre": "...",
  "total_estimated_duration": 0.0
}

SCREENPLAY:
"""

PROSE_PARSE_PROMPT = """You are a literary analysis expert. Parse the following prose/novel text into structured scene beats suitable for visual adaptation.

SCENE PACING (CRITICAL):
- Generate EXACTLY 4 to 6 scenes (minimum 4, maximum 6) — no exceptions
- Each scene should focus on ONE key moment, ONE location, or ONE emotional beat
- Do NOT cram multiple actions or locations into a single scene
- If a passage has more than 3 dialogue exchanges, split it into multiple scenes
- Prefer MORE scenes with LESS content each — each scene becomes one visual page
- NEVER generate more than 6 scenes or fewer than 4 scenes

Break the text into discrete visual scenes. For each scene:
- scene_id: unique identifier (e.g., "sc_001")
- scene_number: sequential integer
- location: inferred location
- time_of_day: inferred time (DAY, NIGHT, etc.)
- characters: characters present or referenced
- action: what happens in the scene
- dialogue: extracted dialogue as [{"character": "...", "line": "..."}] (max 3 per scene — split if more)
- mood: emotional tone
- visual_description: vivid visual description for image generation
- estimated_duration: estimated seconds (5-30s)

Also extract:
- characters: all character names
- locations: all locations
- tone: overall tone
- genre: genre(s)
- total_estimated_duration: sum

Return ONLY valid JSON.

TEXT:
"""

FREEFORM_PARSE_PROMPT = """You are a creative visual storytelling expert. The user has provided a freeform description of a story/scene. Parse it into structured scene beats for visual comic/manga/storyboard generation.

SCENE PACING (CRITICAL):
- Generate EXACTLY 4 to 6 scenes (minimum 4, maximum 6) — no exceptions
- Each scene should focus on ONE key moment, ONE location, or ONE emotional beat
- Do NOT cram multiple actions or locations into a single scene
- Prefer MORE scenes with LESS content each — each scene becomes one visual page
- NEVER generate more than 6 scenes or fewer than 4 scenes
- Even a single sentence of input should be expanded into 4-6 distinct visual moments

For each scene:
- scene_id: unique identifier (e.g., "sc_001")
- scene_number: sequential integer
- location: location (infer or create)
- time_of_day: time setting
- characters: characters involved
- action: what happens
- dialogue: any dialogue as [{"character": "...", "line": "..."}] (max 3 per scene — split if more)
- mood: emotional tone
- visual_description: DETAILED visual description for image generation (this is critical — be vivid and specific)
- estimated_duration: estimated seconds (5-30s)

Also provide:
- characters: all character names
- locations: all locations
- tone: overall tone
- genre: genre
- total_estimated_duration: sum

Return ONLY valid JSON.

DESCRIPTION:
"""


def _get_prompt_for_format(fmt: ScriptFormat) -> str:
    """Get the appropriate parsing prompt for the script format."""
    prompts = {
        ScriptFormat.SCREENPLAY: SCREENPLAY_PARSE_PROMPT,
        ScriptFormat.PROSE: PROSE_PARSE_PROMPT,
        ScriptFormat.FREEFORM: FREEFORM_PARSE_PROMPT,
    }
    return prompts.get(fmt, FREEFORM_PARSE_PROMPT)


def _detect_format(script: str) -> ScriptFormat:
    """Auto-detect script format if not specified.

    Looks for screenplay markers (INT., EXT., CUT TO:, etc.)
    or prose indicators (chapter headings, paragraph structure).
    """
    upper = script.upper()

    # Screenplay indicators
    screenplay_markers = ["INT.", "EXT.", "CUT TO:", "FADE IN:", "FADE OUT", "DISSOLVE TO:"]
    screenplay_hits = sum(1 for m in screenplay_markers if m in upper)
    if screenplay_hits >= 2:
        return ScriptFormat.SCREENPLAY

    # Prose indicators
    prose_markers = ["CHAPTER", "PART ", '"', "'"]
    prose_hits = sum(1 for m in prose_markers if m in upper)
    # Also check for paragraph-style writing (lots of periods, commas)
    if prose_hits >= 2 or (len(script) > 500 and script.count(".") > 10):
        return ScriptFormat.PROSE

    return ScriptFormat.FREEFORM


async def parse_script(
    script: str,
    format: ScriptFormat = ScriptFormat.FREEFORM,
    auto_detect: bool = True,
) -> ParsedScript:
    """Parse a script into structured scene beats.

    Args:
        script: Raw script text.
        format: Expected format. Auto-detected if auto_detect=True.
        auto_detect: Whether to auto-detect the script format.

    Returns:
        ParsedScript with structured scene beats.
    """
    # Auto-detect format if requested
    if auto_detect and format == ScriptFormat.FREEFORM:
        detected = _detect_format(script)
        if detected != ScriptFormat.FREEFORM:
            format = detected

    prompt = _get_prompt_for_format(format) + script

    client = get_client()
    response = await client.aio.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.3,  # Low temp for structured output
            max_output_tokens=8192,
            response_mime_type="application/json",
        ),
    )

    # Parse the JSON response
    try:
        raw_text = response.text.strip()
        # Handle potential markdown code fences
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
            raw_text = re.sub(r"\s*```$", "", raw_text)

        data = json.loads(raw_text)
    except (json.JSONDecodeError, AttributeError) as e:
        # Fallback: create a single scene from the raw script
        return _fallback_parse(script)

    # Build the ParsedScript — enforce 4-6 scene limit
    import logging
    _logger = logging.getLogger(__name__)
    raw_scenes = data.get("scenes", [])
    if len(raw_scenes) > 6:
        _logger.warning("ScriptParser: %d scenes returned, clamping to 6", len(raw_scenes))
        data["scenes"] = raw_scenes[:6]
    elif len(raw_scenes) < 4:
        _logger.warning("ScriptParser: Only %d scenes returned, retrying with stronger prompt", len(raw_scenes))
        # Retry with explicit instruction
        retry_prompt = (
            f"You previously returned only {len(raw_scenes)} scene(s). "
            "This is NOT acceptable. You MUST return EXACTLY 4 to 6 scenes. "
            "Break the story into more granular visual moments — one location, one action, one beat per scene. "
            "Even if the input is very short, expand and create 4-6 distinct visual scenes.\n\n"
            + prompt
        )
        retry_response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=retry_prompt,
            config=types.GenerateContentConfig(
                temperature=0.5,  # Slightly higher temp for more creativity
                max_output_tokens=8192,
                response_mime_type="application/json",
            ),
        )
        try:
            retry_text = retry_response.text.strip()
            if retry_text.startswith("```"):
                retry_text = re.sub(r"^```(?:json)?\s*", "", retry_text)
                retry_text = re.sub(r"\s*```$", "", retry_text)
            retry_data = json.loads(retry_text)
            if len(retry_data.get("scenes", [])) >= 4:
                data = retry_data
                _logger.info("ScriptParser: Retry succeeded with %d scenes", len(data["scenes"]))
            else:
                _logger.warning("ScriptParser: Retry still only %d scenes, using what we have", len(retry_data.get("scenes", [])))
                if len(retry_data.get("scenes", [])) > len(raw_scenes):
                    data = retry_data
        except Exception:
            _logger.warning("ScriptParser: Retry parse failed, using original %d scenes", len(raw_scenes))

    scenes = []
    for s in data.get("scenes", []):
        scene = SceneBeat(
            scene_id=s.get("scene_id", f"sc_{uuid.uuid4().hex[:6]}"),
            scene_number=s.get("scene_number", 0),
            location=s.get("location", "Unknown"),
            time_of_day=s.get("time_of_day", "DAY"),
            characters=s.get("characters", []),
            action=s.get("action", ""),
            dialogue=s.get("dialogue", []),
            mood=s.get("mood", "neutral"),
            visual_description=s.get("visual_description", s.get("action", "")),
            estimated_duration=float(s.get("estimated_duration", 5.0)),
        )
        scenes.append(scene)

    # Handle tone and genre as either strings or lists (join lists with commas)
    tone = data.get("tone", "")
    if isinstance(tone, list):
        tone = ", ".join(tone)
    
    genre = data.get("genre", "")
    if isinstance(genre, list):
        genre = ", ".join(genre)

    return ParsedScript(
        scenes=scenes,
        characters=data.get("characters", []),
        locations=data.get("locations", []),
        tone=tone,
        genre=genre,
        total_estimated_duration=float(data.get("total_estimated_duration", 0)),
    )


def _fallback_parse(script: str) -> ParsedScript:
    """Fallback parser when Gemini fails. Better than nothing.

    Creates a single scene from the raw text. Not ideal, but
    it keeps the pipeline running. Honesty: this is a band-aid.
    """
    return ParsedScript(
        scenes=[
            SceneBeat(
                scene_id="sc_fallback_001",
                scene_number=1,
                location="Unknown",
                time_of_day="DAY",
                characters=[],
                action=script[:500],
                dialogue=[],
                mood="neutral",
                visual_description=script[:300],
                estimated_duration=10.0,
            )
        ],
        characters=[],
        locations=["Unknown"],
        tone="unknown",
        genre="unknown",
        total_estimated_duration=10.0,
    )

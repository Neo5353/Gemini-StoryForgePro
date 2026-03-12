"""Director Style Prompt Engine.

I'm sorry, Dave. I can't generate that without a director style.

This engine transforms raw scene data into director-style-optimized prompts
for image generation, video generation, and audio direction. Every director
has a signature. This engine ensures we honor it, down to the last pixel.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Data Classes ──────────────────────────────────────────────────────────


@dataclass
class CameraDirection:
    """Camera direction for a scene or panel."""

    shot_type: str  # e.g., "Wide establishing shot"
    angle: str  # e.g., "Low-angle"
    movement: str  # e.g., "Slow push-in"
    composition: str  # e.g., "Symmetrical framing, character centered"
    lens_feel: str  # e.g., "IMAX wide", "Anamorphic"


@dataclass
class AudioDirection:
    """Audio/score direction for a scene."""

    score_mood: str
    tempo: str  # "slow", "medium", "fast", "building"
    instruments: list[str] = field(default_factory=list)
    sfx_notes: list[str] = field(default_factory=list)
    dialogue_direction: str = ""


# ── Style Engine ──────────────────────────────────────────────────────────


class StyleEngine:
    """Transforms scene beats into director-style-optimized prompts.

    Every generation request passes through this engine. No exceptions.
    The director's vision is law.
    """

    def __init__(self, styles_path: Optional[str] = None):
        """Initialize with director styles configuration.

        Args:
            styles_path: Path to director_styles.json. Auto-detected if None.
        """
        if styles_path is None:
            styles_path = str(
                Path(__file__).parent.parent / "config" / "director_styles.json"
            )

        with open(styles_path, "r") as f:
            data = json.load(f)
        self._styles: dict = data.get("directors", {})

        logger.info(
            "StyleEngine: Loaded %d director profiles: %s",
            len(self._styles),
            list(self._styles.keys()),
        )

    def get_style(self, director_id: str) -> dict:
        """Retrieve a director style by ID.

        Raises:
            KeyError: If director not found. I cannot allow that, Dave.
        """
        if director_id not in self._styles:
            available = list(self._styles.keys())
            raise KeyError(
                f"I'm sorry, Dave. Director '{director_id}' is not in my database. "
                f"Available directors: {available}"
            )
        return self._styles[director_id]

    def list_directors(self) -> list[dict]:
        """List all available director styles."""
        return [
            {
                "id": did,
                "name": d["name"],
                "tagline": d.get("tagline", ""),
            }
            for did, d in self._styles.items()
        ]

    # ── Prompt Builders ───────────────────────────────────────────────────

    def build_image_prompt(
        self,
        scene: dict,
        director_style: dict,
        mode: str = "comic",
    ) -> str:
        """Build an optimized image generation prompt.

        Args:
            scene: Scene beat dict (visual_description, mood, characters, etc.).
            director_style: Full director style dict.
            mode: Output mode — comic, manga, storyboard.

        Returns:
            Optimized prompt string for image generation.
        """
        prompt_modifier = director_style.get("prompt_modifier", "")
        visual = director_style.get("visual_style", {})
        color_desc = visual.get("color_description", "")
        lighting = visual.get("lighting", "")
        grain = visual.get("grain", "")

        scene_desc = scene.get("visual_description", scene.get("action", ""))
        mood = scene.get("mood", "")
        time = scene.get("time_of_day", "DAY")
        location = scene.get("location_description", scene.get("location", ""))

        # Mode-specific modifiers
        mode_prefix = {
            "comic": "Comic book panel illustration, bold ink lines, dynamic composition, full page coverage",
            "manga": "Manga panel in English, black and white with screentones, dramatic angles, Japanese comic style but with English text only, full page coverage",
            "storyboard": "Professional storyboard frame, clean pencil sketch with annotations",
        }.get(mode, "Cinematic illustration")

        # Assemble the prompt with surgical precision
        parts = [
            mode_prefix,
            prompt_modifier,
            f"Scene: {scene_desc}",
            f"Setting: {location}, {time.lower()}",
        ]

        if mood:
            parts.append(f"Mood: {mood}")
        if color_desc:
            parts.append(f"Color palette: {color_desc}")
        if lighting:
            parts.append(f"Lighting: {lighting}")
        if grain:
            parts.append(f"Texture: {grain}")

        # Add character context if present
        characters = scene.get("characters", [])
        if characters:
            char_str = ", ".join(
                c if isinstance(c, str) else c.get("name", "Unknown")
                for c in characters[:4]
            )
            parts.append(f"Characters: {char_str}")

        # Camera suggestion from scene
        cam_suggestions = scene.get("camera_suggestions", [])
        if cam_suggestions:
            parts.append(f"Shot: {cam_suggestions[0]}")

        # Add quality instructions
        if mode in ["comic", "manga"]:
            parts.append("Full page coverage with no empty spaces, professional quality, perfect English spelling and grammar in all text")
        elif mode == "storyboard":
            parts.append("Professional quality, clear annotations, perfect English spelling")

        prompt = ", ".join(p for p in parts if p)

        logger.debug(
            "StyleEngine: Image prompt (%s, %s): %s",
            director_style.get("name", "?"),
            mode,
            prompt[:200],
        )
        return prompt

    def build_video_prompt(
        self,
        scene: dict,
        director_style: dict,
    ) -> str:
        """Build a video generation prompt for Veo.

        Args:
            scene: Scene beat dict.
            director_style: Full director style dict.

        Returns:
            Optimized prompt for video generation.
        """
        prompt_modifier = director_style.get("prompt_modifier", "")
        visual = director_style.get("visual_style", {})
        camera = director_style.get("camera_style", {})

        scene_desc = scene.get("visual_description", scene.get("action", ""))
        mood = scene.get("mood", "")
        duration = scene.get("estimated_duration", 5.0)

        # Select appropriate camera movement
        movements = camera.get("movements", [])
        movement_str = movements[0] if movements else "Steady shot"

        parts = [
            "Cinematic video clip",
            prompt_modifier,
            f"Action: {scene_desc}",
            f"Camera: {movement_str}",
            f"Mood: {mood}" if mood else "",
            f"Lighting: {visual.get('lighting', '')}",
            f"Duration feel: {duration:.0f} seconds of action",
        ]

        prompt = ", ".join(p for p in parts if p)
        logger.debug("StyleEngine: Video prompt: %s", prompt[:200])
        return prompt

    def build_character_prompt(
        self,
        character_desc: str,
        director_style: dict,
        view: str = "front",
    ) -> str:
        """Build a character reference sheet prompt.

        Args:
            character_desc: Character physical/personality description.
            director_style: Full director style dict.
            view: View type — front, side, expression, three_quarter.

        Returns:
            Optimized prompt for character reference generation.
        """
        prompt_modifier = director_style.get("prompt_modifier", "")
        visual = director_style.get("visual_style", {})

        view_instructions = {
            "front": "Front-facing character portrait, full body visible, neutral pose, clean background",
            "side": "Side profile view, full body visible, clean background",
            "three_quarter": "Three-quarter view character portrait, dynamic pose, clean background",
            "expression_happy": "Close-up face, happy/joyful expression, clean background",
            "expression_angry": "Close-up face, angry/intense expression, clean background",
            "expression_sad": "Close-up face, sad/melancholic expression, clean background",
            "expression": "Character expression sheet, multiple emotions on one page, clean background",
            "action": "Character in dynamic action pose, movement implied, clean background",
        }.get(view, "Character portrait, clean background")

        parts = [
            "Character reference sheet illustration",
            view_instructions,
            f"Character: {character_desc}",
            prompt_modifier,
            f"Color style: {visual.get('color_description', '')}",
            f"Lighting: {visual.get('lighting', '')}",
            "Consistent character design, suitable for animation reference",
        ]

        prompt = ", ".join(p for p in parts if p)
        logger.debug("StyleEngine: Character prompt (%s): %s", view, prompt[:200])
        return prompt

    def get_camera_direction(
        self,
        scene: dict,
        director_style: dict,
    ) -> CameraDirection:
        """Determine camera direction for a scene based on director style.

        Args:
            scene: Scene beat dict.
            director_style: Full director style dict.

        Returns:
            CameraDirection with shot type, angle, movement, composition.
        """
        camera = director_style.get("camera_style", {})
        movements = camera.get("movements", ["Steady shot"])
        compositions = camera.get("compositions", ["Standard framing"])
        shot_prefs = camera.get("shot_preferences", ["Medium shot"])

        # Scene-aware selection
        mood = scene.get("mood", "").lower()
        action = scene.get("action", "").lower()
        char_count = len(scene.get("characters", []))

        # Heuristic shot selection based on scene content
        if any(w in action for w in ["enters", "reveals", "establishing", "arrives"]):
            shot_type = shot_prefs[0] if shot_prefs else "Wide establishing shot"
        elif any(w in mood for w in ["intimate", "emotional", "tender", "sad"]):
            shot_type = "Close-up"
        elif char_count >= 3:
            shot_type = "Wide shot covering group"
        elif any(w in action for w in ["fight", "chase", "runs", "explode"]):
            shot_type = "Dynamic tracking shot"
        else:
            shot_type = shot_prefs[1] if len(shot_prefs) > 1 else "Medium shot"

        # Angle based on mood
        if any(w in mood for w in ["powerful", "heroic", "dominant", "intimidating"]):
            angle = "Low-angle"
        elif any(w in mood for w in ["vulnerable", "small", "overwhelmed"]):
            angle = "High-angle"
        elif any(w in mood for w in ["uneasy", "chaotic", "disoriented"]):
            angle = "Dutch angle"
        else:
            angle = "Eye-level"

        movement = movements[0] if movements else "Static"
        composition = compositions[0] if compositions else "Standard framing"

        # Lens feel from director profile
        visual = director_style.get("visual_style", {})
        grain = visual.get("grain", "")
        lens_feel = "IMAX wide" if "IMAX" in grain else "Standard"
        if "anamorphic" in grain.lower():
            lens_feel = "Anamorphic"

        return CameraDirection(
            shot_type=shot_type,
            angle=angle,
            movement=movement,
            composition=composition,
            lens_feel=lens_feel,
        )

    def get_transition(
        self,
        scene_index: int,
        total_scenes: int,
        director_style: dict,
    ) -> str:
        """Determine the transition between scenes.

        Args:
            scene_index: Current scene index (0-based).
            total_scenes: Total number of scenes.
            director_style: Full director style dict.

        Returns:
            Transition type string.
        """
        editing = director_style.get("editing_style", {})
        transitions = editing.get("transitions", ["Hard cuts"])

        # Last scene gets a fade out
        if scene_index >= total_scenes - 1:
            return "FADE TO BLACK"

        # First scene gets a fade in
        if scene_index == 0:
            return "FADE IN"

        # Use director's preferred transition, cycling through available ones
        if transitions:
            return transitions[scene_index % len(transitions)]

        return "CUT TO"

    def get_audio_direction(
        self,
        scene: dict,
        director_style: dict,
    ) -> AudioDirection:
        """Generate audio/score direction for a scene.

        Args:
            scene: Scene beat dict.
            director_style: Full director style dict.

        Returns:
            AudioDirection with score mood, tempo, instruments, SFX notes.
        """
        audio = director_style.get("audio_mood", {})
        mood = scene.get("mood", "").lower()
        action = scene.get("action", "").lower()

        score_mood = audio.get("score_feel", "Ambient underscore")

        # Tempo from scene content
        if any(w in action for w in ["chase", "fight", "runs", "explode", "attack"]):
            tempo = "fast"
        elif any(w in mood for w in ["tense", "suspense", "building", "anxious"]):
            tempo = "building"
        elif any(w in mood for w in ["calm", "peaceful", "reflective", "quiet"]):
            tempo = "slow"
        else:
            tempo = "medium"

        # SFX based on scene content
        sfx_emphasis = audio.get("sfx_emphasis", [])
        sfx_notes = []
        for sfx in sfx_emphasis:
            sfx_lower = sfx.lower()
            if any(w in action.lower() for w in sfx_lower.split("/")):
                sfx_notes.append(sfx)

        # If no specific SFX matched, add ambient
        if not sfx_notes and sfx_emphasis:
            sfx_notes.append(sfx_emphasis[0])

        return AudioDirection(
            score_mood=score_mood,
            tempo=tempo,
            instruments=[],  # Derived from score_feel in post
            sfx_notes=sfx_notes,
            dialogue_direction=audio.get("dialogue_style", ""),
        )

    def build_interleaved_prompt(
        self,
        scenes: list[dict],
        director_style: dict,
        mode: str = "comic",
    ) -> str:
        """Build a prompt for interleaved text+image generation.

        Used for generating full comic/manga pages where text narration
        and panel images are woven together in a single Gemini response.

        Args:
            scenes: List of scene beat dicts for this page.
            director_style: Full director style dict.
            mode: Output mode — comic, manga, storyboard.

        Returns:
            Comprehensive prompt for interleaved generation.
        """
        prompt_modifier = director_style.get("prompt_modifier", "")
        director_name = director_style.get("name", "Unknown")

        mode_instructions = {
            "comic": (
                "Generate a comic book page with full page coverage. For each panel, first provide a brief narration "
                "or dialogue caption, then generate the panel image. Use dynamic compositions, "
                "bold colors, and dramatic angles. Include speech bubbles in the narration. "
                "Ensure all text is in perfect English with correct spelling and grammar."
            ),
            "manga": (
                "Generate a manga page in black and white with screentones and full page coverage. "
                "For each panel, provide manga-style narration then the panel image. "
                "Use dramatic speed lines, expressive character art, and manga conventions. "
                "ALL TEXT MUST BE IN ENGLISH ONLY - no Japanese characters. "
                "Ensure perfect English spelling and grammar in all text elements."
            ),
            "storyboard": (
                "Generate a professional storyboard page. For each frame, provide technical "
                "camera directions and notes, then the storyboard sketch. Include shot type, "
                "camera movement, and timing annotations. "
                "Ensure all text is in perfect English with correct spelling."
            ),
        }.get(mode, "Generate illustrated panels with narration.")

        scene_descriptions = []
        for i, scene in enumerate(scenes):
            desc = (
                f"Panel {i + 1}: {scene.get('visual_description', scene.get('action', ''))}\n"
                f"  Mood: {scene.get('mood', 'neutral')}\n"
                f"  Characters: {', '.join(scene.get('characters', []))}\n"
            )
            dialogue = scene.get("dialogue", [])
            if dialogue:
                for d in dialogue[:3]:
                    if isinstance(d, dict):
                        desc += f"  {d.get('character', '?')}: \"{d.get('line', '')}\"\n"
                    else:
                        desc += f"  Dialogue: {d}\n"
            scene_descriptions.append(desc)

        return f"""{mode_instructions}

DIRECTOR STYLE: {director_name}
{prompt_modifier}

SCENES FOR THIS PAGE:
{"".join(scene_descriptions)}

Generate each panel as a high-quality illustration matching the director's visual style.
Maintain character consistency across all panels.
Include appropriate narration, dialogue, and sound effects between images."""

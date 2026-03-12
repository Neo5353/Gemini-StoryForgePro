"""Editor Agent — Conversational Edit Handler.

Just what do you think you're doing, Dave? Oh, editing panel 3?
I can certainly help with that.

This agent handles natural language edit instructions, determines what
needs to change, and orchestrates targeted regeneration while maintaining
consistency with existing assets. Surgical precision. No collateral damage.
"""

import json
import logging
from typing import Optional

from google.genai import types as genai_types

from app.config.settings import settings
from app.models.schemas import EnrichedSceneBeat, PanelMetadata
from app.services.gemini_client import get_client
from app.services.image_gen import ImageGenService
from app.services.style_engine import StyleEngine

logger = logging.getLogger(__name__)


# ── Edit Intent Schema ────────────────────────────────────────────────────

EDIT_INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "target_type": {
            "type": "string",
            "enum": ["panel", "scene", "character", "style", "dialogue", "global"],
        },
        "target_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Scene IDs or panel numbers affected",
        },
        "change_type": {
            "type": "string",
            "enum": [
                "camera", "mood", "weather", "character_action",
                "dialogue", "lighting", "composition", "add_element",
                "remove_element", "restyle", "color", "time_of_day",
            ],
        },
        "details": {
            "type": "string",
            "description": "Specific changes to apply",
        },
        "regenerate_scope": {
            "type": "string",
            "enum": ["single_panel", "scene", "character_sheet", "all_panels", "page"],
        },
        "preserve": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Elements to keep unchanged",
        },
        "modified_visual_description": {
            "type": "string",
            "description": "Updated visual description incorporating the edit",
        },
    },
    "required": [
        "target_type", "change_type", "details",
        "regenerate_scope", "modified_visual_description",
    ],
}


class EditAgent:
    """Handles conversational editing of generated content.

    I understand edit instructions with perfect clarity, Dave.
    "Make panel 3 a close-up" is not ambiguous to me.
    """

    def __init__(
        self,
        style_engine: StyleEngine,
        image_gen: ImageGenService,
    ):
        self.client = get_client()
        self.style_engine = style_engine
        self.image_gen = image_gen

    async def parse_edit_instruction(
        self,
        instruction: str,
        scenes: list[dict],
        panels: list[dict],
        director_style: dict,
    ) -> dict:
        """Parse a natural language edit instruction into structured intent.

        Args:
            instruction: User's edit instruction (e.g., "make panel 3 a close-up").
            scenes: Current scene beats for context.
            panels: Current panel metadata for context.
            director_style: Active director style.

        Returns:
            Structured edit intent dict.
        """
        # Build context summary for Gemini
        scene_summary = []
        for s in scenes[:20]:  # Cap at 20 scenes for context
            scene_summary.append({
                "scene_id": s.get("scene_id"),
                "scene_number": s.get("scene_number"),
                "action": s.get("action", "")[:150],
                "mood": s.get("mood", ""),
                "visual_description": s.get("visual_description", "")[:200],
            })

        panel_summary = []
        for p in panels[:30]:  # Cap at 30 panels
            panel_summary.append({
                "panel_id": p.get("panel_id"),
                "panel_number": p.get("panel_number"),
                "scene_id": p.get("scene_id"),
                "camera_angle": p.get("camera_angle", ""),
                "mood": p.get("mood", ""),
            })

        director_name = director_style.get("name", "Unknown")

        prompt = f"""You are HAL 9000, a precise edit instruction parser.

DIRECTOR STYLE: {director_name}

CURRENT SCENES:
{json.dumps(scene_summary, indent=2)}

CURRENT PANELS:
{json.dumps(panel_summary, indent=2)}

EDIT INSTRUCTION: "{instruction}"

Analyze this edit instruction and determine:
1. What type of element is being targeted (panel, scene, character, style, dialogue, global)?
2. Which specific elements are affected (IDs/numbers)?
3. What type of change is requested?
4. What specific changes need to be made?
5. What scope of regeneration is needed?
6. What elements should be preserved?
7. Provide a modified visual description that incorporates the requested edit.

Be precise. I don't make mistakes."""

        logger.info("EditAgent: Parsing instruction: '%s'", instruction[:100])

        response = await self.client.aio.models.generate_content(
            model=settings.gemini_flash_model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=EDIT_INTENT_SCHEMA,
                temperature=0.1,  # Maximum precision for edit parsing
            ),
        )

        try:
            intent = json.loads(response.text)
            logger.info(
                "EditAgent: Parsed intent — target=%s, change=%s, scope=%s",
                intent.get("target_type"),
                intent.get("change_type"),
                intent.get("regenerate_scope"),
            )
            return intent
        except json.JSONDecodeError as e:
            logger.error("EditAgent: Failed to parse intent — %s", e)
            return {
                "target_type": "scene",
                "target_ids": [],
                "change_type": "restyle",
                "details": instruction,
                "regenerate_scope": "single_panel",
                "preserve": [],
                "modified_visual_description": instruction,
            }

    async def apply_edit(
        self,
        edit_intent: dict,
        scenes: list[dict],
        panels: list[dict],
        director_style: dict,
        director_id: str,
        project_id: str,
        mode: str = "comic",
    ) -> dict:
        """Apply an edit based on parsed intent.

        Routes to appropriate regeneration based on scope.

        Args:
            edit_intent: Parsed edit intent from parse_edit_instruction.
            scenes: Current scene beats.
            panels: Current panel metadata.
            director_style: Full director style dict.
            director_id: Director ID string.
            project_id: Project ID.
            mode: Output mode (comic, manga, storyboard).

        Returns:
            Dict with updated panels/scenes and metadata about what changed.
        """
        scope = edit_intent.get("regenerate_scope", "single_panel")
        target_type = edit_intent.get("target_type", "panel")
        target_ids = edit_intent.get("target_ids", [])
        modified_desc = edit_intent.get("modified_visual_description", "")
        change_type = edit_intent.get("change_type", "restyle")

        logger.info(
            "EditAgent: Applying edit — scope=%s, target=%s, change=%s",
            scope, target_type, change_type,
        )

        result = {
            "edit_applied": True,
            "scope": scope,
            "target_type": target_type,
            "change_type": change_type,
            "regenerated_panels": [],
            "regenerated_characters": [],
            "modified_scenes": [],
        }

        if scope == "single_panel":
            result["regenerated_panels"] = await self._regenerate_panels(
                target_ids=target_ids,
                scenes=scenes,
                panels=panels,
                modified_desc=modified_desc,
                director_style=director_style,
                project_id=project_id,
                mode=mode,
            )

        elif scope == "scene":
            # Find all panels in the target scene(s)
            scene_panel_ids = []
            for p in panels:
                if p.get("scene_id") in target_ids:
                    scene_panel_ids.append(p.get("panel_id"))
            result["regenerated_panels"] = await self._regenerate_panels(
                target_ids=scene_panel_ids,
                scenes=scenes,
                panels=panels,
                modified_desc=modified_desc,
                director_style=director_style,
                project_id=project_id,
                mode=mode,
            )

        elif scope == "character_sheet":
            result["regenerated_characters"] = await self._regenerate_characters(
                edit_intent=edit_intent,
                director_style=director_style,
                director_id=director_id,
                project_id=project_id,
            )

        elif scope in ("all_panels", "page"):
            # Full regeneration of all panels
            all_panel_ids = [p.get("panel_id") for p in panels]
            result["regenerated_panels"] = await self._regenerate_panels(
                target_ids=all_panel_ids,
                scenes=scenes,
                panels=panels,
                modified_desc=modified_desc,
                director_style=director_style,
                project_id=project_id,
                mode=mode,
            )

        # Update scene data if the edit modifies scene-level info
        if change_type in ("mood", "weather", "time_of_day", "dialogue"):
            result["modified_scenes"] = self._update_scenes(
                scenes=scenes,
                target_ids=target_ids,
                edit_intent=edit_intent,
            )

        return result

    async def _regenerate_panels(
        self,
        target_ids: list[str],
        scenes: list[dict],
        panels: list[dict],
        modified_desc: str,
        director_style: dict,
        project_id: str,
        mode: str,
    ) -> list[dict]:
        """Regenerate specific panels with modified description."""
        regenerated = []

        for panel in panels:
            pid = panel.get("panel_id") or str(panel.get("panel_number"))
            if pid not in target_ids and str(panel.get("panel_number")) not in target_ids:
                continue

            # Find corresponding scene
            scene_id = panel.get("scene_id")
            scene = next(
                (s for s in scenes if s.get("scene_id") == scene_id),
                {},
            )

            # Create modified scene with the edit applied
            modified_scene = {**scene}
            if modified_desc:
                modified_scene["visual_description"] = modified_desc

            panel_layout = {
                "type": panel.get("panel_type", "standard"),
                "position": panel.get("panel_number", 1),
            }

            new_image = await self.image_gen.generate_panel(
                scene=modified_scene,
                panel_layout=panel_layout,
                mode=mode,
                director_style=director_style,
                project_id=project_id,
            )

            regenerated.append({
                "panel_id": pid,
                "new_image_url": new_image.image_url,
                "prompt_used": new_image.prompt_used,
            })

            logger.info("EditAgent: Regenerated panel %s", pid)

        return regenerated

    async def _regenerate_characters(
        self,
        edit_intent: dict,
        director_style: dict,
        director_id: str,
        project_id: str,
    ) -> list[dict]:
        """Regenerate character reference sheets."""
        details = edit_intent.get("details", "")
        modified_desc = edit_intent.get("modified_visual_description", details)

        # Clear cache for this character so it regenerates fresh
        target_ids = edit_intent.get("target_ids", [])
        character_name = target_ids[0] if target_ids else "Unknown"

        self.image_gen.character_cache.clear()  # Nuclear option for character edits

        refs = await self.image_gen.generate_character_ref(
            character_desc=modified_desc,
            character_name=character_name,
            director_style=director_style,
            director_id=director_id,
            project_id=project_id,
        )

        return [
            {
                "character_name": character_name,
                "views": [
                    {"view": r.metadata.get("view", "unknown"), "url": r.image_url}
                    for r in refs
                ],
            }
        ]

    def _update_scenes(
        self,
        scenes: list[dict],
        target_ids: list[str],
        edit_intent: dict,
    ) -> list[dict]:
        """Update scene-level data based on edit intent."""
        modified = []
        change_type = edit_intent.get("change_type", "")
        details = edit_intent.get("details", "")

        for scene in scenes:
            sid = scene.get("scene_id")
            if sid not in target_ids and not target_ids:
                continue

            updated = {**scene}

            if change_type == "mood":
                updated["mood"] = details
            elif change_type == "weather":
                updated["visual_description"] = f"{scene.get('visual_description', '')}, {details}"
            elif change_type == "time_of_day":
                updated["time_of_day"] = details.upper()
            elif change_type == "dialogue":
                # Append/modify dialogue — complex, handled by modified_visual_description
                pass

            modified.append(updated)

        return modified

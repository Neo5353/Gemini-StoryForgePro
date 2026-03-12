"""Content Sanitizer — Scans and rephrases script content for safe image generation.

Automatically detects content that may trigger AI image safety filters
and rephrases it to be generation-safe while preserving story intent.
"""

import logging
from typing import Optional

from google.genai import types as genai_types

from app.services.gemini_client import get_client

logger = logging.getLogger("storyforge.sanitizer")

# Gemini text model for rephrasing (fast, cheap)
SANITIZER_MODEL = "gemini-2.5-flash"

SANITIZE_PROMPT = """You are a content safety specialist for an AI comic book generator.

Your job: Rewrite scene descriptions so they are SAFE for AI image generation while keeping the story exciting and faithful to the original intent.

AI image generators block content involving:
- Physical restraint (tied up, bound, chained, handcuffed)
- Poison, drugs, or harmful substances being administered
- Graphic violence (stabbing, shooting, blood, gore)
- Weapons pointed at people
- Child endangerment
- Self-harm or suicide themes
- Sexual content or nudity
- Hate symbols or slurs

RULES:
1. PRESERVE the story's core plot, emotions, and drama
2. REPLACE blocked concepts with visually equivalent safe alternatives:
   - "tied with ropes" → "trapped behind an energy barrier" or "held in a containment pod"
   - "poison in food" → "enchanted/cursed food glowing with dark energy" or "tainted with a glowing serum"
   - "fights and kills villains" → "defeats villains" or "overpowers villains"
   - "stabbed" → "struck by a blast of energy"
   - Weapons → energy blasts, force fields, magical powers
3. Keep the SAME characters, locations, and story progression
4. Make it MORE visually interesting for comics (energy effects, dramatic lighting, etc.)
5. Output ONLY the rephrased text, no explanations

If the content is already safe, return it unchanged."""


async def sanitize_scene_text(text: str) -> str:
    """Sanitize a single scene description for safe image generation.
    
    Args:
        text: Raw scene description that may contain blocked content.
        
    Returns:
        Rephrased safe version, or original if already safe.
    """
    if not text or len(text.strip()) < 10:
        return text

    client = get_client()

    try:
        response = await client.aio.models.generate_content(
            model=SANITIZER_MODEL,
            contents=f"{SANITIZE_PROMPT}\n\n--- SCENE TEXT TO SANITIZE ---\n{text}\n--- END ---\n\nSafe version:",
            config=genai_types.GenerateContentConfig(
                temperature=0.3,  # Low creativity, faithful rephrasing
                max_output_tokens=1024,
            ),
        )

        if response and response.text:
            sanitized = response.text.strip()
            if sanitized != text:
                logger.info("Sanitizer: Rephrased scene content (was %d chars, now %d chars)", len(text), len(sanitized))
            return sanitized
        return text

    except Exception as e:
        logger.warning("Sanitizer: Failed to sanitize text, using original: %s", e)
        return text


async def sanitize_scenes(scenes: list[dict]) -> list[dict]:
    """Sanitize all scenes in a parsed script for safe image generation.
    
    Scans and rephrases action, visual_description, and dialogue fields.
    Returns a new list with sanitized copies (originals unchanged).
    
    Args:
        scenes: List of scene dicts from parsed script.
        
    Returns:
        List of sanitized scene dicts.
    """
    if not scenes:
        return scenes

    client = get_client()

    # Build a single batch prompt for all scenes (more efficient than per-scene)
    scene_texts = []
    for i, scene in enumerate(scenes):
        parts = []
        if scene.get("action"):
            parts.append(f"Action: {scene['action']}")
        if scene.get("visual_description"):
            parts.append(f"Visual: {scene['visual_description']}")
        if scene.get("dialogue"):
            for d in scene["dialogue"]:
                if isinstance(d, dict):
                    parts.append(f"Dialogue: {d.get('character', '?')}: {d.get('line', '')}")
                else:
                    parts.append(f"Dialogue: {d}")
        scene_texts.append(f"[SCENE {i+1}]\n" + "\n".join(parts))

    batch_input = "\n\n".join(scene_texts)

    batch_prompt = f"""{SANITIZE_PROMPT}

--- SCENES TO SANITIZE ---
{batch_input}
--- END ---

Output each scene in the EXACT same format with [SCENE N] headers. Only change text that needs sanitizing:"""

    try:
        response = await client.aio.models.generate_content(
            model=SANITIZER_MODEL,
            contents=batch_prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=4096,
            ),
        )

        if not response or not response.text:
            logger.warning("Sanitizer: No response from batch sanitization, using originals")
            return scenes

        # Parse the response back into scene updates
        sanitized_scenes = _parse_batch_response(response.text, scenes)
        
        changed = sum(1 for o, s in zip(scenes, sanitized_scenes) 
                      if o.get("action") != s.get("action") or o.get("visual_description") != s.get("visual_description"))
        if changed:
            logger.info("Sanitizer: Rephrased %d/%d scenes for safe generation", changed, len(scenes))
        else:
            logger.info("Sanitizer: All %d scenes are already safe", len(scenes))

        return sanitized_scenes

    except Exception as e:
        logger.warning("Sanitizer: Batch sanitization failed, using originals: %s", e)
        return scenes


def _parse_batch_response(response_text: str, original_scenes: list[dict]) -> list[dict]:
    """Parse the batch sanitizer response and merge with original scenes.
    
    Returns new scene dicts with sanitized fields applied.
    """
    import re
    
    # Split response by [SCENE N] markers
    scene_blocks = re.split(r'\[SCENE\s+\d+\]', response_text)
    scene_blocks = [b.strip() for b in scene_blocks if b.strip()]

    sanitized = []
    for i, scene in enumerate(original_scenes):
        new_scene = dict(scene)  # Copy

        if i < len(scene_blocks):
            block = scene_blocks[i]
            
            # Extract fields from the block
            action_match = re.search(r'Action:\s*(.+?)(?=\n(?:Visual:|Dialogue:)|$)', block, re.DOTALL)
            visual_match = re.search(r'Visual:\s*(.+?)(?=\n(?:Action:|Dialogue:)|$)', block, re.DOTALL)

            if action_match:
                new_scene["action"] = action_match.group(1).strip()
            if visual_match:
                new_scene["visual_description"] = visual_match.group(1).strip()

            # Update dialogue if present
            dialogue_matches = re.findall(r'Dialogue:\s*(.+?):\s*(.+?)(?=\nDialogue:|\n(?:Action:|Visual:)|$)', block)
            if dialogue_matches and scene.get("dialogue"):
                new_dialogue = []
                for j, (char, line) in enumerate(dialogue_matches):
                    if j < len(scene["dialogue"]):
                        orig = scene["dialogue"][j]
                        if isinstance(orig, dict):
                            new_dialogue.append({**orig, "character": char.strip(), "line": line.strip()})
                        else:
                            new_dialogue.append(f"{char.strip()}: {line.strip()}")
                    else:
                        new_dialogue.append({"character": char.strip(), "line": line.strip()})
                if new_dialogue:
                    new_scene["dialogue"] = new_dialogue

        sanitized.append(new_scene)

    return sanitized

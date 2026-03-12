"""Character Designer Service — Giving faces to names.

Uses Imagen (via google-genai) to generate character reference sheets.
Front view, side view, and expression variants — because every character
deserves a proper casting call.
"""

import uuid
from typing import Optional

from google.genai import types

from app.config.settings import settings
from app.models.schemas import CharacterSheet, CharacterView
from app.services.gemini_client import get_client
from app.services.storage import upload_image


# View configurations for character reference sheets
CHARACTER_VIEWS = [
    {
        "view_type": "front",
        "prompt_suffix": "front-facing portrait view, centered, neutral expression, full face visible, character reference sheet style",
    },
    {
        "view_type": "side",
        "prompt_suffix": "side profile view, 90 degree angle, character reference sheet style",
    },
    {
        "view_type": "expression_happy",
        "prompt_suffix": "front-facing, happy joyful expression, warm smile, character expression sheet",
    },
    {
        "view_type": "expression_angry",
        "prompt_suffix": "front-facing, angry intense expression, furrowed brows, character expression sheet",
    },
    {
        "view_type": "expression_sad",
        "prompt_suffix": "front-facing, sad melancholic expression, downcast eyes, character expression sheet",
    },
]


def _build_character_prompt(
    character_name: str,
    character_description: str,
    view_config: dict,
    style_modifier: str = "",
) -> str:
    """Build the image generation prompt for a character view.

    Combines character description + view specification + director style.
    """
    parts = [
        f"Character illustration of {character_name}.",
        character_description,
        view_config["prompt_suffix"],
        "High quality, detailed, consistent character design.",
    ]
    if style_modifier:
        parts.append(style_modifier)

    return " ".join(parts)


async def generate_character_sheet(
    character_name: str,
    character_description: str,
    project_id: str,
    director_style: Optional[dict] = None,
    views: Optional[list[dict]] = None,
) -> CharacterSheet:
    """Generate a complete character reference sheet.

    Args:
        character_name: Name of the character.
        character_description: Physical description and personality.
        project_id: Project ID for storage organization.
        director_style: Optional director style profile dict.
        views: Optional custom view configs. Defaults to CHARACTER_VIEWS.

    Returns:
        CharacterSheet with all generated views.
    """
    client = get_client()
    style_modifier = ""
    style_name = ""

    if director_style:
        style_modifier = director_style.get("prompt_modifier", "")
        style_name = director_style.get("name", "")

    if views is None:
        views = CHARACTER_VIEWS

    generated_views: list[CharacterView] = []

    for view_config in views:
        prompt = _build_character_prompt(
            character_name,
            character_description,
            view_config,
            style_modifier,
        )

        try:
            # Use Imagen for image generation
            response = await client.aio.models.generate_images(
                model=settings.imagen_model,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="1:1",
                    safety_filter_level="BLOCK_ONLY_HIGH",
                ),
            )

            if response.generated_images:
                image_data = response.generated_images[0].image.image_bytes
                filename = f"{character_name.lower().replace(' ', '_')}_{view_config['view_type']}_{uuid.uuid4().hex[:6]}.png"

                image_url = await upload_image(
                    image_bytes=image_data,
                    project_id=project_id,
                    category="characters",
                    filename=filename,
                )

                generated_views.append(CharacterView(
                    view_type=view_config["view_type"],
                    image_url=image_url,
                    prompt_used=prompt,
                ))
        except Exception as e:
            # Log but don't fail the entire sheet for one bad view
            print(f"⚠️ Failed to generate {view_config['view_type']} for {character_name}: {e}")
            generated_views.append(CharacterView(
                view_type=view_config["view_type"],
                image_url="",
                prompt_used=f"FAILED: {prompt}",
            ))

    return CharacterSheet(
        character_name=character_name,
        description=character_description,
        views=generated_views,
        style_applied=style_name,
    )


async def generate_character_descriptions(
    characters: list[str],
    script_context: str,
) -> dict[str, str]:
    """Use Gemini to generate visual descriptions for characters.

    When the script doesn't describe characters visually, we need
    Gemini to infer what they might look like based on context.

    Args:
        characters: List of character names.
        script_context: The full script or synopsis.

    Returns:
        Dict mapping character name -> visual description.
    """
    client = get_client()

    prompt = f"""Based on the following script/story, generate detailed visual character descriptions for each character listed.

For each character, describe:
- Approximate age and build
- Hair color, style, and length
- Distinctive facial features
- Typical clothing/costume
- Overall vibe/energy

Characters: {', '.join(characters)}

Script context:
{script_context[:3000]}

Return ONLY valid JSON: {{"character_name": "visual description", ...}}"""

    response = await client.aio.models.generate_content(
        model=settings.gemini_flash_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=4096,
            response_mime_type="application/json",
        ),
    )

    try:
        import json, re
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception:
        # Fallback: generic descriptions
        return {name: f"A character named {name}" for name in characters}

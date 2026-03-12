"""Story Chat — generate scripts through conversation with Gemini.

User describes an idea, AI asks clarifying questions and builds
the script iteratively. Like having a writing partner.
"""

import logging
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter

from app.services.gemini_client import get_client
from google.genai import types as genai_types

logger = logging.getLogger(__name__)
router = APIRouter()

SYSTEM_PROMPT = """You are a creative screenwriting partner for StoryForge Pro, an AI visual story studio that turns scripts into comics, manga, storyboards, and cinematic trailers.

Your job: Help the user develop their story idea into a detailed script through natural conversation.

## How to behave:
1. When the user shares a vague idea, ask 2-3 SHORT clarifying questions (genre, tone, characters, setting)
2. When you have enough context, start drafting scenes
3. Keep responses concise — no walls of text
4. Be enthusiastic and creative, suggest twists and details
5. Match the user's energy — casual or serious

## When you have enough detail, output the script in this format:
```script
TITLE: [Story Title]

SCENE 1: [Location] - [Time]
[Detailed visual description of what happens. Include character actions, emotions, camera-worthy moments. 3-5 sentences.]

SCENE 2: [Location] - [Time]
[...]
```

## Rules:
- Aim for 4-8 scenes (good for comics/storyboards)
- Each scene should be visually distinct and interesting
- Include character names and dialogue cues
- DON'T output the script block until the user's idea is developed enough
- When you DO output script, still be conversational — explain your choices
- If user says "that's good" or "generate" or similar, finalize the script"""


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    user_message: str


class ChatResponse(BaseModel):
    reply: str
    script: Optional[str] = None  # Extracted script if present


@router.post("/story")
async def chat_story(req: ChatRequest) -> dict:
    """Chat with Gemini to develop a story idea into a script."""
    client = get_client()

    # Build conversation history for Gemini
    contents = []
    for msg in req.messages:
        contents.append(genai_types.Content(
            role="user" if msg.role == "user" else "model",
            parts=[genai_types.Part.from_text(text=msg.content)],
        ))

    # Add the new user message
    contents.append(genai_types.Content(
        role="user",
        parts=[genai_types.Part.from_text(text=req.user_message)],
    ))

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=genai_types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.8,
                max_output_tokens=2048,
            ),
        )

        reply = response.text or ""

        # Extract script block if present
        script = None
        if "```script" in reply:
            parts = reply.split("```script")
            if len(parts) > 1:
                script_block = parts[1].split("```")[0].strip()
                script = script_block

        return {
            "data": {
                "reply": reply,
                "script": script,
            },
            "success": True,
            "message": "ok",
        }

    except Exception as e:
        logger.error("Chat error: %s", e, exc_info=True)
        return {
            "data": {
                "reply": f"Sorry, I hit a snag: {str(e)[:100]}. Try again?",
                "script": None,
            },
            "success": False,
            "message": str(e),
        }

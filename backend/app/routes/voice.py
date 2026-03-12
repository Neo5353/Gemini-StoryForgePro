"""Voice Chat — Gemini Live API for real-time voice interaction.

User speaks → audio sent via WebSocket → Gemini Live API processes →
AI responds with text (and optionally audio) → sent back to user.
"""

import asyncio
import base64
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types as genai_types
from app.config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter()

VOICE_SYSTEM_PROMPT = """You are a creative screenwriting partner for StoryForge Pro, an AI visual story studio that turns scripts into comics, manga, storyboards, and cinematic trailers.

You're having a VOICE CONVERSATION with the user about their story idea. Be natural, conversational, and enthusiastic.

## How to behave:
1. When the user shares a vague idea, ask 2-3 SHORT clarifying questions (genre, tone, characters, setting)
2. Keep responses SHORT and conversational — this is voice, not text. 2-3 sentences max per turn.
3. Be enthusiastic and creative, suggest twists and details
4. When you have enough detail, tell the user you'll prepare a script and summarize what you've discussed
5. Match the user's energy — casual or serious

## Rules:
- Keep responses brief — this is a voice conversation, not an essay
- Be warm, friendly, and creative
- Ask one question at a time
- When the story is developed enough, say something like "Great! I have everything I need. Let me prepare your script."
"""


@router.websocket("/live")
async def voice_live(ws: WebSocket):
    """WebSocket endpoint for Gemini Live API voice interaction.
    
    Protocol:
    - Client sends: {"type": "audio", "data": "<base64 PCM 16-bit 16kHz mono>"}
    - Client sends: {"type": "text", "data": "typed message"}  
    - Client sends: {"type": "end"} to close
    - Server sends: {"type": "audio", "data": "<base64 PCM 24kHz mono>"}
    - Server sends: {"type": "text", "data": "transcript"}
    - Server sends: {"type": "turn_complete"}
    """
    await ws.accept()
    logger.info("Voice Live session started")

    try:
        # Create Gemini client
        client = genai.Client(
            vertexai=settings.use_vertexai,
            project=settings.google_cloud_project if settings.use_vertexai else None,
            location="us-central1" if settings.use_vertexai else None,
        )

        config = genai_types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=genai_types.Content(
                parts=[genai_types.Part.from_text(text=VOICE_SYSTEM_PROMPT)]
            ),
            speech_config=genai_types.SpeechConfig(
                voice_config=genai_types.VoiceConfig(
                    prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                        voice_name="Kore"
                    )
                )
            ),
        )

        async with client.aio.live.connect(
            model="gemini-2.5-flash-preview-native-audio",
            config=config,
        ) as session:
            logger.info("Gemini Live session connected")

            # Task to receive from Gemini and forward to client
            async def receive_from_gemini():
                try:
                    while True:
                        async for response in session.receive():
                            if response.server_content:
                                sc = response.server_content
                                # Check for audio parts
                                if sc.model_turn and sc.model_turn.parts:
                                    for part in sc.model_turn.parts:
                                        if part.inline_data and part.inline_data.data:
                                            audio_b64 = base64.b64encode(part.inline_data.data).decode('utf-8')
                                            await ws.send_json({
                                                "type": "audio",
                                                "data": audio_b64,
                                                "mime_type": part.inline_data.mime_type or "audio/pcm;rate=24000",
                                            })
                                        elif part.text:
                                            await ws.send_json({
                                                "type": "text",
                                                "data": part.text,
                                            })

                                if sc.turn_complete:
                                    await ws.send_json({"type": "turn_complete"})
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error("Gemini receive error: %s", e)
                    try:
                        await ws.send_json({"type": "error", "data": str(e)})
                    except:
                        pass

            # Start receiving from Gemini in background
            gemini_task = asyncio.create_task(receive_from_gemini())

            try:
                # Receive from client and forward to Gemini
                while True:
                    raw = await ws.receive_text()
                    msg = json.loads(raw)

                    if msg["type"] == "audio":
                        # Decode base64 audio and send to Gemini
                        audio_bytes = base64.b64decode(msg["data"])
                        await session.send_realtime_input(
                            audio=genai_types.Blob(
                                data=audio_bytes,
                                mime_type="audio/pcm;rate=16000",
                            )
                        )

                    elif msg["type"] == "text":
                        # Send text message to Gemini
                        await session.send_client_content(
                            turns=genai_types.Content(
                                role="user",
                                parts=[genai_types.Part.from_text(text=msg["data"])],
                            ),
                            turn_complete=True,
                        )

                    elif msg["type"] == "end":
                        break

            finally:
                gemini_task.cancel()
                try:
                    await gemini_task
                except asyncio.CancelledError:
                    pass

    except WebSocketDisconnect:
        logger.info("Voice Live session disconnected")
    except Exception as e:
        logger.error("Voice Live error: %s", e, exc_info=True)
        try:
            await ws.send_json({"type": "error", "data": str(e)})
        except:
            pass
    finally:
        logger.info("Voice Live session ended")

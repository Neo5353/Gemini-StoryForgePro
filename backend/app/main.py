"""StoryForge Pro — AI Visual Story Studio Backend.

The command center. Routes come in, art goes out.
"""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes import projects, generate, export, directors, chat, voice
from app.services.ws_manager import ConnectionManager

# Load environment variables
load_dotenv()

manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load director styles and initialize services on startup."""
    styles_path = Path(__file__).parent / "config" / "director_styles.json"
    with open(styles_path) as f:
        app.state.director_styles = json.load(f)["directors"]

    # Initialize MongoDB indexes
    from app.services.firestore import ensure_indexes
    await ensure_indexes()

    # Initialize ADK agent hierarchy
    from app.agents.adk_agents import root_agent, ADK_AVAILABLE
    app.state.adk_agent = root_agent
    adk_status = "✅ loaded" if root_agent else ("⚠️ ADK not installed" if not ADK_AVAILABLE else "⚠️ build failed")

    print("🎬 StoryForge Pro backend starting...")
    print(f"   Loaded {len(app.state.director_styles)} director styles")
    print(f"   Directors: {', '.join(app.state.director_styles.keys())}")
    print(f"   ADK Agent: {adk_status}")
    yield
    print("🎬 StoryForge Pro backend shutting down...")


app = FastAPI(
    title="StoryForge Pro",
    description="AI Visual Story Studio — From script to screen",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Lock down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(generate.router, prefix="/api/generate", tags=["generate"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(directors.router, prefix="/api/directors", tags=["directors"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(voice.router, prefix="/api/voice", tags=["voice"])

# Static file serving for locally-generated assets
_assets_dir = Path(__file__).parent.parent / "assets"
_assets_dir.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "storyforge-pro",
        "version": "0.1.0",
    }


@app.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    """WebSocket for real-time generation progress updates.

    Connect to /ws/{project_id} to receive:
    - progress: Stage updates with percentages
    - complete: Generation finished
    - error: Something went wrong

    Send:
    - {"action": "cancel"}: Cancel ongoing generation
    """
    await manager.connect(websocket, project_id)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.handle_client_message(project_id, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket, project_id)

"""WebSocket connection manager for real-time progress updates."""

import json
from typing import Dict, List
from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections per project for progress streaming."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_id: str):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        self.active_connections[project_id].append(websocket)

    def disconnect(self, websocket: WebSocket, project_id: str):
        if project_id in self.active_connections:
            self.active_connections[project_id].remove(websocket)
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]

    async def send_progress(self, project_id: str, data: dict):
        """Send progress update to all connected clients for a project."""
        if project_id in self.active_connections:
            message = json.dumps(data)
            for connection in self.active_connections[project_id]:
                try:
                    await connection.send_text(message)
                except Exception:
                    pass  # Connection may have dropped

    async def handle_client_message(self, project_id: str, data: str):
        """Handle control messages from client (pause, cancel, etc.)."""
        try:
            msg = json.loads(data)
            action = msg.get("action")
            if action == "cancel":
                # TODO: Cancel ongoing generation
                await self.send_progress(project_id, {
                    "type": "status",
                    "status": "cancelled",
                })
        except json.JSONDecodeError:
            pass

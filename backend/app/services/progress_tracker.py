"""Progress Tracker — WALL-E keeps everyone informed.

Tracks generation progress for each project and pushes updates
via WebSocket to connected clients.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Coroutine, Dict, Optional, Any

logger = logging.getLogger("storyforge.progress")


class GenerationPhase(str, Enum):
    SCRIPT_PARSING = "script_parsing"
    CHARACTER_GEN = "character_gen"
    KEY_FRAMES = "key_frames"
    VIDEO_GEN = "video_gen"
    ASSEMBLY = "assembly"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Approximate weight of each phase in the total pipeline (sums to 100)
PHASE_WEIGHTS = {
    GenerationPhase.SCRIPT_PARSING: 5,
    GenerationPhase.CHARACTER_GEN: 10,
    GenerationPhase.KEY_FRAMES: 15,
    GenerationPhase.VIDEO_GEN: 50,
    GenerationPhase.ASSEMBLY: 15,
    GenerationPhase.COMPLETE: 5,
}


@dataclass
class SceneProgress:
    """Progress for a single scene."""
    scene_id: str
    phase: GenerationPhase = GenerationPhase.SCRIPT_PARSING
    progress_pct: float = 0.0
    message: str = ""
    error: Optional[str] = None
    started_at: float = field(default_factory=time.monotonic)
    completed_at: Optional[float] = None


@dataclass
class GenerationStatus:
    """Overall generation status for a project."""
    project_id: str
    phase: GenerationPhase = GenerationPhase.SCRIPT_PARSING
    overall_progress_pct: float = 0.0
    message: str = "Initializing..."
    scenes: Dict[str, SceneProgress] = field(default_factory=dict)
    started_at: float = field(default_factory=time.monotonic)
    completed_at: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize for WebSocket transmission."""
        return {
            "type": "progress",
            "project_id": self.project_id,
            "phase": self.phase.value,
            "overall_progress_pct": round(self.overall_progress_pct, 1),
            "message": self.message,
            "elapsed_seconds": round(time.monotonic() - self.started_at, 1),
            "scenes": {
                sid: {
                    "phase": sp.phase.value,
                    "progress_pct": round(sp.progress_pct, 1),
                    "message": sp.message,
                    "error": sp.error,
                }
                for sid, sp in self.scenes.items()
            },
            "error": self.error,
        }


# Type alias for the WebSocket push callback
ProgressCallback = Callable[[str, dict], Coroutine[Any, Any, None]]


class ProgressTracker:
    """Tracks and broadcasts generation progress.

    WALL-E always lets you know how things are going — one beep at a time.
    """

    def __init__(self, ws_callback: Optional[ProgressCallback] = None):
        """
        Args:
            ws_callback: async fn(project_id, data_dict) that pushes to WebSocket.
                         Typically ConnectionManager.send_progress.
        """
        self._statuses: Dict[str, GenerationStatus] = {}
        self._ws_callback = ws_callback
        self._lock = asyncio.Lock()

    def _ensure_status(self, project_id: str) -> GenerationStatus:
        if project_id not in self._statuses:
            self._statuses[project_id] = GenerationStatus(project_id=project_id)
        return self._statuses[project_id]

    def _compute_overall(self, status: GenerationStatus) -> float:
        """Compute weighted overall progress across phases and scenes."""
        phase = status.phase
        # Base progress from completed phases
        phase_order = list(PHASE_WEIGHTS.keys())
        base = 0.0
        for p in phase_order:
            if p == phase:
                break
            base += PHASE_WEIGHTS.get(p, 0)

        # Add intra-phase progress
        current_weight = PHASE_WEIGHTS.get(phase, 0)
        if status.scenes and phase in (
            GenerationPhase.KEY_FRAMES,
            GenerationPhase.VIDEO_GEN,
        ):
            # Average scene progress within this phase
            scene_progresses = [
                s.progress_pct
                for s in status.scenes.values()
                if s.phase == phase
            ]
            if scene_progresses:
                avg = sum(scene_progresses) / len(scene_progresses)
                base += current_weight * (avg / 100.0)
        elif phase == GenerationPhase.ASSEMBLY:
            # Assembly doesn't have per-scene tracking, use phase progress directly
            # (will be set via scene_id=None updates)
            base += current_weight * (status.overall_progress_pct - base) / max(
                current_weight, 1
            )

        return min(base, 100.0)

    async def update(
        self,
        project_id: str,
        phase: str,
        scene_id: Optional[str] = None,
        progress_pct: float = 0.0,
        message: str = "",
    ) -> None:
        """Update progress for a project/scene.

        Args:
            project_id: The project being generated.
            phase: Current phase (from GenerationPhase values).
            scene_id: Specific scene ID, or None for project-level updates.
            progress_pct: Progress within this phase (0-100).
            message: Human-readable status message.
        """
        async with self._lock:
            status = self._ensure_status(project_id)

            try:
                gen_phase = GenerationPhase(phase)
            except ValueError:
                gen_phase = GenerationPhase.SCRIPT_PARSING

            status.phase = gen_phase
            status.message = message

            if scene_id:
                if scene_id not in status.scenes:
                    status.scenes[scene_id] = SceneProgress(scene_id=scene_id)
                scene = status.scenes[scene_id]
                scene.phase = gen_phase
                scene.progress_pct = progress_pct
                scene.message = message
                if progress_pct >= 100.0:
                    scene.completed_at = time.monotonic()

            # Recompute overall
            status.overall_progress_pct = self._compute_overall(status)

            if gen_phase == GenerationPhase.COMPLETE:
                status.overall_progress_pct = 100.0
                status.completed_at = time.monotonic()
            elif gen_phase == GenerationPhase.FAILED:
                status.error = message

        # Push to WebSocket
        data = status.to_dict()
        logger.info(
            "Progress [%s] %s: %.1f%% — %s",
            project_id, phase, status.overall_progress_pct, message,
        )
        if self._ws_callback:
            try:
                await self._ws_callback(project_id, data)
            except Exception as e:
                logger.warning("Failed to push progress via WS: %s", e)

    async def get_status(self, project_id: str) -> Optional[GenerationStatus]:
        """Get current generation status for a project."""
        return self._statuses.get(project_id)

    async def mark_failed(
        self, project_id: str, error: str, scene_id: Optional[str] = None
    ) -> None:
        """Mark a project or scene as failed."""
        await self.update(
            project_id,
            GenerationPhase.FAILED.value,
            scene_id=scene_id,
            progress_pct=0,
            message=error,
        )

    async def mark_complete(self, project_id: str) -> None:
        """Mark generation as complete."""
        await self.update(
            project_id,
            GenerationPhase.COMPLETE.value,
            progress_pct=100,
            message="Trailer generation complete!",
        )

    def cleanup(self, project_id: str) -> None:
        """Remove tracking data for a completed project."""
        self._statuses.pop(project_id, None)

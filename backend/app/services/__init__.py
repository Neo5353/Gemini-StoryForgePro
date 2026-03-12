# Services package — WALL-E's video pipeline + HAL's AI layer

from app.services.veo_service import VeoService, VideoResult, VeoAPIError, VeoTimeoutError
from app.services.ffmpeg_service import FFmpegService, SceneClip, TransitionType, FFmpegError
from app.services.trailer_pipeline import TrailerPipeline, TrailerResult, SceneSpec, SceneResult
from app.services.progress_tracker import ProgressTracker, GenerationStatus, GenerationPhase
from app.services.ws_manager import ConnectionManager
from app.services.style_engine import StyleEngine, CameraDirection, AudioDirection
from app.services.image_gen import ImageGenService, ImageResult
from app.services.interleaved_gen import InterleavedGenService, ComicPage, MangaPage, StoryboardPage
from app.services.content_sanitizer import sanitize_scenes, sanitize_scene_text

__all__ = [
    # Veo
    "VeoService", "VideoResult", "VeoAPIError", "VeoTimeoutError",
    # FFmpeg
    "FFmpegService", "SceneClip", "TransitionType", "FFmpegError",
    # Pipeline
    "TrailerPipeline", "TrailerResult", "SceneSpec", "SceneResult",
    # Progress
    "ProgressTracker", "GenerationStatus", "GenerationPhase",
    # WebSocket
    "ConnectionManager",
    # HAL — Style Engine
    "StyleEngine", "CameraDirection", "AudioDirection",
    # HAL — Image Generation
    "ImageGenService", "ImageResult",
    # HAL — Interleaved Generation
    "InterleavedGenService", "ComicPage", "MangaPage", "StoryboardPage",
    # Content Sanitizer
    "sanitize_scenes", "sanitize_scene_text",
]

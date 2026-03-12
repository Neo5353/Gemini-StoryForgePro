"""Application settings — loaded from environment variables."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """StoryForge Pro configuration. All the knobs in one place."""

    # Google Cloud
    google_cloud_project: str = "storyforge001"
    # Use "global" endpoint for better availability — routes to region with
    # most capacity, reducing 429 errors vs pinning to us-central1.
    google_cloud_location: str = "global"
    google_application_credentials: Optional[str] = None
    google_genai_use_vertexai: bool = True

    # Firestore
    firestore_database: str = "(default)"

    # Cloud Storage
    gcs_bucket: str = "storyforge-pro-assets"

    # Frontend
    frontend_url: str = "http://localhost:5173"

    # Gemini models
    gemini_model: str = "gemini-2.5-flash"
    gemini_flash_model: str = "gemini-2.5-flash"

    # Native image generation model (interleaved text+image output)
    # Uses Gemini's native image generation via generate_content with
    # response_modalities=["TEXT", "IMAGE"] — NOT the old Imagen API.
    # Options on Vertex AI (storyforge001):
    #   "gemini-2.5-flash-image"      — Proven, interleaved text+image output ✅
    #   "gemini-3-pro-image-preview"  — Pro tier, highest quality (needs preview access)
    imagen_model: str = "gemini-2.5-flash-image"

    # Veo
    veo_model: str = "veo-3.1-generate-001"

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "storyforge"

    # Local dev mode
    storyforge_local: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

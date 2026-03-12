"""Gemini client singleton.

One client to rule them all. Initialized once, used everywhere.
"""

from google import genai
from google.genai import types
from app.config.settings import settings

# Initialize the client — works for both Vertex AI and API key modes
_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Get or create the Gemini client singleton."""
    global _client
    if _client is None:
        if settings.google_genai_use_vertexai:
            _client = genai.Client(
                vertexai=True,
                project=settings.google_cloud_project,
                location=settings.google_cloud_location,
            )
        else:
            _client = genai.Client()
    return _client

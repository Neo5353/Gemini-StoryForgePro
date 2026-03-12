# ADK Agents package — The Robot Crew

from app.agents.hal import ScriptAnalyzer
from app.agents.editor import EditAgent
from app.agents.orchestrator import StoryForgeOrchestrator

# ADK agent hierarchy (requires google-adk)
try:
    from app.agents.adk_agents import root_agent, build_agents, ADK_AVAILABLE
except ImportError:
    root_agent = None
    build_agents = None
    ADK_AVAILABLE = False

__all__ = [
    "ScriptAnalyzer",
    "EditAgent",
    "StoryForgeOrchestrator",
    "root_agent",
    "build_agents",
    "ADK_AVAILABLE",
]

"""Entry point for the ADK dev UI (`adk web`).

`adk web adk_agents` discovers this folder and serves `root_agent` in a browser chat.
"""
import os
import sys
from pathlib import Path

# Make the backend package root ("backend/") importable so `from src...` works
# regardless of where adk launches the loader from.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

from src.settings import settings  # noqa: E402

# ADK/google-genai read Vertex config from os.environ; bridge it in from Settings/.env.
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE" if settings.google_genai_use_vertexai else "FALSE")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.google_cloud_project)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", settings.google_cloud_location)

from src.agents.roi_gatekeeper import build_dev_roi_agent  # noqa: E402

# `adk web` looks for a module-level `root_agent`.
root_agent = build_dev_roi_agent()

"""ADK app definition: exposes the orchestrator as the root agent.

The ADK agent loader imports this module for the text chat endpoints
(``/run``, ``/run_sse``) and the dev UI; run the server from ``backend/`` so
``src`` is importable.

Uses the text model, not the live one: this app is served through
``generateContent``, which live (audio-native) models reject. The voice
WebSocket (``/ws/voice``) builds its own orchestrator on the live model.
"""

from src.agents.orchestrator import create_voice_orchestrator
from src.settings import settings

root_agent = create_voice_orchestrator(model_name=settings.model_name)

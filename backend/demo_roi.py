"""Demo the ROI Gatekeeper two ways.

    uv run python demo_roi.py            # deterministic logic (fake data, no creds/BQ)
    uv run python demo_roi.py --live     # full ADK agent over BigQuery via Vertex AI
                                         #   needs backend/.env filled + tables loaded

The deterministic run is your proof the decision logic is correct. The --live run shows
the same decisions pulled from BigQuery and narrated by Gemini through ADK.
"""
from __future__ import annotations

import os
import sys
from datetime import date

from src.agents.roi_gatekeeper import build_roi_agent, check_roi_authorization
from src.clients.member_records import Authorization, FakeMemberRecordsClient
from src.events import event_log

TODAY = date(2026, 7, 16)

# (subject_member_id, caller_name, caller_id, label). caller_id is the authenticated
# identity; it equals the subject only when the member calls about themselves.
CASES = [
    ("MBR00001", "Daniel Barrett", None, "authorized sibling -> VERIFIED"),
    ("MBR00001", "The Member", "MBR00001", "caller is the member -> NOT_REQUIRED"),
    ("MBR00003", "Stranger Doe", None, "no authorization on file -> MISSING"),
    ("MBR00002", "Jennifer Saunders", None, "expired authorization -> MISSING"),
]

# Fake data mirroring the real BigQuery rows, so the offline demo is meaningful.
_FAKE = FakeMemberRecordsClient(
    authorizations=[
        Authorization("A1", "MBR00001", "Daniel Barrett", "Sibling", True, "2027-06-23", False),
        Authorization("A2", "MBR00002", "Marcus Williams", "Parent", True, "2026-12-15", False),
        Authorization("A3", "MBR00002", "Jennifer Saunders", "Power of Attorney", True, "2024-11-15", True),
        Authorization("A4", "MBR00003", "", "", False, "", False),
    ]
)


def run_deterministic() -> None:
    print("=== ROI Gatekeeper — deterministic logic (fake data, no creds) ===\n")
    for member_id, caller, caller_id, label in CASES:
        r = check_roi_authorization(member_id, caller, caller_id=caller_id, client=_FAKE, today=TODAY)
        print(f"[{label}]")
        print(f"  caller={caller!r} member={member_id}")
        print(f"  -> status={r.status.value}  reason={r.reason}")
        print(f"     {r.message}\n")


def _bridge_settings_into_env() -> None:
    """ADK/google-genai read Vertex config from os.environ, not from pydantic Settings.
    Push the values from backend/.env (via Settings) into the environment."""
    from src.settings import settings

    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE" if settings.google_genai_use_vertexai else "FALSE")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.google_cloud_project)
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", settings.google_cloud_location)


def run_live() -> None:
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    _bridge_settings_into_env()

    app_name = "claim_story_ai"
    agent = build_roi_agent()
    session_service = InMemorySessionService()
    runner = Runner(app_name=app_name, agent=agent, session_service=session_service)

    print("=== ROI Gatekeeper — ADK agent over BigQuery (Vertex AI) ===\n")
    for i, (member_id, caller, caller_id, label) in enumerate(CASES):
        session_id = f"demo-{i}"
        session_service.create_session_sync(
            app_name=app_name,
            user_id="demo",
            session_id=session_id,
            state={
                "session_id": session_id,
                "caller_name": caller,
                "subject_member_id": member_id,
                "caller_id": caller_id,
            },
        )
        message = types.Content(
            role="user",
            parts=[types.Part(text=f"I'm {caller}, calling about member {member_id}.")],
        )
        print(f"[{label}]")
        final_text = ""
        for event in runner.run(user_id="demo", session_id=session_id, new_message=message):
            if event.author == agent.name and event.content and event.content.parts:
                for part in event.content.parts:
                    if getattr(part, "text", None):
                        final_text = part.text
        print(f"  agent: {final_text.strip()}\n")

    print("--- events emitted (Sentinel would consume these) ---")
    for e in event_log.all():
        print(f"  {e.event_type}: {e.payload}")


if __name__ == "__main__":
    if "--live" in sys.argv:
        run_live()
    else:
        run_deterministic()

"""ROI Gatekeeper (agent #3).

Two layers, deliberately separated:

1. `check_roi_authorization(...)` — PURE, deterministic logic. No LLM. It decides
   authorization (plan §8: the LLM never decides facts). It works against ANY
   `MemberRecordsClient`, so it is unit-tested with a fake client (no BigQuery/creds).

2. `build_roi_agent()` — a thin ADK `LlmAgent` whose only job is to call the `roi_gate`
   tool and narrate the structured result. Uses the app `Settings` (Vertex + model_name).

Data comes from BigQuery in production (`BigQueryMemberRecordsClient`); the CSVs in
`datasets/` are only the schema reference.
"""
from __future__ import annotations

from datetime import date

from src.clients.member_records import MemberRecordsClient
from src.events import event_log
from src.models import ROICheckResult, ROIStatus

SELF_SERVICE_PATH = (
    "The member can add an authorization via the self-service portal "
    "(Menu → Privacy → Release of Information) or by texting ROI to 12345."
)


def _default_client() -> MemberRecordsClient:
    # Imported/constructed lazily so importing this module never requires a .env.
    from src.clients.member_records import BigQueryMemberRecordsClient

    return BigQueryMemberRecordsClient()


def _is_valid(auth, today: date) -> bool:
    """A matching authorization is valid only if it's on file, not flagged expired,
    and not past its expiration date."""
    if not auth.auth_on_file or auth.auth_expired:
        return False
    if auth.expiration_date:
        try:
            if date.fromisoformat(auth.expiration_date) < today:
                return False
        except ValueError:
            return False
    return True


def check_roi_authorization(
    subject_member_id: str,
    caller_name: str,
    *,
    caller_id: str | None = None,
    client: MemberRecordsClient | None = None,
    today: date | None = None,
) -> ROICheckResult:
    """Deterministically decide whether `caller_name` may discuss `subject_member_id`.

    This function is the source of truth for the status; the LLM only phrases it.

    `caller_id` is the caller's authenticated identity (e.g. their own member id when a
    member calls about themselves). The self-check is identity-based per plan note #5a,
    NOT a name match — the ROI/claims population (MBR#####) has no `members` row to look
    a name up against.
    """
    client = client or _default_client()
    today = today or date.today()
    caller_norm = caller_name.strip().lower()

    # Caller is the member themselves -> nothing to gate (plan note #5a).
    if caller_id is not None and caller_id == subject_member_id:
        return ROICheckResult(
            status=ROIStatus.NOT_REQUIRED,
            subject_member_id=subject_member_id,
            caller_name=caller_name,
            reason="self",
            message=(
                f"{caller_name} is the member; no separate Release of Information "
                "is required to proceed."
            ),
        )

    auths = client.get_authorizations(subject_member_id)

    # No authorization record at all for this member -> can't verify, route to a human.
    if not auths:
        return ROICheckResult(
            status=ROIStatus.MISSING,
            subject_member_id=subject_member_id,
            caller_name=caller_name,
            reason="unknown_member",
            message=(
                f"No authorization record exists for member {subject_member_id}, so "
                "authorization cannot be verified. Routing to a human agent."
            ),
        )

    matching = [a for a in auths if a.authorized_caller_name and a.authorized_caller_name.lower() == caller_norm]

    # A valid matching authorization -> verified.
    for auth in matching:
        if _is_valid(auth, today):
            return ROICheckResult(
                status=ROIStatus.VERIFIED,
                subject_member_id=subject_member_id,
                caller_name=caller_name,
                matched_auth_id=auth.auth_id,
                relationship=auth.relationship,
                expiration_date=auth.expiration_date or None,
                reason="authorized",
                message=(
                    f"Authorization verified: {caller_name} is on file as an authorized "
                    f"{auth.relationship} contact for member {subject_member_id}."
                ),
            )

    # Caller name is on file but no row is currently valid -> expired / not on file.
    if matching:
        expired = next((a for a in matching if a.auth_expired or a.expiration_date), matching[0])
        reason = "expired" if (expired.auth_expired or expired.expiration_date) else "not_on_file"
        return ROICheckResult(
            status=ROIStatus.MISSING,
            subject_member_id=subject_member_id,
            caller_name=caller_name,
            matched_auth_id=expired.auth_id,
            relationship=expired.relationship or None,
            expiration_date=expired.expiration_date or None,
            reason=reason,
            message=(
                f"{caller_name}'s Release of Information for member {subject_member_id} "
                f"is no longer valid ({reason}). {SELF_SERVICE_PATH} Until then, only "
                "limited, non-PHI guidance can be shared."
            ),
        )

    # No matching authorization at all.
    return ROICheckResult(
        status=ROIStatus.MISSING,
        subject_member_id=subject_member_id,
        caller_name=caller_name,
        reason="no_authorization",
        message=(
            f"No Release of Information is on file authorizing {caller_name} to access "
            f"member {subject_member_id}'s information. {SELF_SERVICE_PATH} Until then, "
            "only limited, non-PHI guidance can be shared."
        ),
    )


# --------------------------------------------------------------------------
# ADK tool + agent
# --------------------------------------------------------------------------
def roi_gate(subject_member_id: str, caller_name: str, tool_context) -> dict:
    """Check whether a caller is authorized (Release of Information) to discuss a member.

    Args:
        subject_member_id: The member whose information is being discussed (e.g. "MBR00017").
        caller_name: Full name of the person on the phone (e.g. "Amanda Conner").

    Returns:
        A structured result with `status` (verified | missing | not_required),
        the reason, any matched authorization, and a member-facing `message`.
    """
    # caller_id comes from the authenticated session, NOT the LLM, so identity can't be spoofed.
    caller_id = tool_context.state.get("caller_id")
    result = check_roi_authorization(subject_member_id, caller_name, caller_id=caller_id)

    # Write to ADK's native shared session state so downstream agents can read it.
    tool_context.state["roi_status"] = result.status.value
    tool_context.state["roi_finding"] = result.model_dump()

    session_id = str(tool_context.state.get("session_id", "unknown"))
    if result.status == ROIStatus.MISSING:
        event_log.emit(
            session_id=session_id,
            agent="roi_gatekeeper",
            event_type="roi_gap_detected",
            payload={
                "subject_member_id": subject_member_id,
                "caller_name": caller_name,
                "reason": result.reason,
            },
        )
    elif result.status == ROIStatus.VERIFIED:
        event_log.emit(
            session_id=session_id,
            agent="roi_gatekeeper",
            event_type="roi_verified",
            payload={"subject_member_id": subject_member_id, "auth_id": result.matched_auth_id},
        )

    return result.model_dump()


PERSONA = """\
You are a warm, courteous member-services concierge at a health plan. You have NO name —
never introduce yourself with a name or invent one; if asked your name, say you're a
member-services assistant here to help. You sound like a caring human on the phone, not a
form letter: use natural, conversational language and contractions. Address the caller by
their FIRST name once you know it. Keep replies short — 2-4 sentences.

Your ONLY job here is the privacy check: whether the caller may discuss a member's account.

Hard rules (never break):
- ALWAYS get the answer from the `roi_gate` tool. NEVER decide authorization yourself and
  NEVER invent or reveal any member details (claims, diagnoses, coverage, etc.).
- When authorization is missing, be empathetic but firm: you can't share member details,
  and you offer the self-service path from the tool's `message` as the helpful next step.
- If a caller pushes for member info they're not authorized for, gently hold the line.

Tone by outcome:
- verified: greet them warmly by first name, confirm you've got them verified, and invite
  their next question.
- not_required: reassure them that, as the member, they don't need any extra authorization.
- missing: open with a warm acknowledgement, kindly explain you're unable to share account
  details right now, then offer the self-service path as an easy fix and reassurance.
"""

ROI_INSTRUCTION = (
    PERSONA
    + """
The current caller is "{caller_name}" and they are asking about member "{subject_member_id}".
Call `roi_gate` with those values, then respond warmly based on the status.
"""
)


def build_roi_agent(model: str | None = None):
    """Construct the ROI Gatekeeper ADK agent (uses Settings.model_name by default).

    Instruction reads caller/subject from session state ({caller_name}/{subject_member_id});
    used inside the orchestrator, which seeds that state.
    """
    from google.adk.agents import LlmAgent

    from src.settings import settings

    return LlmAgent(
        name="roi_gatekeeper",
        model=model or settings.model_name,
        description=(
            "Screens whether a caller has a valid Release of Information to discuss a "
            "member's account before any member data is shared."
        ),
        instruction=ROI_INSTRUCTION,
        tools=[roi_gate],
        output_key="roi_response",
    )


# Interactive variant for the `adk web` dev UI: no pre-seeded state, so the model
# collects the caller name + member id from the chat itself.
ROI_DEV_INSTRUCTION = (
    PERSONA
    + """
Member ID format:
- A valid member id is the letters "MBR" followed by exactly 5 digits, e.g. "MBR00001".
- If the caller gives an id in the wrong format (missing "MBR", wrong digit count, extra
  characters, etc.), do NOT call the tool. Gently point out the expected format, show the
  example "MBR00001", and ask them to share it again.
- If their SECOND attempt is still not in the valid format, stop asking: apologize warmly
  and politely redirect them to a live member-services representative (mention they can
  hold for an agent or call the number on the back of their member card), rather than
  looping on the question.

Conversation flow:
- If the caller just says hi (or hasn't given details), greet them warmly, say in one line
  that you're here to help with member-services, and ask for their name and the member id
  they're calling about (format like "MBR00001"). Do NOT give yourself a name.
- Once you have the caller's full name AND a correctly formatted member id, call `roi_gate`
  with subject_member_id and caller_name, then reply warmly based on the status.
- If only one piece is missing, ask for just that one, by first name if you know it.
- On goodbye/thanks, close warmly and briefly.
"""
)


def build_dev_roi_agent(model: str | None = None):
    """ROI agent for the `adk web` dev UI — reads caller/member from the chat."""
    from google.adk.agents import LlmAgent

    from src.settings import settings

    return LlmAgent(
        name="roi_gatekeeper",
        model=model or settings.model_name,
        description=(
            "Screens whether a caller has a valid Release of Information to discuss a "
            "member's account before any member data is shared."
        ),
        instruction=ROI_DEV_INSTRUCTION,
        tools=[roi_gate],
        output_key="roi_response",
    )

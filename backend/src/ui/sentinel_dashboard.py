from __future__ import annotations

from ..models import SentinelSnapshot


def render_sentinel_dashboard(snapshot: SentinelSnapshot) -> None:
    """Render inside the team's Streamlit app without making Streamlit mandatory."""

    try:
        import streamlit as st
    except ImportError as exc:
        raise RuntimeError(
            "Install Streamlit in the UI environment before rendering the dashboard."
        ) from exc

    st.subheader("Sentinel operations monitor")
    metrics = snapshot.metrics
    columns = st.columns(4)
    columns[0].metric("Active alerts", snapshot.active_alert_count)
    columns[1].metric(
        "Average handle time",
        _minutes(metrics.average_handle_time_minutes),
        _percent_delta(metrics.aht_change_rate),
        delta_color="inverse",
    )
    columns[2].metric(
        "First-call resolution",
        _rate(metrics.first_contact_resolution_rate),
        _percent_delta(metrics.fcr_change_rate),
    )
    columns[3].metric(
        "Repeat contacts",
        _rate(metrics.repeat_contact_rate),
        _percent_delta(metrics.repeat_contact_change_rate),
        delta_color="inverse",
    )

    second_row = st.columns(4)
    second_row[0].metric("Escalation rate", _rate(metrics.escalation_rate))
    second_row[1].metric("ROI-gap rate", _rate(metrics.roi_gap_rate))
    second_row[2].metric(
        "At-risk claims identified", metrics.at_risk_claims_identified
    )
    second_row[3].metric(
        "Corrective interventions recorded",
        metrics.corrective_interventions_recorded,
    )

    st.caption(
        f"Baseline assumption ({metrics.baseline.data_label}): "
        f"{metrics.baseline.source_note}"
    )
    rows = [
        {
            "severity": alert.severity.value.upper(),
            "type": alert.alert_type.value,
            "title": alert.title,
            "description": alert.description,
            "recommended_action": alert.recommended_action,
            "evidence_event_ids": ", ".join(
                str(event_id) for event_id in alert.evidence_event_ids
            ),
            "occurrences": alert.occurrences,
            "last_seen": alert.last_seen,
        }
        for alert in snapshot.alerts
    ]
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No active alerts. Run the deterministic golden path or a live session.")


def _minutes(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1f} min"


def _rate(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1%}"


def _percent_delta(value: float | None) -> str | None:
    return None if value is None else f"{value:+.1%}"

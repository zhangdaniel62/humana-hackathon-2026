from __future__ import annotations

from models import SentinelSnapshot


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

    st.caption(f"Baseline: {metrics.baseline.source_note}")
    rows = [
        {
            "severity": alert.severity.value.upper(),
            "type": alert.alert_type.value,
            "title": alert.title,
            "description": alert.description,
            "recommended_action": alert.recommended_action,
            "occurrences": alert.occurrences,
            "last_seen": alert.last_seen,
        }
        for alert in snapshot.alerts
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _minutes(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1f} min"


def _rate(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1%}"


def _percent_delta(value: float | None) -> str | None:
    return None if value is None else f"{value:+.1%}"

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS call_sessions (
    session_id TEXT PRIMARY KEY,
    started_at INTEGER NOT NULL,
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds > 0),
    member_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    handling_mode TEXT NOT NULL
        CHECK (handling_mode IN ('automated', 'manual_review')),
    rep_user_id INTEGER REFERENCES users(id) ON DELETE RESTRICT,
    resolved INTEGER NOT NULL CHECK (resolved IN (0, 1)),
    CHECK (
        (handling_mode = 'automated' AND rep_user_id IS NULL)
        OR
        (handling_mode = 'manual_review' AND rep_user_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS call_sessions_started_at_idx
    ON call_sessions(started_at);
CREATE INDEX IF NOT EXISTS call_sessions_contact_window_idx
    ON call_sessions(member_id, claim_id, started_at);

CREATE TABLE IF NOT EXISTS claim_interventions (
    claim_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    detected_at INTEGER NOT NULL,
    recommended_at INTEGER,
    recorded_at INTEGER,
    PRIMARY KEY (claim_id, rule_id),
    CHECK (recommended_at IS NULL OR recommended_at >= detected_at),
    CHECK (
        recorded_at IS NULL
        OR (recommended_at IS NOT NULL AND recorded_at >= recommended_at)
    )
);

CREATE INDEX IF NOT EXISTS claim_interventions_detected_at_idx
    ON claim_interventions(detected_at);

CREATE TABLE IF NOT EXISTS prevention_scan_runs (
    run_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL CHECK (source IN ('startup', 'manager', 'golden_path')),
    completed_at INTEGER NOT NULL,
    claims_scanned INTEGER NOT NULL CHECK (claims_scanned >= 0),
    items_created INTEGER NOT NULL CHECK (items_created >= 0),
    items_existing INTEGER NOT NULL CHECK (items_existing >= 0)
);

CREATE TABLE IF NOT EXISTS rep_work_items (
    work_item_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    title TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    risk_band TEXT NOT NULL CHECK (risk_band IN ('high', 'warning')),
    priority_score INTEGER NOT NULL CHECK (priority_score >= 0),
    status TEXT NOT NULL CHECK (
        status IN ('open', 'claimed', 'resolved', 'dismissed')
    ),
    assigned_rep_user_id INTEGER REFERENCES users(id) ON DELETE RESTRICT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    resolved_at INTEGER,
    UNIQUE (claim_id, rule_id),
    CHECK (
        (status = 'open' AND assigned_rep_user_id IS NULL)
        OR (status != 'open' AND assigned_rep_user_id IS NOT NULL)
    ),
    CHECK (
        (status IN ('open', 'claimed') AND resolved_at IS NULL)
        OR (status IN ('resolved', 'dismissed') AND resolved_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS rep_work_items_queue_idx
    ON rep_work_items(status, priority_score DESC, created_at, claim_id);
CREATE INDEX IF NOT EXISTS rep_work_items_assignee_idx
    ON rep_work_items(assigned_rep_user_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS delegation_traces (
    trace_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    work_item_id TEXT,
    specialist TEXT NOT NULL,
    started_at INTEGER NOT NULL,
    completed_at INTEGER NOT NULL,
    latency_ms REAL NOT NULL CHECK (latency_ms >= 0),
    outcome TEXT NOT NULL CHECK (outcome IN ('success', 'fallback', 'blocked')),
    error_code TEXT
);

CREATE INDEX IF NOT EXISTS delegation_traces_session_idx
    ON delegation_traces(session_id, started_at DESC);

CREATE TABLE IF NOT EXISTS agent_events (
    event_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    session_id TEXT NOT NULL,
    agent TEXT NOT NULL,
    event_type TEXT NOT NULL,
    member_id TEXT,
    claim_id TEXT,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS agent_events_replay_idx
    ON agent_events(timestamp, event_id);

CREATE TABLE IF NOT EXISTS golden_path_runs (
    idempotency_key TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed')),
    completed_at INTEGER,
    result_json TEXT
);

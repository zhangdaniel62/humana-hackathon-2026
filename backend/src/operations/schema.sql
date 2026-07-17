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

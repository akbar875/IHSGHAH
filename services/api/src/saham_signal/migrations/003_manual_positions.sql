-- Confirmed manual fills are kept apart from simulation journal outcomes.
CREATE TABLE manual_position_events (
    cursor bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mode text NOT NULL CHECK (mode IN ('research', 'paper', 'live')),
    user_id text NOT NULL CHECK (length(user_id) BETWEEN 1 AND 128),
    position_id text NOT NULL,
    idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 128),
    command jsonb NOT NULL,
    snapshot jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (mode, user_id, idempotency_key),
    CHECK (mode = current_setting('ss.mode', true)),
    CHECK (user_id = current_setting('ss.user_id', true))
);
CREATE INDEX manual_positions_latest ON manual_position_events(mode,user_id,position_id,cursor DESC);
ALTER TABLE manual_position_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE manual_position_events FORCE ROW LEVEL SECURITY;
CREATE POLICY manual_positions_scope ON manual_position_events
    USING (mode = current_setting('ss.mode', true) AND user_id = current_setting('ss.user_id', true))
    WITH CHECK (mode = current_setting('ss.mode', true) AND user_id = current_setting('ss.user_id', true));
CREATE TRIGGER manual_positions_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON manual_position_events
    FOR EACH STATEMENT EXECUTE FUNCTION reject_journal_mutation();

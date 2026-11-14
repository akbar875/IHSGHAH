-- Personal snapshots are append-only and isolated by the same account/mode RLS as journal.
CREATE TABLE personal_preferences (
    cursor bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mode text NOT NULL CHECK (mode IN ('research', 'paper', 'live')),
    user_id text NOT NULL CHECK (length(user_id) BETWEEN 1 AND 128),
    kind text NOT NULL CHECK (kind IN ('Watchlist', 'RiskSettings')),
    idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 128),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (mode, user_id, kind, idempotency_key),
    CHECK (mode = current_setting('ss.mode', true)),
    CHECK (user_id = current_setting('ss.user_id', true))
);
CREATE INDEX preferences_latest ON personal_preferences (mode, user_id, kind, cursor DESC);
ALTER TABLE personal_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE personal_preferences FORCE ROW LEVEL SECURITY;
CREATE POLICY preferences_scope ON personal_preferences
    USING (mode = current_setting('ss.mode', true)
           AND user_id = current_setting('ss.user_id', true))
    WITH CHECK (mode = current_setting('ss.mode', true)
                AND user_id = current_setting('ss.user_id', true));
CREATE TRIGGER preferences_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON personal_preferences
    FOR EACH STATEMENT EXECUTE FUNCTION reject_journal_mutation();

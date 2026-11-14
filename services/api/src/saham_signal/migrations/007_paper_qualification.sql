-- Offline receipts only. No executable plan reservations or actual fills here.
CREATE TABLE paper_qualification (
    mode text NOT NULL CHECK (mode = 'paper'),
    user_id text NOT NULL CHECK (length(user_id) BETWEEN 1 AND 128),
    content_digest text NOT NULL CHECK (length(content_digest) = 64),
    snapshot jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (mode,user_id,content_digest),
    CHECK (mode = current_setting('ss.mode',true)),
    CHECK (user_id = current_setting('ss.user_id',true)),
    CHECK (coalesce(snapshot->>'mode' = mode AND snapshot->>'account' = user_id, false)),
    CHECK (coalesce(snapshot->>'origin' = 'simulation', false)),
    CHECK (coalesce(snapshot->'actual_fills' = '[]'::jsonb, false)),
    CHECK (coalesce(snapshot->'readiness'->'paper_live_enabled' = 'false'::jsonb, false)),
    CHECK (coalesce(snapshot->'live_alerts_enabled' = 'false'::jsonb, false))
);
ALTER TABLE paper_qualification ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_qualification FORCE ROW LEVEL SECURITY;
CREATE POLICY paper_qualification_scope ON paper_qualification
    USING (mode = current_setting('ss.mode',true) AND user_id = current_setting('ss.user_id',true))
    WITH CHECK (mode = current_setting('ss.mode',true) AND user_id = current_setting('ss.user_id',true));
CREATE TRIGGER paper_qualification_immutable
    BEFORE UPDATE OR DELETE OR TRUNCATE ON paper_qualification
    FOR EACH STATEMENT EXECUTE FUNCTION reject_journal_mutation();

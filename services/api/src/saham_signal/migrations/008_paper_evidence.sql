-- Operator-reviewed evidence; API runtime gets SELECT only. No mutation endpoint.
CREATE FUNCTION paper_evidence_operator() RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user
$$;
CREATE TABLE paper_evidence (
    cursor bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mode text NOT NULL CHECK (mode='paper'),
    user_id text NOT NULL CHECK (length(user_id) BETWEEN 1 AND 128),
    kind text NOT NULL CHECK (kind IN ('G0','G1','acceptance','protocol')),
    content_digest text NOT NULL CHECK (length(content_digest)=64),
    actor text NOT NULL CHECK (length(actor) BETWEEN 1 AND 128),
    payload jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (mode,user_id,kind,content_digest),
    CHECK (mode=current_setting('ss.mode',true)),
    CHECK (user_id=current_setting('ss.user_id',true))
);
ALTER TABLE paper_evidence ENABLE ROW LEVEL SECURITY;
CREATE INDEX paper_evidence_latest ON paper_evidence(mode,user_id,kind,cursor DESC);
ALTER TABLE paper_evidence FORCE ROW LEVEL SECURITY;
CREATE POLICY paper_evidence_read ON paper_evidence FOR SELECT
    USING (mode=current_setting('ss.mode',true) AND user_id=current_setting('ss.user_id',true));
CREATE POLICY paper_evidence_write ON paper_evidence FOR INSERT
    WITH CHECK (paper_evidence_operator() AND mode=current_setting('ss.mode',true)
                AND user_id=current_setting('ss.user_id',true));
CREATE TRIGGER paper_evidence_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON paper_evidence
    FOR EACH STATEMENT EXECUTE FUNCTION reject_journal_mutation();

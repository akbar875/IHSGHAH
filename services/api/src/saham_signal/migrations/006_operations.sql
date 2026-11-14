-- Mode-wide switch. Runtime gets SELECT only; operator gets INSERT, never UPDATE/DELETE.
CREATE TABLE operation_events (
    mode text NOT NULL CHECK (mode IN ('research','paper','live')),
    revision integer NOT NULL CHECK (revision > 0),
    blocked boolean NOT NULL,
    reason text NOT NULL CHECK (reason IN ('pause','drift','rollback','resume')),
    release text NOT NULL CHECK (length(release) BETWEEN 1 AND 128),
    evidence text NOT NULL CHECK (length(evidence) BETWEEN 1 AND 512),
    actor text NOT NULL CHECK (length(actor) BETWEEN 1 AND 128),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(mode,revision),
    CHECK (mode = current_setting('ss.mode',true)),
    CHECK (blocked = (reason <> 'resume'))
);
ALTER TABLE operation_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE operation_events FORCE ROW LEVEL SECURITY;
CREATE POLICY operations_scope ON operation_events
    USING (mode = current_setting('ss.mode',true))
    WITH CHECK (mode = current_setting('ss.mode',true));
CREATE TRIGGER operations_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON operation_events
    FOR EACH STATEMENT EXECUTE FUNCTION reject_journal_mutation();

CREATE TABLE in_app_alerts (
    cursor bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mode text NOT NULL CHECK (mode IN ('research','paper','live')),
    user_id text NOT NULL,
    source_key text NOT NULL,
    channel text NOT NULL CHECK (channel = 'in_app'),
    priority integer NOT NULL CHECK (priority BETWEEN 0 AND 4),
    payload jsonb NOT NULL,
    UNIQUE(mode,user_id,source_key,channel),
    CHECK (mode = current_setting('ss.mode',true)),
    CHECK (user_id = current_setting('ss.user_id',true))
);
CREATE INDEX alert_inbox ON in_app_alerts(mode,user_id,priority,cursor DESC);
ALTER TABLE in_app_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE in_app_alerts FORCE ROW LEVEL SECURITY;
CREATE POLICY alert_scope ON in_app_alerts
    USING (mode = current_setting('ss.mode',true) AND user_id = current_setting('ss.user_id',true))
    WITH CHECK (mode = current_setting('ss.mode',true) AND user_id = current_setting('ss.user_id',true));
CREATE TRIGGER alerts_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON in_app_alerts
    FOR EACH STATEMENT EXECUTE FUNCTION reject_journal_mutation();

CREATE TABLE alert_gates (
    mode text NOT NULL CHECK (mode IN ('research','paper','live')),
    user_id text NOT NULL,
    subject text NOT NULL,
    gate jsonb NOT NULL,
    PRIMARY KEY(mode,user_id,subject),
    CHECK (mode = current_setting('ss.mode',true)),
    CHECK (user_id = current_setting('ss.user_id',true))
);
ALTER TABLE alert_gates ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_gates FORCE ROW LEVEL SECURITY;
CREATE POLICY gate_scope ON alert_gates
    USING (mode = current_setting('ss.mode',true) AND user_id = current_setting('ss.user_id',true))
    WITH CHECK (mode = current_setting('ss.mode',true) AND user_id = current_setting('ss.user_id',true));

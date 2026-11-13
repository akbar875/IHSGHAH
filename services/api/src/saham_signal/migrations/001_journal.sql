CREATE TABLE journal (
    cursor bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mode text NOT NULL CHECK (mode IN ('research', 'paper', 'live')),
    user_id text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('MarketEvent', 'Signal', 'Fill', 'Position', 'Experiment')),
    entity_id text NOT NULL CHECK (length(entity_id) BETWEEN 1 AND 128),
    version integer NOT NULL CHECK (version > 0),
    idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 256),
    content_digest text NOT NULL CHECK (length(content_digest) = 64),
    event_time timestamptz NOT NULL,
    provider_time timestamptz,
    received_at timestamptz NOT NULL,
    available_at timestamptz NOT NULL,
    processed_at timestamptz NOT NULL,
    sequence numeric(20, 0) NOT NULL CHECK (sequence >= 0 AND sequence < 1e20),
    source text NOT NULL CHECK (length(source) BETWEEN 1 AND 128),
    data_origin text NOT NULL CHECK (data_origin IN ('simulation', 'market')),
    contract_version text NOT NULL CHECK (contract_version = '1.0.0'),
    actor text NOT NULL CHECK (length(actor) BETWEEN 1 AND 128),
    reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 2000),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (mode, user_id, idempotency_key),
    UNIQUE (mode, user_id, kind, entity_id, version),
    CHECK (mode = current_setting('ss.mode', true)),
    CHECK ((kind = 'MarketEvent' AND user_id = '') OR
           (kind <> 'MarketEvent' AND length(user_id) BETWEEN 1 AND 128)),
    CHECK (kind <> 'Experiment' OR mode = 'research'),
    CHECK (mode <> 'live' OR data_origin <> 'simulation'),
    CHECK (available_at >= received_at AND processed_at >= available_at),
    CHECK (kind NOT IN ('Fill', 'Position') OR
        (payload->>'fees_idr' ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$')),
    CHECK (kind <> 'Fill' OR
        (payload->>'price_idr' ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$'
         AND (payload->>'price_idr')::numeric > 0))
);

CREATE INDEX journal_replay ON journal (mode, user_id, available_at, sequence, cursor);
CREATE INDEX journal_history ON journal (mode, user_id, kind, entity_id, version DESC);
CREATE INDEX journal_source_time ON journal (mode, source, recorded_at);

ALTER TABLE journal ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal FORCE ROW LEVEL SECURITY;
CREATE POLICY journal_scope ON journal
    USING (mode = current_setting('ss.mode', true)
           AND user_id = current_setting('ss.user_id', true))
    WITH CHECK (mode = current_setting('ss.mode', true)
                AND user_id = current_setting('ss.user_id', true));

CREATE FUNCTION reject_journal_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'journal is append-only; append a new version';
END;
$$;
CREATE TRIGGER journal_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON journal
    FOR EACH STATEMENT EXECUTE FUNCTION reject_journal_mutation();

-- Views preserve invoker RLS. Exact NUMERIC values, never float accounting.
CREATE VIEW fills WITH (security_invoker = true) AS
    SELECT cursor, mode, user_id, entity_id AS fill_id, payload->>'position_id' AS position_id,
           payload->>'side' AS side, (payload->>'price_idr')::numeric(18,2) AS price_idr,
           (payload->>'fees_idr')::numeric(18,2) AS fees_idr,
           (payload->>'lots')::integer AS lots, payload
    FROM journal WHERE kind = 'Fill';
CREATE VIEW position_versions WITH (security_invoker = true) AS
    SELECT cursor, mode, user_id, entity_id AS position_id, version,
           (payload->>'average_price_idr')::numeric(18,2) AS average_price_idr,
           (payload->>'fees_idr')::numeric(18,2) AS fees_idr,
           (payload->>'remaining_lots')::integer AS remaining_lots, payload
    FROM journal WHERE kind = 'Position';
CREATE VIEW signal_versions WITH (security_invoker = true) AS
    SELECT * FROM journal WHERE kind = 'Signal';
CREATE VIEW experiments WITH (security_invoker = true) AS
    SELECT * FROM journal WHERE kind = 'Experiment';
CREATE VIEW audit_versions WITH (security_invoker = true) AS
    SELECT cursor, mode, user_id, kind, entity_id, version, actor, reason,
           idempotency_key, recorded_at FROM journal;

-- No implicit deletion while licensed/personal retention remains undecided.
CREATE TABLE retention_policy (
    mode text NOT NULL CHECK (mode IN ('research', 'paper', 'live')),
    source text NOT NULL,
    retain_days integer CHECK (retain_days > 0),
    legal_hold boolean NOT NULL DEFAULT true,
    approval_ref text NOT NULL,
    PRIMARY KEY (mode, source)
);
CREATE VIEW retention_candidates WITH (security_invoker = true) AS
    SELECT j.cursor, j.mode, j.user_id, j.kind, j.source, j.recorded_at
    FROM journal j JOIN retention_policy p USING (mode, source)
    WHERE NOT p.legal_hold AND p.retain_days IS NOT NULL
      AND j.recorded_at < now() - make_interval(days => p.retain_days);

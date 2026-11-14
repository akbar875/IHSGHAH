-- Operator-only research store. API/market roles must not receive table grants.
CREATE TABLE internal_news (
    cursor bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source text NOT NULL,
    document_id text NOT NULL,
    revision integer NOT NULL CHECK (revision > 0),
    available_at timestamptz NOT NULL,
    payload jsonb NOT NULL,
    UNIQUE(source,document_id,revision),
    CHECK (current_database() = 'saham_signal_research'),
    CHECK ((payload->>'available_at')::timestamptz = available_at),
    CHECK (payload->>'source' = source),
    CHECK (payload->'document'->>'document_id' = document_id),
    CHECK ((payload->'document'->>'revision')::integer = revision)
);
CREATE INDEX news_availability ON internal_news(available_at,source,document_id,revision);
ALTER TABLE internal_news ENABLE ROW LEVEL SECURITY;
ALTER TABLE internal_news FORCE ROW LEVEL SECURITY;
CREATE POLICY news_internal ON internal_news
    USING (current_setting('ss.news_internal',true) = 'on')
    WITH CHECK (current_setting('ss.news_internal',true) = 'on');
CREATE TRIGGER news_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON internal_news
    FOR EACH STATEMENT EXECUTE FUNCTION reject_journal_mutation();

// Declarative authoring source. build.mjs emits portable JSON Schema/OpenAPI.
export const version = '1.0.0';
const ref = name => ({ $ref: `#/$defs/${name}` });
const text = { type: 'string', minLength: 1, maxLength: 256 };
const id = { type: 'string', pattern: '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$' };
const integer = { type: 'integer', minimum: 0, maximum: 2147483647 };
const enumeration = (...values) => ({ enum: values });
const array = (items, extra = {}) => ({ type: 'array', items, maxItems: 1000, ...extra });
const nullable = schema => ({ anyOf: [schema, { type: 'null' }] });
const object = (properties, optional = []) => ({
  type: 'object', additionalProperties: false, properties,
  required: Object.keys(properties).filter(key => !optional.includes(key)),
});
const timestamp = { type: 'string', format: 'date-time', pattern: 'Z$' };
const positive = { type: 'string', pattern: '^(?:0\\.(?:0[1-9]|[1-9][0-9])|[1-9][0-9]{0,15}\\.[0-9]{2})$' };
const money = { type: 'string', pattern: '^(?:0|[1-9][0-9]{0,15})\\.[0-9]{2}$' };
const decimal = { type: 'string', pattern: '^-?(?:0|[1-9][0-9]{0,15})\\.[0-9]{6}$' };
const probability = { type: 'number', minimum: 0, maximum: 1 };
const lots = { type: 'integer', minimum: 1, maximum: 2147483647 };
const symbol = { type: 'string', pattern: '^[A-Z][A-Z0-9.]{0,11}$' };
const sequence = { type: 'string', pattern: '^(0|[1-9][0-9]{0,19})$' };
const meta = {
  contract_version: { const: version }, as_of: timestamp,
  mode: enumeration('research', 'paper', 'live'),
  data_origin: enumeration('simulation', 'market'), quality: ref('Quality'),
};
const response = data => object({ ...meta, data });
const plan = {
  entry_zone: object({ lower_idr: positive, upper_idr: positive }),
  trigger: enumeration('PRICE_AND_TREND', 'PRICE_BREAKOUT', 'PRICE_PULLBACK'),
  invalidation: enumeration('PRICE_BREACH', 'DATA_UNHEALTHY', 'TIME_EXPIRED'),
  stop_idr: positive, targets_idr: array(positive, { minItems: 1, maxItems: 2 }),
  entry_from: timestamp, entry_until: timestamp, exit_deadline: timestamp,
};
export const defs = {
  Quality: object({
    status: enumeration('healthy', 'degraded', 'stale', 'disconnected', 'unavailable'),
    feed: enumeration('live', 'delayed', 'disconnected', 'unavailable'),
    last_heartbeat_at: nullable(timestamp), reasons: array(enumeration(
      'SIMULATION', 'SEQUENCE_GAP', 'HEARTBEAT_TIMEOUT', 'DELAYED_FEED',
      'INSUFFICIENT_DATA', 'MODEL_UNVALIDATED', 'MARKET_CLOSED', 'RESYNC_REQUIRED')),
  }),
  Probability: {
    oneOf: [
      object({ status: enumeration('unvalidated', 'unavailable'), value: { type: 'null' }, calibration_version: { type: 'null' } }),
      object({ status: { const: 'validated' }, value: probability, calibration_version: id }),
    ],
  },
  Signal: object({
    signal_id: id, version: { ...lots }, symbol, generated_at: timestamp,
    data_as_of: timestamp, valid_until: timestamp, horizon_minutes: enumeration(15, 30, 60, 240),
    model_version: id, policy_version: id, configuration_version: id,
    state: enumeration('WATCH', 'READY', 'EXPIRED', 'CANCELLED'),
    ...plan, return_quantiles: nullable(object({ p10: decimal, p50: decimal, p90: decimal, net_of_fees: { const: true } })),
    target_probability: ref('Probability'),
    assumptions: object({ reference_price_idr: positive, nominal_idr: positive, fee_schedule_version: id, order_type: { const: 'LIMIT' } }),
  }),
  LiquidityEstimate: object({
    signal_id: id, signal_version: lots, nominal_idr: positive, lots,
    depth_as_of: timestamp, order_policy: { const: 'LIMIT' }, deadline: timestamp,
    slippage_cap_ratio: decimal, category: enumeration('sufficient', 'limited', 'insufficient', 'unavailable'),
    entry_fill_probability: ref('Probability'), exit_fill_probability: ref('Probability'), quality: ref('Quality'),
  }),
  FillRequest: object({
    side: enumeration('BUY', 'SELL'), price_idr: positive, lots,
    filled_at: timestamp, fees_idr: money,
  }),
  OpenPositionRequest: object({ symbol, signal_id: nullable(id), fill: ref('FillRequest') }),
  Fill: object({
    fill_id: id, position_id: id, side: enumeration('BUY', 'SELL'),
    price_idr: positive, lots, filled_at: timestamp, recorded_at: timestamp,
    fees_idr: money, origin: enumeration('manual', 'simulation'),
  }),
  Position: object({
    position_id: id, user_id: id, symbol, fills: array(ref('Fill'), { minItems: 1 }),
    remaining_lots: integer, average_price_idr: positive, fees_idr: money,
    opened_at: timestamp, plan_version: lots,
    status: enumeration('OPEN', 'PARTIAL', 'EXIT_REQUESTED', 'CLOSED'),
    overnight_risk: { type: 'boolean' },
  }),
  PositionPlan: object({ stop_idr: positive, target_idr: positive, exit_deadline: timestamp,
    sell_fee_ratio: { type: 'string', pattern: '^(?:0\\.[0-9]{6}|1\\.000000)$' } }),
  ExitRequest: object({ reason: enumeration('MANUAL', 'STOP', 'TARGET', 'DEADLINE') }),
  PositionMonitor: object({ position: ref('Position'), plan: nullable(ref('PositionPlan')),
    invested_idr: money, remaining_cost_idr: money,
    realized_pnl_idr: { type: 'string', pattern: '^-?(?:0|[1-9][0-9]{0,18})\\.[0-9]{2}$' },
    stop_loss_idr: nullable(money), target_net_idr: nullable({ type: 'string', pattern: '^-?(?:0|[1-9][0-9]{0,18})\\.[0-9]{2}$' }),
    exit_reason: nullable(enumeration('MANUAL', 'STOP', 'TARGET', 'DEADLINE')) }),
  Alert: object({
    event_id: id, user_id: id, signal_id: nullable(id), position_id: nullable(id),
    type: enumeration('ENTRY_READY', 'INVALIDATED', 'TP', 'STOP', 'TIME_EXIT', 'PLAN_CHANGED', 'DATA_DISCONNECTED'),
    created_at: timestamp, delivered_at: nullable(timestamp),
    status: enumeration('pending', 'delivered', 'failed'), channel: { const: 'in_app' }, dedup_key: id,
  }),
  InstrumentRule: object({
    symbol, board: text, effective_from: timestamp, effective_to: nullable(timestamp),
    rule_version: id, lot_size_shares: lots,
    tick_rule: array(object({ from_idr: money, to_idr: nullable(positive), tick_idr: positive }), { minItems: 1 }),
    limit_rule: object({ reference_price_idr: positive, lower_idr: positive, upper_idr: positive, version: id }),
    session: id, calendar_version: id, tradability: enumeration('tradable', 'suspended', 'unsupported', 'closed'),
  }),
  BookLevel: object({ price_idr: positive, lots, cumulative_lots: lots }),
  Depth: object({ symbol, snapshot_id: id, sequence, depth_as_of: timestamp,
    bids: array(ref('BookLevel'), { maxItems: 50 }), asks: array(ref('BookLevel'), { maxItems: 50 }),
    available_levels: integer, limited: { type: 'boolean' },
  }),
  Trade: object({ price_idr: positive, lots, aggressor: enumeration('buyer', 'seller', 'unknown') }),
  FeedStatus: object({ status: enumeration('healthy', 'degraded', 'disconnected'), heartbeat_at: timestamp }),
  MarketEvent: object({
    ...meta, event_id: id, symbol, event_type: enumeration('trade', 'book_snapshot', 'feed_status'),
    event_time: timestamp, provider_time: nullable(timestamp), received_at: timestamp,
    available_at: timestamp, processed_at: timestamp, sequence, source: id,
    payload: { oneOf: [ref('Trade'), ref('Depth'), ref('FeedStatus')] },
  }),
  NewsEvent: object({
    ...meta, event_id: id, entity_ids: array(id), published_at: timestamp,
    first_seen_at: timestamp, available_at: timestamp, source_ref: id,
    dedup_id: id, event_type: enumeration('disclosure', 'news', 'global'), confidence: probability,
  }),
  Experiment: object({
    ...meta, experiment_id: id, dataset_version: id, code_version: id,
    split: object({ train_from: timestamp, train_until: timestamp, validation_from: timestamp,
      validation_until: timestamp, test_from: timestamp, test_until: timestamp, purge_minutes: integer, embargo_minutes: integer }),
    parameters: array(object({ name: id, value: { type: ['string', 'number', 'boolean', 'null'] } })),
    assumptions: object({ fee_schedule_version: id, fill_model_version: id, latency_ms: integer, intrabar_policy: { const: 'conservative' } }),
    metrics: array(object({ name: id, value: nullable({ type: 'number' }), unit: enumeration('ratio', 'idr', 'count', 'milliseconds') })),
    promotion_decision: enumeration('experimental', 'rejected', 'approved'), report_ref: nullable(id),
  }),
  Candle: object({ at: timestamp, open_idr: positive, high_idr: positive, low_idr: positive, close_idr: positive, volume_lots: integer }),
  Projection: object({ at: timestamp, median_idr: positive, lower_idr: positive, upper_idr: positive, coverage: probability }),
  Chart: object({ symbol, interval: enumeration('1m', '5m', '15m'), candles: array(ref('Candle')),
    projection: array(ref('Projection')), model_version: nullable(id), horizon_minutes: nullable(lots),
    coverage_status: enumeration('unvalidated', 'validated', 'unavailable') }),
  Pressure: object({ window_minutes: enumeration(1, 5, 15),
    buy_ratio: nullable(probability), sell_ratio: nullable(probability), classified_ratio: probability,
    method: enumeration('provider', 'estimated', 'unavailable'), validated: { type: 'boolean' } }),
  StockDetail: object({ symbol, last_price_idr: nullable(positive), rule: ref('InstrumentRule'),
    signal: nullable(ref('Signal')), liquidity: nullable(ref('LiquidityEstimate')),
    depth: nullable(ref('Depth')), pressure: array(ref('Pressure'), { maxItems: 3 }) }),
  Watchlist: object({ symbols: array(symbol, { uniqueItems: true, maxItems: 200 }) }),
  UserFeeSchedule: object({ version: id,
    buy_ratio: { type: 'string', pattern: '^(?:0\\.[0-9]{6}|1\\.000000)$' },
    sell_ratio: { type: 'string', pattern: '^(?:0\\.[0-9]{6}|1\\.000000)$' },
    effective_from: timestamp, effective_to: timestamp, source: text,
    verification: { const: 'user_assumption' } }),
  SettingsEligibility: object({ configuration_version: id, risk_budget_idr: money,
    combined_budget_idr: money, budget_lots_ceiling: { type: 'integer', minimum: 0 },
    eligible_lots: { const: 0 }, reason: enumeration('MODEL_UNVALIDATED', 'FEE_SCHEDULE_EXPIRED') }),
  RiskSettings: object({ configuration_version: id, nominal_idr: positive, capital_idr: positive,
    risk_per_position_ratio: decimal, max_combined_risk_ratio: decimal, max_positions: lots,
    fee_schedule_version: id }),
  Error: object({ code: enumeration('INVALID_REQUEST', 'UNAUTHENTICATED', 'FORBIDDEN', 'NOT_FOUND',
    'CONFLICT', 'RATE_LIMITED', 'DATA_UNAVAILABLE', 'UNSUPPORTED_VERSION', 'RESYNC_REQUIRED', 'INTERNAL_ERROR'),
    request_id: id, retryable: { type: 'boolean' }, fields: array(enumeration('price_idr', 'lots', 'filled_at', 'fees_idr',
      'symbol', 'interval', 'cursor', 'configuration_version', 'nominal_idr', 'risk_per_position_ratio', 'contract_version')) }),
};
// New endpoint profile preserves the frozen RiskSettings v1 payload unchanged.
defs.RiskProfile = object({ ...defs.RiskSettings.properties, fee_schedule: ref('UserFeeSchedule') });
// A tagged payload prevents a book being accepted as a trade (and vice versa).
defs.MarketEvent.allOf = Object.entries({ trade: 'Trade', book_snapshot: 'Depth', feed_status: 'FeedStatus' }).map(([tag, type]) => ({
  if: { properties: { event_type: { const: tag } }, required: ['event_type'] },
  then: { properties: { payload: ref(type) } },
}));
defs.Position.allOf = [{
  if: { properties: { status: { const: 'CLOSED' } }, required: ['status'] },
  then: { properties: { remaining_lots: { const: 0 } } },
  else: { properties: { remaining_lots: lots } },
}];
defs.Chart.allOf = [{
  if: { properties: { coverage_status: { enum: ['unvalidated', 'unavailable'] } }, required: ['coverage_status'] },
  then: { properties: { projection: { maxItems: 0 } } },
}];
defs.Pressure.allOf = [{
  if: { properties: { validated: { const: false } }, required: ['validated'] },
  then: { properties: { buy_ratio: { type: 'null' }, sell_ratio: { type: 'null' } } },
}];
for (const [name, type] of Object.entries({
  CandidatesResponse: array(ref('Signal')), StockDetailResponse: ref('StockDetail'),
  DepthResponse: ref('Depth'), ChartResponse: ref('Chart'), WatchlistResponse: ref('Watchlist'),
  RiskSettingsResponse: ref('RiskSettings'), RiskProfileResponse: ref('RiskProfile'), SettingsEligibilityResponse: ref('SettingsEligibility'), PositionResponse: ref('Position'),
  PositionsResponse: array(ref('Position')), PositionMonitorResponse: ref('PositionMonitor'), AlertsResponse: array(ref('Alert')),
  SignalHistoryResponse: array(ref('Signal')), ErrorResponse: ref('Error'),
})) defs[name] = response(type);
const streamScope = {
  ...meta, stream_id: id, subscription_id: id,
  topic: enumeration('signals', 'positions', 'alerts', 'depth'), symbol: nullable(symbol),
  user_id: nullable(id), cursor: id, sequence,
};
defs.StreamEntity = { oneOf: [ref('Signal'), ref('Position'), ref('Alert'), ref('Depth')] };
defs.Snapshot = object({ ...streamScope, kind: { const: 'snapshot' }, items: array(ref('StreamEntity')) });
defs.Delta = object({ ...streamScope, kind: { const: 'delta' }, previous_sequence: sequence,
  operations: array({ oneOf: [
    object({ op: { const: 'upsert' }, entity_id: id, entity: ref('StreamEntity') }),
    object({ op: { const: 'remove' }, entity_id: id }),
  ] }, { minItems: 1 }),
});
for (const name of ['Snapshot', 'Delta']) {
  defs[name].allOf = Object.entries({ signals: 'Signal', positions: 'Position', alerts: 'Alert', depth: 'Depth' }).map(([topic, type]) => ({
    if: { properties: { topic: { const: topic } }, required: ['topic'] },
    then: { properties: {
      ...(name === 'Snapshot' ? { items: { items: ref(type) } } : {
        operations: { items: { properties: { entity: ref(type) } } },
      }),
      user_id: ['positions', 'alerts'].includes(topic) ? id : nullable(id),
      symbol: topic === 'depth' ? symbol : nullable(symbol),
    } },
  }));
}
defs.Subscribe = object({ kind: { const: 'subscribe' }, contract_version: { const: version },
  subscription_id: id, topic: enumeration('signals', 'positions', 'alerts', 'depth'), symbol: nullable(symbol),
  resume_cursor: nullable(id),
});
defs.StreamMessage = { oneOf: [ref('Snapshot'), ref('Delta'), ref('ErrorResponse')] };
defs.Alert.anyOf = [
  { properties: { signal_id: id } }, { properties: { position_id: id } },
];
defs.OpenPositionRequest.properties.fill = {
  allOf: [ref('FillRequest'), { properties: { side: { const: 'BUY' } } }],
};
defs.Subscribe.allOf = [{
  if: { properties: { topic: { const: 'depth' } }, required: ['topic'] },
  then: { properties: { symbol } },
}];
// Every envelope forbids fixtures from claiming the live environment.
for (const definition of Object.values(defs)) {
  if (definition.properties?.data_origin) {
    definition.allOf ??= [];
    definition.allOf.push({
      if: { properties: { data_origin: { const: 'simulation' } }, required: ['data_origin'] },
      then: { properties: { mode: { enum: ['research', 'paper'] } } },
    });
  }
}
export const schema = {
  $schema: 'https://json-schema.org/draft/2020-12/schema',
  $id: 'https://contracts.saham-signal.invalid/v1/schema.json',
  title: 'Saham Signal wire contracts v1', $defs: defs,
};

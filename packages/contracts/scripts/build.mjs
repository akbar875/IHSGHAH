import { readFile, writeFile } from 'node:fs/promises';
import { isDeepStrictEqual } from 'node:util';
import { schema, version } from './definitions.mjs';

const ref = name => ({ $ref: `./schema.json#/$defs/${name}` });
const content = name => ({ 'application/json': { schema: ref(name) } });
const pathParameter = name => ({ name, in: 'path', required: true, schema: { type: 'string', minLength: 1 } });
const endpoints = [
  ['/candidates', 'get', 'listCandidates', 'CandidatesResponse'],
  ['/stocks/{symbol}', 'get', 'getStock', 'StockDetailResponse'],
  ['/stocks/{symbol}/depth', 'get', 'getDepth', 'DepthResponse'],
  ['/stocks/{symbol}/chart', 'get', 'getChart', 'ChartResponse'],
  ['/stocks/{symbol}/signals', 'get', 'signalHistory', 'SignalHistoryResponse'],
  ['/watchlist', 'get', 'getWatchlist', 'WatchlistResponse'],
  ['/watchlist', 'put', 'replaceWatchlist', 'WatchlistResponse', 'Watchlist'],
  ['/settings/risk', 'get', 'getRiskSettings', 'RiskSettingsResponse'],
  ['/settings/eligibility', 'get', 'getSettingsEligibility', 'SettingsEligibilityResponse'],
  ['/settings/profile', 'get', 'getRiskProfile', 'RiskProfileResponse'],
  ['/settings/profile', 'put', 'replaceRiskProfile', 'RiskProfileResponse', 'RiskProfile'],
  ['/settings/risk', 'put', 'replaceRiskSettings', 'RiskSettingsResponse', 'RiskSettings'],
  ['/positions', 'get', 'listPositions', 'PositionsResponse'],
  ['/positions', 'post', 'openPosition', 'PositionResponse', 'OpenPositionRequest'],
  ['/positions/{position_id}', 'get', 'getPosition', 'PositionResponse'],
  ['/positions/{position_id}/fills', 'post', 'recordFill', 'PositionResponse', 'FillRequest'],
  ['/alerts', 'get', 'listAlerts', 'AlertsResponse'],
];
const paths = {};
for (const [path, method, operationId, result, body] of endpoints) {
  const parameters = [...path.matchAll(/\{([^}]+)\}/g)].map(match => pathParameter(match[1]));
  if (method === 'post' || method === 'put') parameters.push({ name: 'Idempotency-Key', in: 'header', required: true,
    schema: { type: 'string', minLength: 1, maxLength: 128 } });
  if (operationId === 'getChart') parameters.push({ name: 'interval', in: 'query', required: true,
    schema: { enum: ['1m', '5m', '15m'] } });
  if (operationId === 'listCandidates') parameters.push({ name: 'nominal_idr', in: 'query', required: false,
    description: 'Requested sizing nominal. Defaults to server setting; never changes account, mode or horizon. Simulation does not imply validated sizing or ranking.',
    schema: schema.$defs.Signal.properties.assumptions.properties.nominal_idr });
  paths[path] ??= {};
  paths[path][method] = {
    operationId, parameters,
    ...(body ? { requestBody: { required: true, content: content(body) } } : {}),
    responses: {
      [method === 'post' ? '201' : '200']: { description: 'Versioned snapshot; simulated fixtures are not live data.', content: content(result) },
      ...Object.fromEntries([400, 401, 403, 404, 409, 422, 429, 500, 503].map(code => [code,
        { description: 'Safe machine-readable error; no upstream documents, secrets or stack traces.', content: content('ErrorResponse') }])),
    },
  };
}
const openapi = {
  openapi: '3.1.1', info: { title: 'Saham Signal public API', version,
    description: 'Contract specification only. Server derives account/mode from authenticated session and deployment; no internal news or experiment routes.' },
  jsonSchemaDialect: 'https://json-schema.org/draft/2020-12/schema',
  servers: [{ url: '/api/v1' }], security: [{ sessionCookie: [] }], paths,
  components: { securitySchemes: { sessionCookie: { type: 'apiKey', in: 'cookie', name: 'saham_session',
    description: 'Placeholder for SS-023: secure HttpOnly session, authorization and CSRF protection required before pilot.' } } },
  'x-websocket': { path: '/api/v1/stream', client: ref('Subscribe'), server: ref('StreamMessage'),
    protocol: 'See ../README.md for cursor, replacement delta, gap and reconnect rules.' },
};
for (const [filename, value] of [['schema.json', schema], ['openapi.json', openapi]]) {
  const target = new URL(`../v1/${filename}`, import.meta.url);
  if (process.argv.includes('--check')) {
    if (!isDeepStrictEqual(JSON.parse(await readFile(target, 'utf8')), value)) throw Error(`${filename} is stale; run npm run build`);
  } else await writeFile(target, `${JSON.stringify(value, null, 2)}\n`);
}

import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

const read = async name => JSON.parse(await readFile(new URL(`../v1/${name}`, import.meta.url), 'utf8'));
const schema = await read('schema.json');
const examples = await read('examples.json');
const openapi = await read('openapi.json');
// Conditional branches refine types established by their parent schema.
const ajv = new Ajv2020({ strict: true, strictTypes: false, allErrors: true });
addFormats(ajv);
ajv.addSchema(schema);
const validators = Object.fromEntries(Object.keys(schema.$defs).map(name => [name,
  ajv.compile({ $ref: `${schema.$id}#/$defs/${name}` })]));
const copy = name => structuredClone(examples.find(example => example.schema === name).payload);
function valid(name, payload) {
  assert.ok(validators[name](payload), `${name}: ${JSON.stringify(validators[name].errors)}`);
}
function invalid(name, mutate) {
  const payload = copy(name);
  mutate(payload);
  assert.equal(validators[name](payload), false, `${name} accepted invalid payload`);
}

test('all schemas compile; every entity/request/response has a valid fixture', () => {
  for (const example of examples) valid(example.schema, example.payload);
  for (const name of Object.keys(validators)) {
    assert.ok(examples.some(example => example.schema === name), `Missing fixture: ${name}`);
  }
});

test('money, lots, UTC, version, enum and simulation boundaries reject unsafe values', () => {
  invalid('FillRequest', p => { p.price_idr = 1250.1; });
  invalid('FillRequest', p => { p.price_idr = '1250.001'; });
  invalid('FillRequest', p => { p.price_idr = '0.00'; });
  invalid('FillRequest', p => { p.lots = 0.5; });
  invalid('FillRequest', p => { p.lots = 0; });
  invalid('FillRequest', p => { p.filled_at = '2026-11-12T10:00:00+07:00'; });
  invalid('FillRequest', p => { p.filled_at = '2026-02-30T03:00:00Z'; });
  invalid('FillRequest', p => { p.side = 'SHORT'; });
  invalid('CandidatesResponse', p => { p.contract_version = '2.0.0'; });
  invalid('CandidatesResponse', p => { p.mode = 'live'; });
  invalid('MarketEvent', p => { p.sequence = 9007199254740992; });
});

test('uncalibrated probabilities and projections cannot invent precision', () => {
  invalid('Signal', p => { p.target_probability.value = 0; });
  invalid('Signal', p => { p.target_probability.status = 'validated'; });
  const calibrated = { status: 'validated', value: 0.6, calibration_version: 'calibration-test-1' };
  valid('Probability', calibrated);
  assert.equal(validators.Probability({ ...calibrated, value: 1.1 }), false);
  invalid('Chart', p => { p.projection = [copy('Projection')]; });
  invalid('Pressure', p => { p.buy_ratio = 0.7; });
});

test('position/fill and event tags preserve transport invariants', () => {
  invalid('Position', p => { p.status = 'CLOSED'; });
  invalid('Position', p => { p.remaining_lots = 0; });
  invalid('MarketEvent', p => { p.event_type = 'book_snapshot'; });
  invalid('Alert', p => { p.signal_id = null; p.position_id = null; });
  invalid('OpenPositionRequest', p => { p.fill.side = 'SELL'; });
  invalid('Subscribe', p => { p.topic = 'depth'; p.symbol = null; });
});

test('public REST and WebSocket schemas cannot reference internal entities or open objects', () => {
  const visited = new Set();
  function inspect(node) {
    if (!node || typeof node !== 'object') return;
    if (node.$ref) {
      const name = node.$ref.split('/').at(-1);
      assert.ok(!['NewsEvent', 'Experiment', 'MarketEvent'].includes(name), `Internal exposure: ${name}`);
      assert.ok(schema.$defs[name], `Unresolved ${node.$ref}`);
      if (!visited.has(name)) { visited.add(name); inspect(schema.$defs[name]); }
    }
    if (node.type === 'object') assert.equal(node.additionalProperties, false);
    for (const value of Object.values(node)) {
      if (Array.isArray(value)) value.forEach(inspect);
      else if (value && typeof value === 'object') inspect(value);
    }
  }
  inspect(openapi.paths);
  inspect(openapi['x-websocket']);
  assert.ok(visited.has('Position') && visited.has('Signal'));
  for (const name of ['CandidatesResponse', 'StockDetailResponse', 'Snapshot', 'Delta', 'ErrorResponse']) {
    invalid(name, p => { p.vendor_token = 'forbidden-test-value'; });
  }
  invalid('Signal', p => { p.news_document = { body: 'internal' }; });
  invalid('Signal', p => { p.assumptions.secret = 'forbidden'; });
  invalid('ErrorResponse', p => { p.data.stack = 'internal stack'; });
  invalid('FillRequest', p => { p.user_id = 'another-account'; });
  invalid('FillRequest', p => { p.mode = 'live'; });
});

test('REST operations have versioned responses, errors, authentication and valid references', () => {
  assert.equal(openapi.openapi, '3.1.1');
  assert.equal(openapi.servers[0].url, '/api/v1');
  assert.ok(openapi.security.length);
  const ids = new Set();
  for (const methods of Object.values(openapi.paths)) {
    for (const operation of Object.values(methods)) {
      assert.ok(!ids.has(operation.operationId)); ids.add(operation.operationId);
      for (const response of Object.values(operation.responses)) {
        const name = response.content['application/json'].schema.$ref.split('/').at(-1);
        assert.ok(name.endsWith('Response'));
        valid(name, copy(name));
      }
      if (operation.requestBody) {
        const name = operation.requestBody.content['application/json'].schema.$ref.split('/').at(-1);
        valid(name, copy(name));
        assert.ok(operation.parameters.some(p => p.name === 'Idempotency-Key' && p.required));
      }
    }
  }
  assert.equal(ids.size, 20);
});

test('stream topic rejects another entity; sequences remain exact beyond JS safe integer', () => {
  invalid('Snapshot', p => { p.topic = 'positions'; p.user_id = 'pilot'; });
  invalid('Delta', p => { p.operations[0].entity = copy('Experiment'); });
  const delta = copy('Delta');
  delta.previous_sequence = '9007199254740992';
  delta.sequence = '9007199254740993';
  valid('Delta', delta);
  assert.equal(BigInt(delta.sequence), BigInt(delta.previous_sequence) + 1n);
});

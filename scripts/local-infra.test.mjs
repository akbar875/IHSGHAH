import test from 'node:test';
import assert from 'node:assert/strict';
import { plan, assertLocalVolumes } from './local-infra.mjs';

test('local endpoint and fixed project resist ambient production overrides', () => {
  const p = plan(['up'], '', { PATH: 'keep', DOCKER_HOST: 'tcp://production:2376', DOCKER_CONTEXT: 'production', COMPOSE_FILE: 'production.yaml', COMPOSE_PROJECT_NAME: 'production', LOCAL_MODE: 'live', DATABASE_URL: 'production', REDIS_URL: 'production' }, 'linux');
  assert.equal(p.project, 'saham-signal-local-research');
  assert.deepEqual(p.docker, ['--host', 'unix:///var/run/docker.sock']);
  for (const key of ['DOCKER_HOST', 'DOCKER_CONTEXT', 'COMPOSE_FILE', 'COMPOSE_PROJECT_NAME', 'DATABASE_URL', 'REDIS_URL']) assert.equal(p.env[key], undefined);
  assert.equal(p.env.PATH, 'keep');
  assert.equal(p.env.COMPOSE_DISABLE_ENV_FILE, '1');
  assert.equal(plan(['up'], '', {}, 'win32').docker[1], 'npipe:////./pipe/dockerDesktopLinuxEngine');
});

test('modes have separate projects, ports, credentials and exact reset confirmation', () => {
  const plans = ['research', 'paper', 'live'].map(mode => plan(['up', mode], '', {}));
  for (const field of ['LOCAL_POSTGRES_PORT', 'LOCAL_REDIS_PORT', 'LOCAL_POSTGRES_PASSWORD', 'LOCAL_REDIS_PASSWORD']) assert.equal(new Set(plans.map(p => p.env[field])).size, 3);
  for (const p of plans) {
    assert.throws(() => plan(['reset', p.mode]));
    assert.throws(() => plan(['reset', p.mode, '--confirm-local-reset=production']));
    assert.deepEqual(plan(['reset', p.mode, `--confirm-local-reset=${p.project}`]).command, ['down', '--volumes']);
    assert.deepEqual(plan(['down', p.mode]).command, ['down']);
  }
  for (const args of [['up', '../production'], ['prune'], ['up', 'research', '--file=production.yaml']]) assert.throws(() => plan(args));
});

test('local env accepts configurable ports/passwords and rejects overrides/injection', () => {
  const p = plan(['up'], 'LOCAL_POSTGRES_PORT=15432\nLOCAL_REDIS_PORT=16379\nLOCAL_POSTGRES_PASSWORD=custom_local_password');
  assert.equal(p.env.LOCAL_POSTGRES_PORT, '15432');
  assert.equal(p.env.LOCAL_REDIS_PORT, '16379');
  assert.equal(p.env.LOCAL_POSTGRES_PASSWORD, 'custom_local_password');
  assert.throws(() => plan(['up'], 'LOCAL_POSTGRES_PORT=05432\nLOCAL_REDIS_PORT=5432'));
  for (const source of ['DOCKER_HOST=tcp://production', 'LOCAL_MODE=live', 'LOCAL_POSTGRES_PORT=5432\nLOCAL_REDIS_PORT=5432', 'LOCAL_POSTGRES_PORT=1', 'LOCAL_POSTGRES_PORT=65536', 'LOCAL_POSTGRES_PASSWORD=$(evil)', 'LOCAL_REDIS_PASSWORD=has space', 'LOCAL_POSTGRES_PORT=5432\nLOCAL_POSTGRES_PORT=5433']) assert.throws(() => plan(['up'], source));
});

test('reset refuses volumes with missing/foreign ownership labels or names', () => {
  const project = 'saham-signal-local-research';
  const volume = { Name: `${project}_postgres-data`, Labels: { 'io.saham-signal.scope': 'local-only', 'com.docker.compose.project': project } };
  assert.doesNotThrow(() => assertLocalVolumes([volume], project));
  for (const other of [{ ...volume, Name: 'production' }, { ...volume, Labels: {} }, { ...volume, Labels: { ...volume.Labels, 'com.docker.compose.project': 'production' } }]) assert.throws(() => assertLocalVolumes([other], project));
});

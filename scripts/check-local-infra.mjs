// Opt-in real integration: uses local research/paper stacks, stops/restarts them.
import { spawnSync } from 'node:child_process';
import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { plan } from './local-infra.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const python = resolve(root, 'services/api/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
function run(command, args, env) {
  const result = spawnSync(command, args, { cwd: root, env, stdio: 'inherit' });
  if (result.error || result.status !== 0) throw Error('Local integration command failed.');
}
function stack(mode) {
  const path = resolve(root, `infra/.env.${mode}`);
  return plan(['up', mode], existsSync(path) ? readFileSync(path, 'utf8') : '');
}
function compose(p, args) { run('docker', [...p.compose, ...args], p.env); }
function probe(p, action) {
  const v = p.env;
  run(python, [resolve(root, 'infra/probe.py'), action], {
    ...v, APP_MODE: p.mode,
    DATABASE_URL: `postgresql://saham_signal_${p.mode}:${v.LOCAL_POSTGRES_PASSWORD}@127.0.0.1:${v.LOCAL_POSTGRES_PORT}/saham_signal_${p.mode}`,
    REDIS_URL: `redis://:${v.LOCAL_REDIS_PASSWORD}@127.0.0.1:${v.LOCAL_REDIS_PORT}/0`,
    BAD_REDIS_URL: `redis://:${v.LOCAL_REDIS_PASSWORD}_wrong@127.0.0.1:${v.LOCAL_REDIS_PORT}/0`,
    BAD_DATABASE_URL: `postgresql://saham_signal_${p.mode}:${v.LOCAL_POSTGRES_PASSWORD}_wrong@127.0.0.1:${v.LOCAL_POSTGRES_PORT}/saham_signal_${p.mode}`,
    REDIS_NAMESPACE: `saham-signal:${p.mode}:`,
    SESSION_SECRET: 'local_integration_only_32_characters', PILOT_ACCOUNT_ID: 'local-integration',
  });
}
const research = stack('research');
const paper = stack('paper');
try {
  compose(research, research.command);
  probe(research, 'write');
  // Recreate containers: both named volumes must retain the sentinel.
  compose(research, ['down']);
  compose(research, research.command);
  probe(research, 'persisted');
  for (const service of ['postgres', 'redis']) {
    compose(research, ['stop', service]);
    probe(research, 'unavailable');
    compose(research, research.command);
    probe(research, 'ready');
  }
  compose(paper, paper.command);
  probe(paper, 'isolated');
  probe(research, 'cleanup');
  console.log('Local infrastructure integration passed. Volumes retained; stacks stopped.');
} finally {
  compose(research, ['down']);
  compose(paper, ['down']);
}

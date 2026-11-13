import { spawnSync } from 'node:child_process';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const keys = ['LOCAL_POSTGRES_PORT', 'LOCAL_REDIS_PORT', 'LOCAL_POSTGRES_PASSWORD', 'LOCAL_REDIS_PASSWORD'];

export function plan(args, source = '', inherited = process.env, platform = process.platform) {
  const [action, mode = 'research', confirmation, ...extra] = args;
  const modes = ['research', 'paper', 'live'];
  if (!['up', 'status', 'stop', 'down', 'reset', 'check'].includes(action) || !modes.includes(mode) || extra.length) {
    throw Error('Usage: node scripts/local-infra.mjs <up|status|stop|down|reset|check> [research|paper|live] [--confirm-local-reset=<project>]');
  }
  const project = `saham-signal-local-${mode}`;
  if (action === 'reset' ? confirmation !== `--confirm-local-reset=${project}` : confirmation !== undefined) {
    throw Error(`Reset requires --confirm-local-reset=${project}; other actions accept no confirmation.`);
  }
  const offset = modes.indexOf(mode);
  const values = {
    LOCAL_MODE: mode,
    LOCAL_POSTGRES_PORT: String(5432 + offset),
    LOCAL_REDIS_PORT: String(6379 + offset),
    LOCAL_POSTGRES_PASSWORD: `local_only_${mode}`,
    LOCAL_REDIS_PASSWORD: `local_redis_${mode}`,
  };
  const seen = new Set();
  for (const line of source.split(/\r?\n/)) {
    if (!line.trim() || line.trim().startsWith('#')) continue;
    const match = /^([A-Z_]+)=([^\s#]+)$/.exec(line.trim());
    if (!match || !keys.includes(match[1]) || seen.has(match[1])) throw Error('Invalid local env file; use infra/.env.example.');
    seen.add(match[1]);
    values[match[1]] = match[2];
  }
  for (const key of keys) {
    const value = values[key];
    if (key.endsWith('PORT') ? !/^\d+$/.test(value) || Number(value) < 1024 || Number(value) > 65535 : !/^[A-Za-z0-9_-]{12,128}$/.test(value)) {
      throw Error('Invalid local port/password; see infra/README.md.');
    }
  }
  if (Number(values.LOCAL_POSTGRES_PORT) === Number(values.LOCAL_REDIS_PORT)) throw Error('Local ports must differ.');
  // Never inherit remote contexts, Compose overrides, ambient DSNs or local values.
  const env = Object.fromEntries(Object.entries(inherited).filter(([key]) => !/^(DOCKER_|COMPOSE_|LOCAL_|DATABASE_URL$|REDIS_URL$)/i.test(key)));
  Object.assign(env, values, { COMPOSE_DISABLE_ENV_FILE: '1' });
  const host = platform === 'win32' ? 'npipe:////./pipe/dockerDesktopLinuxEngine' : 'unix:///var/run/docker.sock';
  const docker = ['--host', host];
  const compose = [...docker, 'compose', '--project-name', project, '--project-directory', root, '--file', resolve(root, 'infra/compose.yaml')];
  const commands = { up: ['up', '-d', '--wait', '--wait-timeout', '120'], status: ['ps', '--all'], stop: ['stop'], down: ['down'], reset: ['down', '--volumes'], check: ['config', '--quiet'] };
  return { action, mode, project, env, docker, compose, command: commands[action] };
}

export function assertLocalVolumes(volumes, project) {
  for (const volume of volumes) {
    const labels = volume.Labels ?? {};
    if (!['postgres-data', 'redis-data'].some(name => volume.Name === `${project}_${name}`) || labels['io.saham-signal.scope'] !== 'local-only' || labels['com.docker.compose.project'] !== project) {
      throw Error('Reset refused: unexpected volume ownership.');
    }
  }
}

function run() {
  const args = process.argv.slice(2);
  // Validate mode before using it in a path.
  const initial = plan(args);
  const envPath = resolve(root, `infra/.env.${initial.mode}`);
  const p = plan(args, existsSync(envPath) ? readFileSync(envPath, 'utf8') : '');
  function docker(args, capture = false) {
    const result = spawnSync('docker', args, { cwd: root, env: p.env, encoding: 'utf8', stdio: capture ? 'pipe' : 'inherit' });
    if (result.error || result.status !== 0) throw Error('Docker command failed; check local Docker Engine and Compose.');
    return result.stdout;
  }
  if (p.action === 'reset') {
    // Enumerate exact names; never prune, target a DSN, or select arbitrary projects.
    const names = docker([...p.docker, 'volume', 'ls', '--format', '{{.Name}}'], true).trim().split(/\r?\n/);
    const targets = ['postgres-data', 'redis-data'].map(name => `${p.project}_${name}`).filter(name => names.includes(name));
    if (targets.length) assertLocalVolumes(JSON.parse(docker([...p.docker, 'volume', 'inspect', ...targets], true)), p.project);
  }
  docker([...p.compose, ...p.command]);
  console.log(`${p.project}: ${p.action} complete (local development only).`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { run(); } catch (error) { console.error(error.message); process.exitCode = 1; }
}

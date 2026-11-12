import { readFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';

const root = new URL('../', import.meta.url);
const backlog = JSON.parse(await readFile(new URL('docs/issues/backlog.json', root), 'utf8'));
const publish = process.argv.includes('--publish');
if (process.argv.slice(2).some(arg => arg !== '--publish')) {
  throw new Error('Usage: node scripts/publish-issues.mjs [--publish]');
}
if (!publish) {
  for (const issue of backlog.issues) console.log(`${issue.id}: ${issue.title} (${issue.phase}, ${issue.priority})`);
  console.log(`Dry run: ${backlog.issues.length} issues; no network requests or changes.`);
  process.exit(0);
}

// Use the normal Git credential helper; never print or persist its output.
let token = process.env.GH_TOKEN || process.env.GITHUB_TOKEN;
if (!token) {
  const credential = spawnSync('git', ['credential', 'fill'], {
    input: 'protocol=https\nhost=github.com\n\n', encoding: 'utf8',
    env: { ...process.env, GIT_TERMINAL_PROMPT: '0', GCM_INTERACTIVE: 'never' },
  });
  if (credential.status === 0) token = credential.stdout.match(/^password=(.+)$/m)?.[1].trim();
}
if (!token) throw new Error('GitHub authentication unavailable. Sign in with Git Credential Manager or set GH_TOKEN locally.');

const api = `https://api.github.com/repos/${backlog.repository}`;
async function request(path, method = 'GET', body) {
  const response = await fetch(`${api}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'IHSGHAH-backlog',
      'Content-Type': 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(30000),
  });
  if (!response.ok) throw new Error(`GitHub ${method} ${path}: HTTP ${response.status}. Check repository access and token permissions.`);
  return response.json();
}

// Read open AND closed issues across every page before making any changes.
const existing = [];
for (let page = 1; ; page++) {
  const items = await request(`/issues?state=all&per_page=100&page=${page}`);
  existing.push(...items.filter(item => !item.pull_request));
  if (items.length < 100) break;
}
const published = new Map();
for (const issue of backlog.issues) {
  const marker = `<!-- saham-signal:${issue.id} -->`;
  const matches = existing.filter(item => item.body?.includes(marker) || item.title.startsWith(`[${issue.id}] `));
  if (matches.length > 1) throw new Error(`Duplicate ${issue.id}; resolve manually before publishing.`);
  let result = matches[0];
  if (!result) {
    const body = await readFile(new URL(issue.file, root), 'utf8');
    const dependencies = issue.depends_on.map(id => {
      const dependency = published.get(id);
      if (!dependency) throw new Error(`Dependency ${id} must precede ${issue.id}.`);
      return `- ${id}: #${dependency.number}`;
    });
    result = await request('/issues', 'POST', {
      title: `[${issue.id}] ${issue.title}`,
      body: `${marker}\n\n${body}\n\n## Dependency GitHub\n\n${dependencies.join('\n') || 'Tidak ada.'}\n`,
    });
    // A failed request stops the run. Rerun discovers successfully created issues.
    console.log(`Created ${issue.id}: ${result.html_url}`);
  } else {
    console.log(`Exists ${issue.id}: ${result.html_url}`);
  }
  published.set(issue.id, result);
}
console.log(`Verified ${published.size} backlog issues. Existing issues were not modified.`);

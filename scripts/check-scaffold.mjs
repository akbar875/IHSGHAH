import assert from 'node:assert/strict';
import { readFile, readdir, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const backlog = JSON.parse(await readFile(path.join(root, 'docs/issues/backlog.json'), 'utf8'));
assert.equal(backlog.repository, 'akbar875/IHSGHAH');
assert.ok(backlog.issues.length > 0);
const seen = new Set();
for (const issue of backlog.issues) {
  assert.match(issue.id, /^SS-\d{3}$/);
  assert.ok(!seen.has(issue.id), `Duplicate ${issue.id}`);
  for (const dependency of issue.depends_on) assert.ok(seen.has(dependency), `${issue.id}: dependency must precede issue: ${dependency}`);
  assert.ok(['P0', 'P1', 'P2'].includes(issue.priority));
  assert.ok(issue.title && issue.phase && issue.branch);
  assert.ok(issue.file.startsWith('docs/issues/') && !issue.file.includes('..'));
  const body = await readFile(path.join(root, issue.file), 'utf8');
  for (const heading of ['## Tujuan', '## Scope', '## Acceptance criteria', '## Dependency', '## Referensi PRD', '## Branch']) {
    assert.ok(body.includes(heading), `${issue.id}: missing ${heading}`);
  }
  assert.ok(body.includes('- [ ]'), `${issue.id}: no acceptance checklist`);
  seen.add(issue.id);
}

// Check relative Markdown document links, including anchors and URL-encoded paths.
async function checkLinks(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (['.git', 'node_modules', '.venv'].includes(entry.name)) continue;
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory()) await checkLinks(filename);
    else if (entry.name.endsWith('.md')) {
      const contents = await readFile(filename, 'utf8');
      for (const match of contents.matchAll(/\]\(([^)]+)\)/g)) {
        const target = match[1].split('#')[0];
        if (!target || /^[a-z][a-z\d+.-]*:/i.test(target)) continue;
        await stat(path.resolve(path.dirname(filename), decodeURIComponent(target)));
      }
    }
  }
}
await checkLinks(root);
console.log(`Scaffold valid: ${seen.size} issues, ordered dependencies, issue bodies, and local Markdown links.`);

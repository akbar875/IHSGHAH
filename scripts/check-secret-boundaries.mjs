import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';

// Browser code may use only this reviewed, non-secret environment variable.
const allowed = new Set(['NEXT_PUBLIC_API_BASE_URL']);
async function inspect(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const location = new URL(`${entry.name}${entry.isDirectory() ? '/' : ''}`, directory);
    if (entry.isDirectory()) await inspect(location);
    else if (/\.[cm]?[jt]sx?$/.test(entry.name)) {
      const source = await readFile(location, 'utf8');
      for (const match of source.matchAll(/process\s*\.\s*env\b([^\n;]*)/g)) {
        const variable = match[1].match(/^\s*\.\s*([A-Z_][A-Z0-9_]*)\b/);
        assert.ok(variable && allowed.has(variable[1]), `Unreviewed environment access: ${location}`);
      }
      assert.ok(!/import\.meta\.env|saham_signal|MARKET_DATA_API_KEY|SESSION_SECRET|MARKET_FIXTURE_TOKEN/.test(source),
        `Server secret boundary crossed: ${location}`);
    }
  }
}
await inspect(new URL('../apps/web/src/', import.meta.url));
console.log('Web secret boundary valid: reviewed public environment only.');

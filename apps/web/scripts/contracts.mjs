import { readFile, writeFile } from 'node:fs/promises';
import { compile } from 'json-schema-to-typescript';

const schema = JSON.parse(await readFile(new URL('../../../packages/contracts/v1/schema.json', import.meta.url), 'utf8'));
const output = await compile({ ...schema.$defs.CandidatesResponse, $defs: schema.$defs }, 'CandidatesResponse', {
  bannerComment: '/* Generated from packages/contracts/v1/schema.json. Run npm run contracts. */',
  unreachableDefinitions: false,
  enableConstEnums: false,
  format: false,
  maxItems: -1,
});
const target = new URL('../src/lib/generated/candidates.d.ts', import.meta.url);
// Bundle only public candidate definitions, with no unrelated internal contracts.
const definitions = {};
function visit(value) {
  if (!value || typeof value !== 'object') return;
  if (value.$ref) {
    const name = value.$ref.replace('#/$defs/', '');
    if (!(name in definitions)) {
      definitions[name] = schema.$defs[name];
      visit(definitions[name]);
    }
  }
  for (const child of Object.values(value)) visit(child);
}
visit({ $ref: '#/$defs/CandidatesResponse' });
const runtime = JSON.stringify({ $schema: schema.$schema, $ref: '#/$defs/CandidatesResponse', $defs: definitions }, null, 2) + '\n';
for (const [url, content] of [[target, output], [new URL('../src/lib/generated/candidates.schema.json', import.meta.url), runtime]]) {
  if (process.argv.includes('--check')) {
    if (await readFile(url, 'utf8') !== content) throw new Error('Generated contracts are stale: run npm run contracts');
  } else await writeFile(url, content);
}

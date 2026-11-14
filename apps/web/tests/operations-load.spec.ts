import { randomUUID } from 'node:crypto';
import { writeFile } from 'node:fs/promises';
import { performance } from 'node:perf_hooks';
import { test, expect } from '@playwright/test';
import fixture from '../../../services/api/src/saham_signal/fixtures/market-simulation.json';

test('pilot browser consumes 100 simulated candidates within the 2s p95 budget', async ({ page }, testInfo) => {
  test.setTimeout(90000);
  let cycle = 0;
  let received = 0;
  const samples: number[] = [];
  await page.route('**/api/v1/settings/profile', route => route.fulfill({ status: 404, json: {} }));
  await page.route('**/api/v1/candidates?*', async route => {
    const response = structuredClone(fixture.CandidatesResponse);
    const at = new Date().toISOString();
    const until = new Date(Date.now() + 1800000).toISOString();
    response.as_of = at;
    response.data = Array.from({ length: 100 }, (_, index) => ({
      ...structuredClone(response.data[0]),
      signal_id: randomUUID(), symbol: index === 0 ? `C${cycle}` : `S${index.toString().padStart(3, '0')}`,
      generated_at: at, data_as_of: at, entry_from: at,
      entry_until: until, valid_until: until, exit_deadline: until,
    }));
    // The fixture API boundary stands in for received_at. No vendor/network SLA is inferred.
    received = performance.now();
    await route.fulfill({ json: response });
  });
  await page.goto('/');
  for (cycle = 0; cycle < 20; cycle++) {
    if (cycle > 0) await page.getByRole('button', { name: 'Terapkan' }).click();
    await expect(page.getByRole('article', { name: `Kandidat C${cycle}`, exact: true })).toBeVisible();
    await expect(page.getByRole('article')).toHaveCount(100);
    await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    samples.push(performance.now() - received);
  }
  const p95 = [...samples].sort((a, b) => a - b)[18];
  const evidence = {
    data_origin: 'simulation', users: 1, candidates: 100, snapshots: 20,
    boundary: 'mock_received_at_to_browser_two_animation_frames',
    p95_ms: p95, samples_ms: samples, vendor_sla_tested: false,
    automatic_polling_tested: false,
  };
  await writeFile(testInfo.outputPath('operations-load.json'), JSON.stringify(evidence, null, 2));
  await testInfo.attach('operations-load', { body: JSON.stringify(evidence), contentType: 'application/json' });
  expect(p95).toBeLessThanOrEqual(2000);
});

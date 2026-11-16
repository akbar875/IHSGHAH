import { expect, test } from '@playwright/test';

const result = {
  method: 'ma-rsi-momentum-2r-v1', latest_date: '2026-11-13', available_at: '2026-11-16T02:00:00Z',
  stale: false, needs_reimport: false, universe_count: 100,
  source: 'https://dataset.aethereal.top/datasets/idx-stock-features',
  license_url: 'https://creativecommons.org/licenses/by/4.0/', attribution: 'Synthetic UI test data.',
  rows: [
    { symbol: 'BULL', date: '2026-11-13', direction: 'bullish', reference: '1000', take_profit: '1100', stop_loss: '950', potential_pct: '10', risk_pct: '5', reward_risk: '2', rsi_14: '60', momentum_20d_pct: '12' },
    { symbol: 'BEAR', date: '2026-11-13', direction: 'bearish', reference: '1000', take_profit: '900', stop_loss: '1050', potential_pct: '-10', risk_pct: '5', reward_risk: '2', rsi_14: '40', momentum_20d_pct: '-12' },
  ],
};

test('home shows directional targets, filters and readable mobile layout', async ({ page }) => {
  await page.route('**/api/research/screener', route => route.fulfill({ json: result }));
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto('/');
  await expect(page.getByRole('status')).toHaveText('Analisis selesai.');
  await expect(page.locator('article')).toHaveCount(2);
  await expect(page.locator('article').first()).toContainText('+10.00%');
  await expect(page.locator('article').first()).toContainText('Take profit');
  await expect(page.locator('article').last()).toContainText('Batas invalidasi');
  await page.getByRole('button', { name: '↘ Bearish' }).click();
  await expect(page.locator('article')).toHaveCount(1);
  await expect(page.locator('article')).toContainText('BEAR');
  await page.getByLabel('Cari saham').fill('BULL');
  await expect(page.locator('article')).toHaveCount(0);
  await expect(page.getByText('Belum ada saham yang memenuhi kriteria.')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('refresh failure clears the previous targets', async ({ page }) => {
  let failed = false;
  await page.route('**/api/research/screener', route => failed ? route.fulfill({ status: 503 }) : route.fulfill({ json: result }));
  await page.goto('/');
  await expect(page.locator('article')).toHaveCount(2);
  failed = true;
  await page.getByRole('button', { name: 'Perbarui analisis' }).click();
  await expect(page.getByRole('status')).toContainText('Data belum tersedia');
  await expect(page.locator('article')).toHaveCount(0);
});

for (const variant of ['inverted', 'stale', 'fabricated-percent']) {
  test(`rejects ${variant} targets`, async ({ page }) => {
    const invalid = structuredClone(result);
    if (variant === 'inverted') invalid.rows[0].take_profit = '900';
    if (variant === 'stale') invalid.stale = true;
    if (variant === 'fabricated-percent') invalid.rows[0].potential_pct = '50';
    await page.route('**/api/research/screener', route => route.fulfill({ json: invalid }));
    await page.goto('/');
    await expect(page.getByRole('status')).toContainText('tidak valid');
    await expect(page.locator('article')).toHaveCount(0);
  });
}

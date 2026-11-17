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
  await expect(page.getByText('Tidak ada kandidat yang cocok dengan filter.')).toBeVisible();
  await page.getByRole('button', { name: 'Reset pencarian & filter' }).click();
  await expect(page.locator('article')).toHaveCount(2);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('unauthenticated visitors get an actionable session flow and can return to stocks', async ({ page }) => {
  let activated = false;
  await page.setViewportSize({ width: 360, height: 800 });
  await page.route('**/api/research/screener', route => activated ? route.fulfill({ json: result }) : route.fulfill({ status: 401 }));
  await page.route('**/api/research/session', async route => {
    expect(route.request().postDataJSON()).toEqual({ token: 'administrator-issued-code' });
    activated = true;
    await route.fulfill({ status: 204 });
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Aktifkan akses untuk melihat saham' })).toBeVisible();
  await expect(page.getByText('Sesi belum aktif', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Cari saham')).toBeDisabled();
  await page.screenshot({ path: '../../.work/screener-access-mobile.png', fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('link', { name: 'Aktifkan sesi research →' }).click();
  await page.getByLabel('Kode akses research').fill('administrator-issued-code');
  await page.getByRole('button', { name: 'Aktifkan & lihat saham' }).click();
  await expect(page).toHaveURL('/');
  await expect(page.locator('article')).toHaveCount(2);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.screenshot({ path: '../../.work/screener-ready-desktop.png', fullPage: true });
});

test('invalid session code gives a recoverable error without storing the code', async ({ page }) => {
  await page.route('**/api/research/session', route => route.fulfill({ status: 401 }));
  await page.goto('/access');
  await page.getByLabel('Kode akses research').fill('invalid-code');
  await page.getByRole('button', { name: 'Aktifkan & lihat saham' }).click();
  await expect(page.getByRole('status')).toContainText('Kode akses tidak valid');
  await expect(page.getByLabel('Kode akses research')).toHaveValue('');
  expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
});

test('loaded snapshot without candidates offers all daily stocks', async ({ page }) => {
  await page.route('**/api/research/screener', route => route.fulfill({ json: { ...result, rows: [] } }));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Belum ada saham yang memenuhi kriteria.' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Jelajahi semua saham →' })).toHaveAttribute('href', '/research');
  await expect(page.getByRole('heading', { name: 'Aktifkan akses untuk melihat saham' })).toHaveCount(0);
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

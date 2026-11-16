import { expect, test } from '@playwright/test';

const snapshot = {
  mode: 'research', origin: 'market', frequency: 'daily', provider: 'Aethereal', license: 'CC BY 4.0',
  source: 'https://dataset.aethereal.top/datasets/idx-stock-features', license_url: 'https://creativecommons.org/licenses/by/4.0/',
  attribution: 'Aethereal (2026), IDX Stock Features; synthetic test values for layout verification.',
  available_at: '2026-11-16T02:00:00Z', latest_date: '2026-11-13', stale: false, signals_enabled: false, sha256: 'a'.repeat(64),
  quality: { rows: 4, accepted_rows: 3, rejected_rows: 1, published_symbols: 2 },
  rows: [
    { symbol: 'SIM', date: '2026-11-13', close_idr: '1000.00', volume: '10000', return_1d: '0.01', rsi_14: '55', stale: false },
    { symbol: 'ZERO', date: '2026-11-06', close_idr: '500', volume: '0', return_1d: null, rsi_14: null, stale: true },
  ],
};

test('daily real-origin research shows attribution, dates and nullable indicators at 360px', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.route('**/api/research/eod', route => route.fulfill({ json: snapshot }));
  await page.goto('/research');
  await expect(page.getByRole('status')).toContainText('Data pasar harian tersedia');
  await expect(page.getByRole('region', { name: 'Batas penggunaan' })).toContainText('Sinyal intraday');
  await expect(page.getByRole('list', { name: 'Data saham harian' })).toContainText('1.00%');
  await expect(page.getByRole('list', { name: 'Data saham harian' })).toContainText('Belum tersedia');
  await expect(page.getByRole('region', { name: 'Sumber dan kualitas' })).toContainText('CC BY 4.0');
  await expect(page.getByRole('region', { name: 'Sumber dan kualitas' })).toContainText('lebih dari 7 hari');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '../../.work/free-eod-mobile.png', fullPage: true });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.screenshot({ path: '../../.work/free-eod-desktop.png', fullPage: true });
  await page.getByLabel('Cari kode saham').fill('sim');
  await expect(page.getByRole('list', { name: 'Data saham harian' }).locator('li')).toHaveCount(1);
  await page.getByLabel('Cari kode saham').fill('XXXX');
  await expect(page.getByText('Tidak ada saham yang cocok.')).toBeVisible();
});

test('daily outage clears prior data and never substitutes simulation', async ({ page }) => {
  let failed = false;
  await page.route('**/api/research/eod', route => failed ? route.fulfill({ status: 503 }) : route.fulfill({ json: snapshot }));
  await page.goto('/research');
  await expect(page.getByRole('status')).toContainText('tersedia');
  failed = true;
  await page.getByRole('button', { name: 'Muat ulang data harian' }).click();
  await expect(page.getByRole('status')).toContainText('Jalankan import');
  await expect(page.getByRole('list', { name: 'Data saham harian' })).toHaveCount(0);
});

for (const variant of ['simulation', 'wrong-mode', 'infinite-price', 'duplicate', 'enabled-signal']) {
  test(`daily rejects ${variant}`, async ({ page }) => {
    const invalid = structuredClone(snapshot);
    if (variant === 'simulation') invalid.origin = 'simulation';
    if (variant === 'wrong-mode') invalid.mode = 'paper';
    if (variant === 'infinite-price') invalid.rows[0].close_idr = 'Infinity';
    if (variant === 'duplicate') invalid.rows[1].symbol = 'SIM';
    if (variant === 'enabled-signal') invalid.signals_enabled = true;
    await page.route('**/api/research/eod', route => route.fulfill({ json: invalid }));
    await page.goto('/research');
    await expect(page.getByRole('status')).toContainText('tidak valid');
    await expect(page.getByRole('list', { name: 'Data saham harian' })).toHaveCount(0);
  });
}

test('daily requires an authenticated research session', async ({ page }) => {
  await page.route('**/api/research/eod', route => route.fulfill({ status: 401 }));
  await page.goto('/research');
  await expect(page.getByRole('status')).toContainText('Sesi admin research diperlukan');
});

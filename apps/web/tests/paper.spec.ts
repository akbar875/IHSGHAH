import { test, expect } from '@playwright/test';

const result = { mode: 'paper', origin: 'simulation', paper_live_enabled: false, receipt: {
  mode: 'paper', origin: 'simulation', as_of: '2026-11-13T03:00:00Z',
  actual_fills: [], paper_fills: [{ side: 'buy' }], paper_positions: { SIM: 100 },
  readiness: { paper_live_enabled: false },
} };

test('paper report separates simulation and actual fills at 360px', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.route('**/api/ops/paper', route => route.fulfill({ json: result }));
  await page.goto('/paper');
  await expect(page.getByRole('region', { name: 'Hasil simulasi paper' })).toContainText('100');
  await expect(page.getByRole('region', { name: 'Fill aktual' })).toContainText('terpisah');
  await expect(page.getByRole('region', { name: 'Status observasi' })).toContainText('Paper live belum dimulai');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '../../.work/issue26-mobile.png', fullPage: true });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.screenshot({ path: '../../.work/issue26-desktop.png', fullPage: true });
});

test('paper report clears previous data on outage and rejects mixed fills', async ({ page }) => {
  let variant = 0;
  await page.route('**/api/ops/paper', route => variant === 0 ? route.fulfill({ json: result }) : variant === 1 ? route.fulfill({ status: 503 }) : route.fulfill({ json: { ...result, receipt: { ...result.receipt, ...(variant === 2 ? { actual_fills: [{}] } : { paper_positions: 100 }) } } }));
  await page.goto('/paper');
  await expect(page.getByRole('region', { name: 'Hasil simulasi paper' })).toBeVisible();
  variant = 1;
  await page.getByRole('button', { name: 'Muat ulang laporan' }).click();
  await expect(page.getByRole('status')).toContainText('belum tersedia');
  await expect(page.getByRole('region', { name: 'Hasil simulasi paper' })).toHaveCount(0);
  variant = 2;
  await page.getByRole('button', { name: 'Muat ulang laporan' }).click();
  await expect(page.getByRole('status')).toContainText('tidak valid');
  variant = 3;
  await page.getByRole('button', { name: 'Muat ulang laporan' }).click();
  await expect(page.getByRole('status')).toContainText('tidak valid');
  await expect(page.getByRole('region', { name: 'Hasil simulasi paper' })).toHaveCount(0);
});

test('paper report distinguishes missing receipt and unsigned session', async ({ page }) => {
  await page.route('**/api/ops/paper', route => route.fulfill({ json: { ...result, receipt: null } }));
  await page.goto('/paper');
  await expect(page.getByRole('status')).toContainText('Belum ada laporan');
  await page.unroute('**/api/ops/paper');
  await page.route('**/api/ops/paper', route => route.fulfill({ status: 401 }));
  await page.getByRole('button', { name: 'Muat ulang laporan' }).click();
  await expect(page.getByRole('status')).toContainText('Sesi admin paper diperlukan');
});

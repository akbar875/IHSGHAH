import { test, expect } from '@playwright/test';
import receipt from '../../../research/reports/SS-026-acceptance.json';

const titles = ['Feed putus', 'Heartbeat saham sepi', 'Nominal dan likuiditas', 'ARA tanpa penjual',
  'ARB tanpa pembeli', 'Berita terlambat', 'Reconnect/out-of-order', 'Partial fill',
  'Riwayat/proyeksi', 'Tekanan transaksi', 'Versi dan deduplikasi', 'Mobile 360px'];

const result = { mode: 'paper', origin: 'simulation', paper_live_enabled: false, receipt: {
  mode: 'paper', origin: 'simulation', as_of: '2026-11-13T03:00:00Z',
  actual_fills: [], paper_fills: [{ side: 'buy' }], paper_positions: { SIM: 100 },
  readiness: { paper_live_enabled: false },
}, acceptance: {
  acceptance_passed: true, can_advance: false, reasons: ['G0_NOT_PASSED', 'G1_NOT_PASSED'],
  gates: { G0: { decision: 'pending' }, G1: { decision: 'no-go' } },
  scenarios: receipt.scenarios.map((scenario, i) => ({ ...scenario, title: titles[i] })),
}, fill_reports: { combined_pnl: null, actual: {
  source: 'manual_position_events', source_mode: 'paper', origin: 'manual', available: true,
  fill_count: 3, buy_lots: 4, sell_lots: 1, remaining_lots: 3, realized_pnl_idr: '50.00',
} } };

test('paper report separates simulation and actual fills at 360px', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.route('**/api/ops/paper', route => route.fulfill({ json: result }));
  await page.goto('/paper');
  await expect(page.getByRole('region', { name: 'Hasil simulasi paper' })).toContainText('100');
  await expect(page.getByRole('region', { name: 'Fill aktual' })).toContainText('terpisah');
  await expect(page.getByRole('region', { name: 'Fill aktual' })).toContainText('4 / 1');
  await expect(page.getByRole('region', { name: 'Acceptance PRD 14' })).toContainText('12/12');
  await expect(page.getByRole('region', { name: 'Status observasi' })).toContainText('Paper live belum dimulai');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '../../.work/issue26-mobile.png', fullPage: true });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.screenshot({ path: '../../.work/issue26-desktop.png', fullPage: true });
});

test('critical acceptance failure holds progression despite paper fills', async ({ page }) => {
  const failed = structuredClone(result);
  failed.acceptance.acceptance_passed = false;
  failed.acceptance.scenarios[6].status = 'blocked';
  failed.acceptance.scenarios[6].evidence[0].status = 'blocked';
  failed.acceptance.reasons = ['CRITICAL_ACCEPTANCE_INCOMPLETE'];
  await page.route('**/api/ops/paper', route => route.fulfill({ json: failed }));
  await page.goto('/paper');
  await expect(page.getByRole('region', { name: 'Acceptance PRD 14' })).toContainText('11/12');
  await expect(page.getByRole('region', { name: 'Gerbang dan kemajuan' })).toContainText('Kemajuan ditahan');
  await expect(page.getByRole('region', { name: 'Gerbang dan kemajuan' })).toContainText('skenario kritis');
  await expect(page.getByRole('region', { name: 'Fill aktual' })).toContainText('50.00');
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

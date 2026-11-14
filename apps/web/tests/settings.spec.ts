import { test, expect, type Page } from '@playwright/test';
import fixture from '../../../services/api/src/saham_signal/fixtures/market-simulation.json';
import type { RiskProfile } from '../src/lib/generated/candidates';

const base = { ...fixture.CandidatesResponse, data: undefined };
function initial(): RiskProfile {
  return { configuration_version: 'config-test', nominal_idr: '1000000.00', capital_idr: '10000000.00', risk_per_position_ratio: '0.005000',
    max_combined_risk_ratio: '0.020000', max_positions: 3, fee_schedule_version: 'fee-test', fee_schedule: { version: 'fee-test',
      buy_ratio: '0.001500', sell_ratio: '0.002500', effective_from: '2026-11-01T00:00:00Z', effective_to: '2026-12-01T00:00:00Z',
      source: 'Asumsi pengguna untuk uji UI', verification: 'user_assumption' } };
}
async function mock(page: Page, risk: RiskProfile | null = null) {
  let saved = risk;
  let symbols: string[] = [];
  await page.route('**/api/v1/settings/profile', async route => {
    if (route.request().method() === 'PUT') {
      saved = route.request().postDataJSON();
      expect(route.request().headers()['idempotency-key']).toBeTruthy();
    }
    await route.fulfill(saved ? { json: { ...base, data: saved } } : { status: 404, json: {} });
  });
  await page.route('**/api/v1/watchlist', async route => {
    if (route.request().method() === 'PUT') symbols = route.request().postDataJSON().symbols;
    await route.fulfill({ json: { ...base, data: { symbols } } });
  });
  await page.route('**/api/v1/settings/eligibility', route => route.fulfill(saved ? { json: { ...base, data: {
    configuration_version: saved.configuration_version, risk_budget_idr: '50000.00', combined_budget_idr: '200000.00',
    budget_lots_ceiling: Number(saved.nominal_idr) < 1000000 ? 1 : 9, eligible_lots: 0, reason: 'MODEL_UNVALIDATED',
  } } } : { status: 404, json: {} }));
  await page.route('**/api/v1/candidates?*', route => {
    const value = structuredClone(fixture.CandidatesResponse);
    value.as_of = new Date().toISOString();
    value.data[0].assumptions.nominal_idr = saved?.nominal_idr ?? '1000000.00';
    value.data[0].valid_until = value.data[0].entry_until = new Date(Date.now() + 1800000).toISOString();
    return route.fulfill({ json: value });
  });
}

test('unconfigured profile is blank; watchlist persists through reload and removal', async ({ page }) => {
  await mock(page); await page.goto('/settings');
  await expect(page.getByLabel('Modal (Rp)', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('Biaya beli (rasio)')).toHaveValue('');
  await expect(page.getByText('Watchlist kosong.')).toBeVisible();
  await page.getByLabel('Tambah kode saham').fill('test');
  await page.getByRole('button', { name: 'Tambah', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Hapus TEST' })).toBeVisible();
  await page.reload(); await expect(page.getByRole('button', { name: 'Hapus TEST' })).toBeVisible();
  await page.getByRole('button', { name: 'Hapus TEST' }).click();
  await expect(page.getByText('Watchlist kosong.')).toBeVisible();
});

test('risk and dated user assumptions save, recalculate and reach dashboard', async ({ page }) => {
  await mock(page, initial()); await page.goto('/settings');
  await expect(page.getByLabel('Nominal transaksi (Rp)', { exact: true })).toHaveValue('1000000.00');
  await page.getByLabel('Nominal transaksi (Rp)', { exact: true }).fill('200000');
  await page.getByRole('button', { name: 'Simpan pengaturan', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Pengaturan tersimpan');
  await expect(page.getByRole('region', { name: 'Kelayakan simulasi' })).toContainText('Batas lot menurut anggaran: 1');
  await page.reload(); await expect(page.getByLabel('Nominal transaksi (Rp)', { exact: true })).toHaveValue('200000.00');
  await page.getByRole('link', { name: '← Kembali ke kandidat' }).click();
  await expect(page.getByText('Nominal tersimpan:')).toContainText('200.000');
  await expect(page.getByRole('article')).toContainText('200.000');
});

test('invalid decimal and duplicate ticker rejected without replacing saved data', async ({ page }) => {
  await mock(page, initial()); await page.goto('/settings');
  await expect(page.getByLabel('Biaya beli (rasio)')).toHaveValue('0.001500');
  await page.getByLabel('Biaya beli (rasio)').fill('NaN');
  await page.getByRole('button', { name: 'Simpan pengaturan' }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Gunakan angka positif');
  await page.getByLabel('Tambah kode saham').fill('TEST'); await page.getByRole('button', { name: 'Tambah', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Hapus TEST' })).toBeVisible();
  await page.getByLabel('Tambah kode saham').fill('TEST'); await page.getByRole('button', { name: 'Tambah', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('duplikat');
});

test('failed load disables writes and retry recovers', async ({ page }) => {
  await mock(page);
  await page.route('**/api/v1/watchlist', route => route.fulfill({ status: 503, json: {} }));
  await page.goto('/settings');
  await expect(page.getByRole('main').getByRole('alert')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Simpan pengaturan' })).toBeDisabled();
  await page.unroute('**/api/v1/watchlist');
  await page.route('**/api/v1/watchlist', route => route.fulfill({ json: { ...base, data: { symbols: [] } } }));
  await page.getByRole('button', { name: 'Muat ulang' }).click();
  await expect(page.getByRole('button', { name: 'Simpan pengaturan' })).toBeEnabled();
});

test('failed save retains fields and exposes safe validation error', async ({ page }) => {
  await mock(page, initial()); await page.goto('/settings');
  await expect(page.getByLabel('Modal (Rp)', { exact: true })).toHaveValue('10000000.00');
  await page.route('**/api/v1/settings/profile', route => route.fulfill({ status: 422, json: {} }));
  await page.getByRole('button', { name: 'Simpan pengaturan' }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Input ditolak');
  await expect(page.getByLabel('Modal (Rp)', { exact: true })).toHaveValue('10000000.00');
});

for (const width of [1280, 360]) test(`settings accessible at ${width}px without overflow`, async ({ page }) => {
  await page.setViewportSize({ width, height: 900 });
  await mock(page, initial()); await page.goto('/settings');
  await expect(page.getByLabel('Biaya beli (rasio)')).toHaveValue('0.001500');
  await expect(page.getByText('Biaya adalah asumsi pengguna')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: `../../docs/screenshots/SS-020-${width === 360 ? 'mobile' : 'desktop'}.png`, fullPage: true });
});


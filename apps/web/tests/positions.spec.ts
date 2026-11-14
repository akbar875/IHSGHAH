import { test, expect, type Page } from '@playwright/test';
import fixture from '../../../services/api/src/saham_signal/fixtures/market-simulation.json';
import type { Position } from '../src/lib/generated/candidates';

const base = { ...fixture.CandidatesResponse, data: undefined };
async function mock(page: Page, failFirst = false) {
  let current: Position | null = null;
  let commands = 0;
  let key = '';
  await page.route('**/api/v1/positions**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (request.method() === 'GET') {
      const data = url.pathname.endsWith('/monitor') ? { position: current, plan: null, invested_idr: '200300.00', remaining_cost_idr: '200300.00', realized_pnl_idr: '0.00', stop_loss_idr: null, target_net_idr: null, exit_reason: current?.status === 'EXIT_REQUESTED' ? 'STOP' : null } : (url.pathname.endsWith('/positions') ? (current ? [current] : []) : current);
      return route.fulfill({ json: { ...base, data } });
    }
    const body = request.postDataJSON();
    commands++;
    if (url.pathname.endsWith('/positions')) {
      if (!key) key = request.headers()['idempotency-key'];
      else expect(request.headers()['idempotency-key']).toBe(key);
      current = { position_id: 'manual-1', user_id: 'pilot', symbol: body.symbol, fills: [{ ...body.fill, fill_id: 'fill-1', position_id: 'manual-1', recorded_at: body.fill.filled_at, origin: 'manual' }], remaining_lots: body.fill.lots, average_price_idr: body.fill.price_idr, fees_idr: body.fill.fees_idr, opened_at: body.fill.filled_at, status: 'OPEN', plan_version: 1, overnight_risk: false };
      if (failFirst && commands === 1) return route.abort();
    } else if (url.pathname.endsWith('/exit-request')) {
      current!.status = 'EXIT_REQUESTED';
    } else if (url.pathname.endsWith('/fills')) {
      current!.remaining_lots -= body.lots;
      current!.status = current!.remaining_lots === 0 ? 'CLOSED' : 'EXIT_REQUESTED';
      current!.fills.push({ ...body, fill_id: `fill-${commands}`, position_id: 'manual-1', recorded_at: body.filled_at, origin: 'manual' });
    }
    return route.fulfill({ json: { ...base, data: current } });
  });
}
async function fill(page: Page) {
  await page.getByLabel('Kode saham').fill('TEST');
  await page.getByLabel('Harga rata-rata fill (Rp)').fill('1000');
  await page.getByLabel('Lot aktual').fill('2');
  await page.getByLabel('Biaya total aktual (Rp)').fill('300');
  await page.getByLabel('Waktu fill (WIB)').fill('2026-11-14T09:00');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Simpan fill terkonfirmasi' }).click();
}

test('confirmed fill, exit without sale, partial sell and reload', async ({ page }) => {
  await mock(page); await page.goto('/positions');
  await expect(page.getByText('Belum ada fill yang dicatat.')).toBeVisible();
  await fill(page);
  await expect(page.getByRole('heading', { name: 'TEST · OPEN', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Minta exit: STOP' }).click();
  await expect(page.getByText('Sisa 2 lot', { exact: false })).toBeVisible();
  await page.getByLabel('Sisi fill').selectOption('SELL');
  await page.getByLabel('Lot aktual').fill('1');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Simpan fill terkonfirmasi' }).click();
  await expect(page.getByText('Sisa 1 lot', { exact: false })).toBeVisible();
  await page.reload();
  await page.getByRole('button', { name: 'TEST · 1 lot · EXIT_REQUESTED' }).click();
  await expect(page.getByText('SELL 1 lot', { exact: false })).toBeVisible();
});

test('lost response retains idempotency key on unchanged retry', async ({ page }) => {
  await mock(page, true); await page.goto('/positions'); await fill(page);
  await expect(page.locator('p[role=alert]')).toBeVisible();
  await page.getByRole('button', { name: 'Simpan fill terkonfirmasi' }).click();
  await expect(page.getByRole('heading', { name: 'TEST · OPEN', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'TEST · 2 lot · OPEN' })).toHaveCount(1);
});

test('360px layout and loading failure', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await mock(page); await page.goto('/positions'); await fill(page);
  await expect(page.getByRole('heading', { name: 'TEST · OPEN', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: '../../docs/screenshots/SS-021-mobile.png', fullPage: true });
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.screenshot({ path: '../../docs/screenshots/SS-021-desktop.png', fullPage: true });
  await page.unrouteAll(); await page.route('**/api/v1/positions', route => route.fulfill({ status: 503, json: {} }));
  await page.reload(); await expect(page.locator('p[role=alert]')).toContainText('Posisi belum dapat');
});

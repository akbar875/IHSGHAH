import { test, expect, type Page } from '@playwright/test';
import fixture from '../../../services/api/src/saham_signal/fixtures/market-simulation.json';
import type { Alert } from '../src/lib/generated/candidates';

const alert: Alert = {
  event_id: 'stop-1', user_id: 'pilot', signal_id: null, position_id: 'position-1',
  type: 'STOP', created_at: '2026-11-14T03:00:00Z', delivered_at: null,
  status: 'pending', channel: 'in_app', dedup_key: 'stop-1',
};
const response = (data: Alert[]) => ({ ...fixture.CandidatesResponse, data });
async function mock(page: Page) {
  await page.route('**/api/v1/alerts', route => route.fulfill({ json: response([
    { ...alert, event_id: 'entry-1', dedup_key: 'entry-1', type: 'ENTRY_READY', signal_id: 'signal-1', position_id: null }, alert, alert,
  ]) }));
}

test('risk priority, exit semantics, retry and reload deduplicate inbox', async ({ page }) => {
  await mock(page); await page.goto('/alerts');
  const items = page.getByRole('list', { name: 'Daftar notifikasi' }).getByRole('listitem');
  await expect(items).toHaveCount(2);
  await expect(items.first().getByRole('heading')).toHaveText('Stop exit');
  await expect(page.getByText('Saat alert dibuat, fill jual untuk permintaan exit ini belum dikonfirmasi.', { exact: false })).toBeVisible();
  await expect(items.first().getByText('10.00.00 WIB', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Muat ulang notifikasi' }).click();
  await expect(items).toHaveCount(2);
  await page.reload(); await expect(items).toHaveCount(2);
});

test('offline retains inbox and reconnect replaces snapshot', async ({ page, context }) => {
  await mock(page); await page.goto('/alerts');
  const items = page.getByRole('listitem');
  await expect(items).toHaveCount(2);
  await context.setOffline(true);
  await expect(page.getByRole('status')).toContainText('Offline');
  await expect(items).toHaveCount(2);
  await context.setOffline(false);
  await expect(page.getByRole('status')).toContainText('Daftar diperbarui');
  await expect(items).toHaveCount(2);
});

test('wrong mode rejected, empty state and recovery after transport failure', async ({ page }) => {
  await page.route('**/api/v1/alerts', route => route.fulfill({ json: { ...response([alert]), mode: 'live' } }));
  await page.goto('/alerts');
  await expect(page.getByRole('status')).toContainText('Notifikasi ditolak');
  await expect(page.getByRole('listitem')).toHaveCount(0);
  await page.unroute('**/api/v1/alerts');
  await page.route('**/api/v1/alerts', route => route.abort());
  await page.getByRole('button', { name: 'Muat ulang notifikasi' }).click();
  await expect(page.getByRole('status')).toContainText('Daftar terakhir mungkin tertinggal');
  await page.unroute('**/api/v1/alerts');
  await page.route('**/api/v1/alerts', route => route.fulfill({ json: response([]) }));
  await page.getByRole('button', { name: 'Muat ulang notifikasi' }).click();
  await expect(page.getByRole('status')).toHaveText('Belum ada notifikasi.');
});

test('360px touch layout and screenshots', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await mock(page); await page.goto('/alerts');
  await expect(page.getByRole('heading', { name: 'Stop exit' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
  expect((await page.getByRole('button', { name: 'Muat ulang notifikasi' }).boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await page.screenshot({ path: '../../.work/issue22-mobile.png', fullPage: true });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.screenshot({ path: '../../.work/issue22-desktop.png', fullPage: true });
});

import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';

const bundled = JSON.parse(readFileSync(path.resolve('../../services/api/src/saham_signal/resources/idx-daily.json'), 'utf8'));
const snapshot = { ...bundled, as_of: new Date().toISOString(), stale: false, rows: bundled.rows.map((row: Record<string, unknown>) => ({ ...row, stale: false, history: undefined, backtest: undefined })) };

test.beforeEach(async ({ page }) => {
  await page.route('**/api/research/eod', r => r.fulfill({ json: snapshot }));
  await page.route('**/api/research/stocks/*', r => {
    const symbol = r.request().url().split('/').at(-1);
    const row = bundled.rows.find((row: { symbol: string }) => row.symbol === symbol);
    return r.fulfill({ json: { ...row, origin: 'market', feed: 'daily', as_of: snapshot.as_of, available_at: bundled.available_at, stale: false, plan: null, order_book: null, individual_queue: null, depth_status: 'feed_not_connected', source: bundled.source, license_url: bundled.license_url, attribution: bundled.attribution } });
  });
});

test('public home shows real bundled stocks and selecting a row switches the adjacent detail', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('list', { name: 'Saham tersedia' }).getByRole('listitem')).toHaveCount(bundled.rows.length);
  await expect(page.getByRole('heading', { name: 'BBCA', exact: true })).toBeVisible();
  await expect(page.getByRole('status')).toHaveText('Detail saham tersedia.');
  await expect(page.getByRole('button', { name: 'Lihat saham BBCA', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Lihat saham BBRI', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'BBRI', exact: true })).toBeVisible();
  await expect(page.getByRole('status')).toHaveText('Detail saham tersedia.');
  await expect(page.getByRole('img', { name: 'Chart harga penutupan', exact: false })).toBeVisible();
  await expect(page.getByLabel('Cari saham')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Akses research' })).toHaveCount(0);
  await page.screenshot({ path: '../../.work/stock-workspace-desktop.png', fullPage: true });
});

test('phone opens a selected stock and returns to the searchable list without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 820 });
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Lihat saham BBCA', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Chart harga & volume' })).not.toBeVisible();
  await page.getByLabel('Cari saham').fill('mandiri');
  await expect(page.getByRole('list', { name: 'Saham tersedia' }).getByRole('listitem')).toHaveCount(1);
  await page.getByRole('button', { name: 'Lihat saham BMRI', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'BMRI', exact: true })).toBeVisible();
  await expect(page.getByRole('status')).toHaveText('Detail saham tersedia.');
  await expect(page.getByRole('heading', { name: 'Chart harga & volume' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '../../.work/stock-workspace-mobile-detail.png', fullPage: true });
  await page.getByRole('button', { name: '← Daftar saham', exact: true }).click();
  await expect(page.getByLabel('Cari saham')).toBeVisible();
  await page.getByLabel('Cari saham').fill('ZZZZZZZZ');
  await expect(page.getByText('Tidak ada saham yang cocok.')).toBeVisible();
  await page.getByRole('button', { name: 'Reset pencarian', exact: true }).click();
  await expect(page.getByRole('list', { name: 'Saham tersedia' }).getByRole('listitem')).toHaveCount(bundled.rows.length);
  await page.screenshot({ path: '../../.work/stock-workspace-mobile-list.png', fullPage: true });
});

test('the former activation page opens the stock list directly', async ({ page }) => {
  await page.goto('/access');
  await expect(page).toHaveURL('/');
  await expect(page.getByRole('button', { name: 'Lihat saham BBCA', exact: true })).toBeVisible();
});

test('an unavailable API offers retry and removes the old list and stock detail', async ({ page }) => {
  let failed = false;
  await page.route('**/api/research/eod', r => failed ? r.fulfill({ status: 503 }) : r.fulfill({ json: snapshot }));
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Lihat saham BBCA', exact: true })).toBeVisible();
  failed = true;
  await page.getByRole('button', { name: 'Perbarui daftar saham', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Coba lagi', exact: true })).toBeVisible();
  await expect(page.getByRole('list', { name: 'Saham tersedia' }).getByRole('listitem')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'BBCA', exact: true })).toHaveCount(0);
});

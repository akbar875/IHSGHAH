import { test, expect, type Page } from '@playwright/test';
import fixture from '../../../services/api/src/saham_signal/fixtures/market-simulation.json';

function snapshots() {
  const result = structuredClone(fixture);
  const now = Date.now();
  const at = new Date(now).toISOString();
  const until = new Date(now + 1800000).toISOString();
  for (const response of Object.values(result)) response.as_of = at;
  const signal = result.StockDetailResponse.data.signal;
  signal.generated_at = signal.data_as_of = signal.entry_from = at;
  signal.entry_until = signal.valid_until = until;
  signal.exit_deadline = new Date(now + 3600000).toISOString();
  result.StockDetailResponse.data.depth.depth_as_of = at;
  result.ChartResponse.data.candles[0].at = at;
  result.SignalHistoryResponse.data = [structuredClone(signal)];
  return result;
}
async function mock(page: Page, value = snapshots()) {
  await page.route('**/api/v1/stocks/TEST**', route => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/chart')) {
      const chart = structuredClone(value.ChartResponse);
      const interval = url.searchParams.get('interval')!;
      chart.data.interval = interval;
      if (interval !== '1m') chart.data.candles = [];
      return route.fulfill({ json: chart });
    }
    return route.fulfill({ json: url.pathname.endsWith('/signals') ? value.SignalHistoryResponse : value.StockDetailResponse });
  });
}

test('detail displays canonical plan, candle, snapshot metadata and honest missing values', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await mock(page);
  await page.goto('/stocks/TEST');
  const plan = page.getByRole('region', { name: 'Rencana transaksi' });
  await expect(plan).toContainText('Rp 990');
  await expect(plan).toContainText('Rp 1.030');
  await expect(plan).toContainText('Horizon 30 menit');
  await expect(plan).toContainText('Nominal rencana layanan');
  await expect(page.getByRole('region', { name: 'Order book' })).toContainText('Kedalaman terbatas · 1 tingkat tersedia');
  await expect(page.getByRole('region', { name: 'Order book' })).toContainText('book-sim-1 · urutan 1');
  await expect(page.getByRole('region', { name: 'Order book' })).toContainText('Rp 10');
  await expect(page.getByRole('region', { name: 'Tekanan transaksi agresif' })).toContainText('5 menit · Beli / jual: Tidak tersedia · Cakupan klasifikasi: 0%');
  await expect(page.getByText('Proyeksi: Tidak tersedia', { exact: false })).toBeVisible();
  await expect(page.locator('.price-chart canvas').first()).toBeVisible();
  await expect(page.locator('body')).not.toContainText('sim-policy-1');
  await page.screenshot({ path: '../../.work/issue19-desktop.png', fullPage: true });
  expect(errors).toEqual([]);
});

test('interval change keeps horizon and does not synthesize missing candles', async ({ page }) => {
  await mock(page);
  await page.goto('/stocks/TEST');
  await expect(page.getByText('Horizon rencana: 30 menit.', { exact: false })).toBeVisible();
  for (const interval of ['5m', '15m', '1m']) {
    await page.getByRole('button', { name: interval, exact: true }).click();
    await expect(page.getByRole('button', { name: interval, exact: true })).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByText('Horizon rencana: 30 menit.', { exact: false })).toBeVisible();
    if (interval !== '1m') await expect(page.getByText(`Riwayat interval ${interval}: Tidak tersedia`)).toBeVisible();
    else await expect(page.getByText('Riwayat interval 1m: Tidak tersedia')).toHaveCount(0);
  }
});

test('full snapshot replacement removes old levels, failed refresh clears book', async ({ page }) => {
  const value = snapshots();
  await mock(page, value);
  await page.goto('/stocks/TEST');
  const book = page.getByRole('region', { name: 'Order book' });
  await expect(book).toContainText('book-sim-1');
  value.StockDetailResponse.data.depth.snapshot_id = 'book-sim-2';
  value.StockDetailResponse.data.depth.sequence = '2';
  value.StockDetailResponse.data.depth.bids = [];
  await page.getByRole('button', { name: 'Muat ulang data' }).click();
  await expect(book).toContainText('book-sim-2');
  await expect(book).not.toContainText('book-sim-1');
  await expect(page.getByRole('table', { name: 'Antrean bid' }).locator('tbody tr')).toHaveCount(0);
  await page.route('**/api/v1/stocks/TEST', route => route.abort());
  await page.getByRole('button', { name: 'Muat ulang data' }).click();
  await expect(book).toContainText('Book tidak tersedia');
  await expect(book.getByRole('table')).toHaveCount(0);
});

for (const variant of ['wrong-symbol', 'mixed-book', 'internal', 'wrong-mode', 'bad-cumulative']) {
  test(`reject detail ${variant}`, async ({ page }) => {
    const value = snapshots();
    if (variant === 'wrong-symbol') value.StockDetailResponse.data.symbol = 'OTHER';
    if (variant === 'mixed-book') value.StockDetailResponse.data.depth.symbol = 'OTHER';
    if (variant === 'internal') Object.assign(value.StockDetailResponse.data, { news: 'PRIVATE-NEWS' });
    if (variant === 'wrong-mode') value.StockDetailResponse.mode = 'live';
    if (variant === 'bad-cumulative') value.StockDetailResponse.data.depth.bids[0].cumulative_lots = 99;
    await mock(page, value);
    await page.goto('/stocks/TEST');
    await expect(page.getByRole('main').getByRole('alert')).toBeVisible();
    await expect(page.getByRole('region', { name: 'Rencana transaksi' })).toHaveCount(0);
    await expect(page.getByRole('region', { name: 'Order book' }).getByRole('table')).toHaveCount(0);
    await expect(page.locator('body')).not.toContainText('PRIVATE-NEWS');
  });
}

test('touch viewport keeps plan above book and no horizontal overflow', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 360, height: 800 }, hasTouch: true, isMobile: true });
  const page = await context.newPage();
  await mock(page);
  await page.goto('/stocks/TEST');
  const plan = page.getByRole('region', { name: 'Rencana transaksi' });
  const book = page.getByRole('region', { name: 'Order book' });
  await expect(plan).toBeVisible();
  await expect(page.locator('.price-chart canvas').first()).toBeVisible();
  const chart = page.getByRole('img', { name: 'Chart candle', exact: false });
  await chart.tap();
  const bounds = (await chart.boundingBox())!;
  const cdp = await context.newCDPSession(page);
  await cdp.send('Input.synthesizePinchGesture', { x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height / 2, scaleFactor: 1.5, gestureSourceType: 'touch' });
  await cdp.send('Input.synthesizeScrollGesture', { x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height / 2, xDistance: 50, yDistance: 0, gestureSourceType: 'touch' });
  await expect(page.getByText('Horizon rencana: 30 menit.', { exact: false })).toBeVisible();
  expect((await plan.boundingBox())!.y).toBeLessThan((await book.boundingBox())!.y);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
  for (const cell of await page.locator('.plan-grid dd, .book-sides table').all()) {
    const bounds = (await cell.boundingBox())!;
    expect(bounds.x).toBeGreaterThanOrEqual(0);
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(360);
  }
  await page.screenshot({ path: '../../.work/issue19-mobile.png', fullPage: true });
  await context.close();
});

test('five-level book renders available rows without padding', async ({ page }) => {
  const value = snapshots();
  const book = value.StockDetailResponse.data.depth;
  book.available_levels = 5;
  book.limited = false;
  book.bids = Array.from({ length: 5 }, (_, i) => ({ price_idr: `${1000 - i * 10}.00`, lots: 10, cumulative_lots: (i + 1) * 10 }));
  book.asks = Array.from({ length: 5 }, (_, i) => ({ price_idr: `${1010 + i * 10}.00`, lots: 12, cumulative_lots: (i + 1) * 12 }));
  await mock(page, value);
  await page.goto('/stocks/TEST');
  await expect(page.getByRole('table', { name: 'Antrean bid' }).locator('tbody tr')).toHaveCount(5);
  await expect(page.getByRole('table', { name: 'Antrean ask' }).locator('tbody tr')).toHaveCount(5);
  await expect(page.getByRole('region', { name: 'Order book' })).toContainText('5 tingkat tersedia');
});

test('validated synthetic projection renders coverage bands and expires without a refetch', async ({ page }) => {
  await page.clock.install();
  const value = snapshots();
  const signal = value.StockDetailResponse.data.signal;
  Object.assign(value.ChartResponse.data, {
    model_version: signal.model_version, horizon_minutes: 30, coverage_status: 'validated',
    projection: [0.5, 0.8].flatMap(coverage => [5, 15, 25].map(minutes => ({ at: new Date(Date.parse(value.ChartResponse.as_of) + minutes * 60000).toISOString(), median_idr: '1020.00', lower_idr: coverage === 0.5 ? '1010.00' : '1000.00', upper_idr: coverage === 0.5 ? '1030.00' : '1040.00', coverage }))),
  });
  await mock(page, value);
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('/stocks/TEST');
  await expect(page.locator('.projection-legend')).toContainText('50%, 80%');
  await page.screenshot({ path: '../../.work/issue19-projection.png', fullPage: true });
  await page.getByRole('button', { name: '5m', exact: true }).click();
  await expect(page.locator('.projection-legend')).toContainText('Horizon 30 menit');
  await page.clock.fastForward(1801000);
  await expect(page.locator('.projection-legend')).toHaveCount(0);
  await expect(page.getByText('Proyeksi: Tidak tersedia · rencana kedaluwarsa', { exact: false })).toBeVisible();
  expect(errors).toEqual([]);
});

test('late chart response cannot replace selected interval', async ({ page }) => {
  await mock(page);
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/chart?interval=1m', async route => {
    await gate;
    await route.fulfill({ json: snapshots().ChartResponse }).catch(() => {});
  });
  await page.goto('/stocks/TEST');
  await page.getByRole('button', { name: '15m', exact: true }).click();
  await expect(page.getByText('Riwayat interval 15m: Tidak tersedia')).toBeVisible();
  release();
  await expect(page.getByText('Riwayat interval 15m: Tidak tersedia')).toBeVisible();
});

test('chart horizon mismatch suppresses projection rather than changing plan', async ({ page }) => {
  const value = snapshots();
  Object.assign(value.ChartResponse.data, { horizon_minutes: 60, model_version: value.StockDetailResponse.data.signal.model_version });
  await mock(page, value);
  await page.goto('/stocks/TEST');
  await expect(page.getByText('Horizon rencana: 30 menit.', { exact: false })).toBeVisible();
  await expect(page.locator('.projection-legend')).toHaveCount(0);
});

test('null resources remain unavailable and retry restores the whole plan', async ({ page }) => {
  const value = snapshots();
  Object.assign(value.StockDetailResponse.data, { signal: null, liquidity: null, depth: null, last_price_idr: null, pressure: [] });
  await mock(page, value);
  await page.goto('/stocks/TEST');
  await expect(page.getByRole('region', { name: 'Rencana transaksi' })).toContainText('Rencana: Tidak tersedia');
  await expect(page.getByRole('region', { name: 'Order book' })).toContainText('Order book: Tidak tersedia');
  await expect(page.getByText('Harga terakhir:', { exact: false })).toContainText('Tidak tersedia');
  value.StockDetailResponse = snapshots().StockDetailResponse;
  await page.getByRole('button', { name: 'Muat ulang data' }).click();
  await expect(page.getByRole('region', { name: 'Rencana transaksi' })).toContainText('Rp 990');
});

test('validated estimated pressure includes method, window and classified coverage', async ({ page }) => {
  const value = snapshots();
  Object.assign(value.StockDetailResponse.data.pressure[0], { validated: true, method: 'estimated', classified_ratio: 0.9, buy_ratio: 0.6, sell_ratio: 0.4 });
  await mock(page, value);
  await page.goto('/stocks/TEST');
  await expect(page.getByRole('region', { name: 'Tekanan transaksi agresif' })).toContainText('5 menit · Beli 60% / jual 40% · Cakupan klasifikasi: 90% · Metode: Estimasi');
});

test('future actual candle is rejected independently of the plan', async ({ page }) => {
  const value = snapshots();
  value.ChartResponse.data.candles[0].at = new Date(Date.now() + 60000).toISOString();
  await mock(page, value);
  await page.goto('/stocks/TEST');
  await expect(page.getByRole('region', { name: 'Harga & volume' }).getByRole('alert')).toContainText('Chart tidak konsisten');
  await expect(page.getByRole('region', { name: 'Rencana transaksi' })).toContainText('Rp 990');
  await expect(page.locator('.price-chart')).toHaveCount(0);
});

for (const status of [401, 404, 503]) {
  test(`safe detail HTTP ${status}`, async ({ page }) => {
    await mock(page);
    await page.route('**/api/v1/stocks/TEST', route => route.fulfill({ status, body: 'PRIVATE-ERROR' }));
    await page.goto('/stocks/TEST');
    await expect(page.getByRole('main').getByRole('alert')).toBeVisible();
    await expect(page.locator('body')).not.toContainText('PRIVATE-ERROR');
  });
}

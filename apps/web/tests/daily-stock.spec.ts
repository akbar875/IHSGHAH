import { expect, test } from '@playwright/test';

const net = 1.1 * (1 - .0025 - .001) / (1 + .0015 + .001);
const detail = {
  origin: 'market', feed: 'daily', symbol: 'BULL', date: '2026-11-13',
  as_of: '2026-11-17T01:00:00Z', available_at: '2026-11-16T02:00:00Z', stale: false,
  close_idr: '1000', plan: null, order_book: null, individual_queue: null, depth_status: 'feed_not_connected',
  source: 'https://dataset.aethereal.top/datasets/idx-stock-features', license_url: 'https://creativecommons.org/licenses/by/4.0/', attribution: 'Synthetic test values.',
  history: [10, 11, 12, 13].map(n => ({ date: `2026-11-${n}`, close_idr: n === 12 ? '1100' : '1000', volume: '100000', return_1d: '0' })),
  backtest: {
    origin: 'simulation', method: 'ma-rsi-close-replay-v1', direction: 'long_only', sample: 'exploratory_in_sample',
    target_trades: 1000, completed_trades: 1, target_reached: false, status: 'insufficient_trades',
    start_date: '2026-11-10', end_date: '2026-11-13', unclosed_position: false,
    win_count: 1, loss_count: 0, flat_count: 0, total_return_pct: (net - 1) * 100, max_drawdown_pct: 1,
    buy_fee: .0015, sell_fee: .0025, slippage_each_side: .001, holding_sessions: 15,
    trades: [{ signal_date: '2026-11-10', entry_date: '2026-11-11', exit_date: '2026-11-12', entry_close: '1000', exit_close: '1100', net_return_pct: (net - 1) * 100, equity: net, exit_reason: 'target_close' }],
  },
};
const list = {
  method: 'ma-rsi-momentum-2r-v1', latest_date: '2026-11-13', available_at: detail.available_at,
  stale: false, needs_reimport: false, universe_count: 100, source: detail.source,
  license_url: detail.license_url, attribution: detail.attribution,
  rows: [{ symbol: 'BULL', date: '2026-11-13', direction: 'bullish', reference: '1000', take_profit: '1100', stop_loss: '950', potential_pct: '10', risk_pct: '5', reward_risk: '2', rsi_14: '60', momentum_20d_pct: '12' }],
};

test('clicking a listed stock opens daily charts, actual backtest counts and unavailable depth at 360px', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 820 });
  await page.route('**/api/research/screener', r => r.fulfill({ json: list }));
  await page.route('**/api/research/stocks/BULL', r => r.fulfill({ json: detail }));
  await page.goto('/screener');
  await page.getByRole('link', { name: 'Lihat detail BULL' }).click();
  await expect(page).toHaveURL(/\/stocks\/BULL\?source=daily$/);
  await expect(page.getByRole('status')).toHaveText('Detail saham tersedia.');
  await expect(page.getByRole('heading', { name: 'Chart harga & volume' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Backtest transaksi historis' })).toBeVisible();
  await expect(page.getByText('Belum mencapai 1.000 transaksi.', { exact: false })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Order book', exact: true })).toContainText('Feed belum terhubung');
  await expect(page.getByRole('region', { name: 'Antrean order', exact: true })).toContainText('Belum tersedia');
  await expect(page.getByRole('table', { name: '20 transaksi selesai terakhir · tanggal EOD WIB' })).toContainText('2026-11-12');
  await expect(page.getByText('Ungu: indeks hasil (awal 100)')).toBeVisible();
  await page.getByRole('button', { name: '20 sesi', exact: true }).click();
  await expect(page.getByRole('button', { name: '20 sesi', exact: true })).toHaveAttribute('aria-pressed', 'true');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '../../.work/daily-detail-mobile.png', fullPage: true });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.screenshot({ path: '../../.work/daily-detail-desktop.png', fullPage: true });
  await page.getByRole('link', { name: '← Daftar saham' }).click();
  await expect(page).toHaveURL('/');
});

test('refreshes daily snapshots every 15 seconds and removes charts after outage', async ({ page }) => {
  await page.clock.install();
  let failed = false;
  let requests = 0;
  await page.route('**/api/research/stocks/BULL', r => { requests++; return failed ? r.fulfill({ status: 503 }) : r.fulfill({ json: detail }); });
  await page.goto('/stocks/BULL?source=daily');
  await expect(page.getByRole('status')).toHaveText('Detail saham tersedia.');
  await page.clock.fastForward(15001);
  await expect.poll(() => requests).toBeGreaterThanOrEqual(2);
  failed = true;
  await page.clock.fastForward(15001);
  await expect(page.getByRole('status')).toContainText('Data belum tersedia');
  await expect(page.getByRole('heading', { name: 'Chart harga & volume' })).toHaveCount(0);
});

for (const variant of ['wrong-symbol', 'fabricated-thousand', 'duplicate-trade', 'fake-depth', 'bad-equity']) {
  test(`rejects ${variant}`, async ({ page }) => {
    const invalid = structuredClone(detail);
    if (variant === 'wrong-symbol') invalid.symbol = 'OTHER';
    if (variant === 'fabricated-thousand') invalid.backtest.completed_trades = 1000;
    if (variant === 'duplicate-trade') { invalid.backtest.trades.push(structuredClone(invalid.backtest.trades[0])); invalid.backtest.completed_trades = 2; invalid.backtest.win_count = 2; }
    if (variant === 'fake-depth') Object.assign(invalid, { order_book: { bids: [] } });
    if (variant === 'bad-equity') invalid.backtest.trades[0].equity = 100;
    await page.route('**/api/research/stocks/BULL', r => r.fulfill({ json: invalid }));
    await page.goto('/stocks/BULL?source=daily');
    await expect(page.getByRole('status')).toContainText('tidak valid');
    await expect(page.getByRole('heading', { name: 'Chart harga & volume' })).toHaveCount(0);
  });
}

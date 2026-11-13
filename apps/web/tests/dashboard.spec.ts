import { test, expect, type Page } from '@playwright/test';
import fixture from '../../../services/api/src/saham_signal/fixtures/market-simulation.json';

function snapshot(nominal = '1000000.00') {
  const value = structuredClone(fixture.CandidatesResponse);
  const now = Date.now();
  value.as_of = new Date(now).toISOString();
  for (const signal of value.data) {
    signal.assumptions.nominal_idr = nominal;
    signal.generated_at = signal.data_as_of = signal.entry_from = value.as_of;
    signal.entry_until = signal.valid_until = signal.exit_deadline = new Date(now + 1800000).toISOString();
  }
  return value;
}

async function mock(page: Page, mutate: (value: ReturnType<typeof snapshot>) => void = () => {}) {
  await page.route('**/api/v1/candidates?*', async route => {
    const value = snapshot(new URL(route.request().url()).searchParams.get('nominal_idr')!);
    mutate(value);
    await route.fulfill({ json: value, headers: { 'Access-Control-Allow-Origin': 'http://127.0.0.1:3100', 'Access-Control-Allow-Credentials': 'true' } });
  });
}

test('simulation, null probabilities, core numbers and no internal model content', async ({ page }) => {
  await mock(page);
  await page.goto('/');
  const card = page.getByRole('article', { name: 'Kandidat TEST' });
  await expect(card).toBeVisible();
  await expect(page.getByText('Research / Simulasi', { exact: true })).toBeVisible();
  await expect(card.getByText('Simulasi · 30 menit')).toBeVisible();
  await expect(card.locator('div').filter({ has: page.locator('dt', { hasText: 'Peluang target' }) }).last()).toContainText('Tidak tersedia');
  await expect(card).toContainText('Rp 1.000');
  await expect(card).toContainText('Rp 990');
  await expect(card).toContainText('Rp 1.030');
  await expect(card).toContainText('WIB');
  await expect(page.getByText('Model belum tervalidasi.', { exact: false })).toBeVisible();
  await expect(page.locator('body')).not.toContainText('sim-policy-1');
  await expect(page.locator('body')).not.toContainText('unvalidated-1');
  await page.screenshot({ path: '../../.work/issue18-desktop.png', fullPage: true });
});

test('search and active filter handle empty results', async ({ page }) => {
  await mock(page, value => { value.data[0].state = 'CANCELLED'; });
  await page.goto('/');
  await expect(page.getByText('Belum ada kandidat aktif')).toBeVisible();
  await page.getByLabel('Kandidat aktif').uncheck();
  await expect(page.getByRole('article')).toBeVisible();
  await page.getByLabel('Cari kode saham').fill('unknown');
  await expect(page.getByText('Tidak ada kandidat yang cocok')).toBeVisible();
  await page.getByLabel('Cari kode saham').fill('test');
  await expect(page.getByRole('article')).toBeVisible();
});

test('READY with unhealthy data never advertises entry readiness', async ({ page }) => {
  await mock(page, value => { value.data[0].state = 'READY'; });
  await page.goto('/');
  await expect(page.getByRole('article')).toBeVisible();
  await expect(page.getByRole('article').getByText('Entry ditahan', { exact: true })).toBeVisible();
  await expect(page.getByText('Siap masuk', { exact: true })).toHaveCount(0);
});

test('nominal submits a fresh request and validates input', async ({ page }) => {
  await mock(page);
  await page.goto('/');
  await expect(page.getByRole('article')).toBeVisible();
  await page.getByLabel('Nominal transaksi (Rp)').fill('2500000');
  const request = page.waitForRequest('**/candidates?nominal_idr=2500000.00');
  await page.getByRole('button', { name: 'Terapkan' }).click();
  await request;
  await expect(page.getByRole('article')).toContainText('Rp 2.500.000');
  await page.getByLabel('Nominal transaksi (Rp)').fill('0');
  await page.getByRole('button', { name: 'Terapkan' }).click();
  await expect(page.locator('#nominal-error')).toContainText('Masukkan nominal');
  await expect(page.getByRole('article')).toContainText('Rp 2.500.000');
});

for (const [name, mutate, message] of [
  ['empty', (v: ReturnType<typeof snapshot>) => { v.data = []; }, 'Belum ada kandidat aktif'],
  ['closed', (v: ReturnType<typeof snapshot>) => { v.quality.reasons.push('MARKET_CLOSED'); }, 'Pasar tutup. Tunggu sesi berikutnya.'],
  ['delayed', (v: ReturnType<typeof snapshot>) => { v.quality.feed = 'delayed'; }, 'Data delayed.'],
  ['stale', (v: ReturnType<typeof snapshot>) => { v.quality.status = 'stale'; }, 'Data kedaluwarsa.'],
  ['disconnected', (v: ReturnType<typeof snapshot>) => { v.quality.status = 'disconnected'; }, 'Koneksi terputus. Entry ditahan'],
] as const) {
  test(`data state: ${name}`, async ({ page }) => {
    await mock(page, mutate);
    await page.goto('/');
    await expect(page.getByText(message, { exact: false })).toBeVisible();
  });
}

test('loading, network failure and retry recover without retaining old candidates', async ({ page }) => {
  let fail = true;
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/v1/candidates?*', async route => {
    await gate;
    if (fail) await route.abort();
    else await route.fulfill({ json: snapshot() });
  });
  await page.goto('/');
  await expect(page.getByText('Memuat kandidat…')).toBeVisible();
  release();
  await expect(page.getByText('Data belum dapat dimuat')).toBeVisible();
  fail = false;
  await page.getByRole('button', { name: 'Coba lagi' }).click();
  await expect(page.getByRole('article')).toBeVisible();
});

for (const status of [401, 503]) {
  test(`safe HTTP ${status} handling`, async ({ page }) => {
    await page.route('**/api/v1/candidates?*', route => route.fulfill({ status, body: 'PRIVATE-UPSTREAM-DETAIL' }));
    await page.goto('/');
    await expect(page.getByText('Data belum dapat dimuat')).toBeVisible();
    await expect(page.locator('body')).not.toContainText('PRIVATE-UPSTREAM-DETAIL');
  });
}

for (const variant of ['internal-field', 'wrong-nominal', 'wrong-mode', 'bad-probability']) {
  test(`reject invalid payload: ${variant}`, async ({ page }) => {
    await mock(page, value => {
      if (variant === 'internal-field') Object.assign(value.data[0], { news: 'INTERNAL-DOCUMENT' });
      if (variant === 'wrong-nominal') value.data[0].assumptions.nominal_idr = '5000000.00';
      if (variant === 'wrong-mode') value.mode = 'live';
      if (variant === 'bad-probability') Object.assign(value.data[0].target_probability, { value: 0.99 });
    });
    await page.goto('/');
    await expect(page.getByText('Data tidak sesuai permintaan.', { exact: false })).toBeVisible();
    await expect(page.getByRole('article')).toHaveCount(0);
    await expect(page.locator('body')).not.toContainText('INTERNAL-DOCUMENT');
  });
}

test('late response from a previous nominal cannot overwrite the latest result', async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/v1/candidates?*', async route => {
    const nominal = new URL(route.request().url()).searchParams.get('nominal_idr')!;
    if (nominal === '1000000.00') await gate;
    await route.fulfill({ json: snapshot(nominal) }).catch(() => {});
  });
  await page.goto('/');
  await page.getByLabel('Nominal transaksi (Rp)').fill('2500000');
  await page.getByRole('button', { name: 'Terapkan' }).click();
  await expect(page.getByRole('article')).toContainText('Rp 2.500.000');
  release();
  await expect(page.getByRole('article')).toContainText('Rp 2.500.000');
});

test('expired plans disappear from the active filter without another response', async ({ page }) => {
  await page.clock.install();
  const value = snapshot();
  await page.route('**/api/v1/candidates?*', route => route.fulfill({ json: value }));
  await page.goto('/');
  await expect(page.getByRole('article')).toBeVisible();
  await page.clock.fastForward(1801000);
  await expect(page.getByText('Belum ada kandidat aktif')).toBeVisible();
  await page.getByLabel('Kandidat aktif').uncheck();
  await expect(page.getByRole('article')).toContainText('Kedaluwarsa');
});

test('core numbers fit at 360px with no horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await mock(page);
  await page.goto('/');
  await expect(page.getByRole('article')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
  for (const dd of await page.locator('.plan-grid dd').all()) {
    const bounds = await dd.boundingBox();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(360);
  }
  await page.screenshot({ path: '../../.work/issue18-mobile.png', fullPage: true });
});

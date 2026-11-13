'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { MarketError, money, time } from '@/lib/market';
import { fetchStock, type StockDetailResponse, type ChartResponse, type SignalHistoryResponse, type Interval, type Depth } from '@/lib/stock';
import PriceChart from './price-chart';

type Responses = { StockDetailResponse: StockDetailResponse; ChartResponse: ChartResponse; SignalHistoryResponse: SignalHistoryResponse };
function useResource<K extends keyof Responses>(kind: K, symbol: string, revision: number, interval?: Interval) {
  const key = `${kind}:${symbol}:${interval}:${revision}`;
  const [result, setResult] = useState<{ key: string; data: Responses[K] | null; error: string | null }>({ key: '', data: null, error: null });
  useEffect(() => {
    let disposed = false;
    let pending = false;
    let controller: AbortController | null = null;
    async function load() {
      if (pending) return;
      pending = true;
      controller = new AbortController();
      const timeout = setTimeout(() => controller?.abort(), 10000);
      try {
        const data = await fetchStock(kind, symbol, controller.signal, interval);
        if (!disposed) setResult({ key, data, error: null });
      } catch (cause) {
        if (!disposed) setResult({ key, data: null, error: cause instanceof MarketError ? cause.message : 'Koneksi terputus. Coba lagi.' });
      } finally { clearTimeout(timeout); pending = false; }
    }
    void load();
    const timer = setInterval(() => void load(), 15000);
    return () => { disposed = true; clearInterval(timer); controller?.abort(); };
  }, [key, kind, symbol, interval]);
  return result.key === key ? { ...result, loading: false } : { data: null, error: null, loading: true };
}
const percent = (v: number) => `${(v * 100).toLocaleString('id-ID', { maximumFractionDigits: 1 })}%`;
const states = { WATCH: 'Tunggu', READY: 'Entry ditahan', EXPIRED: 'Kedaluwarsa', CANCELLED: 'Dibatalkan' };
const qualityLabels = { healthy: 'Sehat', degraded: 'Menurun', stale: 'Kedaluwarsa', disconnected: 'Terputus', unavailable: 'Tidak tersedia' };
const feedLabels = { live: 'Live', delayed: 'Delayed', disconnected: 'Terputus', unavailable: 'Tidak tersedia' };

function Book({ book, now }: { book: Depth | null; now: number }) {
  if (!book) return <p>Order book: Tidak tersedia</p>;
  const spread = book.bids[0] && book.asks[0] ? money((Number(book.asks[0].price_idr) - Number(book.bids[0].price_idr)).toFixed(2)) : 'Tidak tersedia';
  return <>
    <p className="muted">{book.limited || book.available_levels < 5 ? 'Kedalaman terbatas' : 'Kedalaman tersedia'} · {book.available_levels} tingkat tersedia · maksimal 5 ditampilkan</p>
    <dl className="timing-grid"><div><dt>Snapshot</dt><dd>{book.snapshot_id} · urutan {book.sequence}</dd></div><div><dt>Waktu / umur snapshot</dt><dd>{time(book.depth_as_of)} · {Math.max(0, Math.floor((now - Date.parse(book.depth_as_of)) / 1000))} detik</dd></div><div><dt>Spread</dt><dd>{spread}</dd></div></dl>
    <div className="book-sides">{(['bids', 'asks'] as const).map(side => <table key={side} aria-label={side === 'bids' ? 'Antrean bid' : 'Antrean ask'}>
      <caption>{side === 'bids' ? 'Bid' : 'Ask'}</caption><thead><tr><th>Harga (Rp)</th><th>Lot</th><th>Kumulatif</th></tr></thead>
      <tbody>{book[side].slice(0, 5).map(row => <tr key={row.price_idr}><td>{Number(row.price_idr).toLocaleString('id-ID')}</td><td>{row.lots.toLocaleString('id-ID')}</td><td>{row.cumulative_lots.toLocaleString('id-ID')}</td></tr>)}</tbody>
    </table>)}</div>
    {(!book.bids.length || !book.asks.length) && <p>Sisi antrean kosong: Tidak tersedia. Tidak ada tingkat pengganti.</p>}
  </>;
}

export default function StockDetail({ symbol }: { symbol: string }) {
  const [interval, setIntervalValue] = useState<Interval>('1m');
  const [revision, setRevision] = useState(0);
  const [now, setNow] = useState(0);
  const detail = useResource('StockDetailResponse', symbol, revision);
  const chart = useResource('ChartResponse', symbol, revision, interval);
  const history = useResource('SignalHistoryResponse', symbol, revision);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const data = detail.data?.data;
  const signal = data?.signal ?? null;
  const expired = signal && now >= Math.min(Date.parse(signal.valid_until), Date.parse(signal.entry_until));
  const chartData = chart.data?.data;
  const compatible = !!chartData && !!signal && chartData.horizon_minutes === signal.horizon_minutes && chartData.model_version === signal.model_version;
  const projectionAllowed = !!(compatible && signal && !expired && signal.state !== 'EXPIRED' && signal.state !== 'CANCELLED' && chartData?.coverage_status === 'validated' && chartData.projection.every(p => Date.parse(p.at) > now && Date.parse(p.at) <= Date.parse(signal.valid_until)));
  return <>
    <a className="skip-link" href="#utama">Lewati ke konten</a>
    <header className="header"><Link className="brand" href="/">Saham Signal</Link><span className="mode">Research / Simulasi</span></header>
    <main id="utama" className="workspace stock-workspace">
      <Link href="/">← Daftar kandidat</Link><h1>{symbol}.</h1>
      <p className="intro">Tinjau riwayat harga, rencana, dan antrean pasar.</p>
      <section className="notice"><div><h2>Lingkungan simulasi</h2><p>Harga, volume dan rencana sintetis untuk mencoba tampilan. Belum ada feed pasar atau model produksi tervalidasi. Jangan gunakan untuk transaksi nyata.</p></div></section>
      <button onClick={() => setRevision(v => v + 1)}>Muat ulang data</button>
      <div aria-live="polite">{detail.loading ? <p>Memuat detail…</p> : detail.error ? <p role="alert">{detail.error}</p> : data && <>
        <p>Harga terakhir: <strong>{data.last_price_idr === null ? 'Tidak tersedia' : money(data.last_price_idr)}</strong> · Waktu data: {time(detail.data!.as_of)}</p>
        <p className="entry-warning">Entry ditahan · simulasi. Status data: {qualityLabels[detail.data!.quality.status]}; feed: {feedLabels[detail.data!.quality.feed]}. READY tidak membuka posisi.</p>
        {detail.data!.quality.reasons.includes('MARKET_CLOSED') && <p>Pasar tutup. Tunggu sesi berikutnya.</p>}
        {detail.data!.quality.reasons.includes('MODEL_UNVALIDATED') && <p>Model belum tervalidasi. Estimasi yang belum tersedia tidak ditampilkan.</p>}
        <section className="panel detail-section" aria-labelledby="plan-title"><h2 id="plan-title">Rencana transaksi</h2>
          {signal ? <>
            <p className="tag">{expired ? 'Kedaluwarsa' : states[signal.state]} · Horizon {signal.horizon_minutes} menit</p>
            <dl className="plan-grid">
              <div className="entry"><dt>Zona entry</dt><dd>{money(signal.entry_zone.lower_idr)} – {money(signal.entry_zone.upper_idr)}</dd></div>
              <div><dt>Stop loss</dt><dd>{money(signal.stop_idr)}</dd></div>
              {signal.targets_idr.map((p, i) => <div key={i}><dt>Target TP{i + 1}</dt><dd>{money(p)}</dd></div>)}
              <div><dt>Nominal rencana layanan</dt><dd>{money(signal.assumptions.nominal_idr)}</dd></div>
              <div><dt>Lot rencana</dt><dd>{data.liquidity?.lots ?? 'Tidak tersedia'}</dd></div>
              <div><dt>Estimasi hasil bersih</dt><dd>{signal.return_quantiles ? percent(Number(signal.return_quantiles.p50)) : 'Tidak tersedia'}</dd></div>
              <div><dt>Peluang target</dt><dd>{signal.target_probability.value === null ? 'Tidak tersedia' : percent(signal.target_probability.value)}</dd></div>
            </dl>
            <dl className="timing-grid"><div><dt>Jendela entry</dt><dd>{time(signal.entry_from)} – {time(signal.entry_until)}</dd></div><div><dt>Deadline exit</dt><dd>{time(signal.exit_deadline)}</dd></div><div><dt>Kedaluwarsa rencana</dt><dd>{time(signal.valid_until)}</dd></div></dl>
            <p className="muted">Nominal pada detail mengikuti konfigurasi layanan, terpisah dari input dashboard.</p>
          </> : <p>Rencana: Tidak tersedia</p>}
        </section>
      </>}</div>
      <section className="panel detail-section" aria-labelledby="chart-title"><h2 id="chart-title">Harga &amp; volume</h2>
        <div className="intervals" role="group" aria-label="Interval candle">{(['1m', '5m', '15m'] as const).map(value => <button key={value} aria-pressed={interval === value} onClick={() => setIntervalValue(value)}>{value}</button>)}</div>
        <p>Horizon rencana: {signal ? `${signal.horizon_minutes} menit` : 'Tidak tersedia'}. Interval dan zoom hanya mengubah tampilan riwayat.</p>
        {chart.loading ? <p>Memuat chart…</p> : chart.error ? <p role="alert">{chart.error}</p> : chart.data && <>
          {!chart.data.data.candles.length && <p>Riwayat interval {interval}: Tidak tersedia</p>}
          <PriceChart response={chart.data} signal={signal} projectionAllowed={projectionAllowed} />
          <p className="muted">Riwayat aktual (simulasi): candle + volume lot. Entry / stop / TP: garis horizontal. Kedaluwarsa: garis vertikal merah.</p>
          {projectionAllowed && chartData!.projection.length ? <p className="projection-legend">Proyeksi estimasi: garis putus-putus, latar ungu. Cakupan rentang: {[...new Set(chartData!.projection.map(p => percent(p.coverage)))].join(', ')}. Horizon {chartData!.horizon_minutes} menit.</p> : <p>Proyeksi: Tidak tersedia{expired ? ' · rencana kedaluwarsa' : ' · belum tervalidasi atau tidak sesuai rencana'}. Rentang tidak digambar tanpa data tervalidasi.</p>}
        </>}
        <p className="muted">Sentuh dan geser chart untuk menelusuri, cubit untuk zoom. Waktu WIB.</p>
        <p className="chart-attribution">TradingView Lightweight Charts™ · Copyright (с) 2025 TradingView, Inc. · <a href="https://www.tradingview.com/">TradingView</a> · <a href="https://www.apache.org/licenses/LICENSE-2.0">Apache-2.0</a></p>
      </section>
      <section className="panel detail-section" aria-labelledby="book-title"><h2 id="book-title">Order book</h2>{detail.loading ? <p>Memuat book…</p> : detail.error ? <p>Book tidak tersedia. Muat ulang seluruh snapshot.</p> : <Book book={data?.depth ?? null} now={now} />}</section>
      <section className="panel detail-section" aria-labelledby="pressure-title"><h2 id="pressure-title">Tekanan transaksi agresif</h2>
        <p className="muted">Berbasis volume transaksi terklasifikasi, bukan jumlah investor atau komposisi antrean.</p>
        {([1, 5, 15] as const).map(window => {
          const pressure = data?.pressure.find(p => p.window_minutes === window);
          const show = pressure?.validated && pressure.method !== 'unavailable' && pressure.classified_ratio > 0 && pressure.buy_ratio !== null && pressure.sell_ratio !== null && Math.abs(pressure.buy_ratio + pressure.sell_ratio - 1) < .000001;
          return <p key={window}>{window} menit · {show ? `Beli ${percent(pressure.buy_ratio!)} / jual ${percent(pressure.sell_ratio!)}` : 'Beli / jual: Tidak tersedia'} · Cakupan klasifikasi: {pressure ? percent(pressure.classified_ratio) : 'Tidak tersedia'} · Metode: {pressure?.method === 'estimated' ? 'Estimasi' : pressure?.method === 'provider' ? 'Agresor dari penyedia' : 'Tidak tersedia'}</p>;
        })}
      </section>
      <section className="panel detail-section"><h2>Riwayat sinyal</h2>{history.loading ? <p>Memuat riwayat…</p> : history.error ? <p>{history.error}</p> : history.data?.data.length ? <ul>{history.data.data.map(s => <li key={`${s.signal_id}:${s.version}`}>{time(s.generated_at)} · versi {s.version} · {states[s.state]} · Horizon {s.horizon_minutes} menit</li>)}</ul> : <p>Tidak tersedia</p>}</section>
    </main>
    <footer className="footer">Saham Signal · Research / Simulasi · Asia/Jakarta</footer>
  </>;
}

'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { publicConfig } from '@/lib/config';

type DailyRow = { symbol: string; date: string; close_idr: string; volume: string; return_1d: string | null; rsi_14: string | null; stale: boolean };
type DailyData = { mode: 'research'; origin: 'market'; frequency: 'daily'; provider: 'Aethereal'; license: 'CC BY 4.0'; source: string; license_url: string; attribution: string; available_at: string; latest_date: string; stale: boolean; signals_enabled: false; sha256: string; rows: DailyRow[]; quality: { rows: number; accepted_rows: number; rejected_rows: number; published_symbols: number } };
const source = 'https://dataset.aethereal.top/datasets/idx-stock-features';
const license = 'https://creativecommons.org/licenses/by/4.0/';
const decimal = (value: unknown) => typeof value === 'string' && value.length < 80 && Number.isFinite(Number(value)) && value.trim() !== '';
const day = (value: unknown): value is string => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;
function parse(value: unknown): DailyData {
  const data = value as DailyData;
  if (!data || data.mode !== 'research' || data.origin !== 'market' || data.frequency !== 'daily' || data.provider !== 'Aethereal' ||
      data.license !== 'CC BY 4.0' || data.source !== source || data.license_url !== license || data.signals_enabled !== false ||
      typeof data.attribution !== 'string' || !data.attribution || !Number.isFinite(Date.parse(data.available_at)) || !day(data.latest_date) ||
      typeof data.stale !== 'boolean' || !/^[a-f0-9]{64}$/.test(data.sha256) || !Array.isArray(data.rows) || !data.rows.length || data.rows.length > 2000 ||
      new Set(data.rows.map(r => r?.symbol)).size !== data.rows.length || data.rows.some(r =>
        !r || typeof r.symbol !== 'string' || !/^[A-Z][A-Z0-9]{1,7}$/.test(r.symbol) || !day(r.date) || r.date > data.latest_date ||
        !decimal(r.close_idr) || Number(r.close_idr) <= 0 || Number(r.close_idr) >= 1e16 ||
        typeof r.volume !== 'string' || !/^(?:0|[1-9][0-9]{0,18})$/.test(r.volume) || BigInt(r.volume) > BigInt('1000000000000000000') ||
        typeof r.stale !== 'boolean' || (r.return_1d !== null && (!decimal(r.return_1d) || Number(r.return_1d) < -1 || Number(r.return_1d) > 1e12)) ||
        (r.rsi_14 !== null && (!decimal(r.rsi_14) || Number(r.rsi_14) < 0 || Number(r.rsi_14) > 100)))) throw new Error('Data harian tidak valid.');
  if (!data.quality || [data.quality.rows, data.quality.accepted_rows, data.quality.rejected_rows, data.quality.published_symbols].some(n => !Number.isSafeInteger(n) || n < 0) ||
      data.quality.rows !== data.quality.accepted_rows + data.quality.rejected_rows || data.quality.published_symbols !== data.rows.length) throw new Error('Laporan kualitas tidak valid.');
  return data;
}
const rupiah = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 2 });
const integer = new Intl.NumberFormat('id-ID');
const dateLabel = (value: string) => new Date(`${value}T00:00:00+07:00`).toLocaleDateString('id-ID', { timeZone: 'Asia/Jakarta' });

export default function DailyResearch() {
  const [data, setData] = useState<DailyData | null>(null);
  const [status, setStatus] = useState('Memuat data harian…');
  const [retry, setRetry] = useState(0);
  const [query, setQuery] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    let disposed = false;
    const timeout = setTimeout(() => controller.abort(), 10000);
    fetch(new URL('../research/eod', `${publicConfig.apiBaseUrl}/`), { credentials: 'include', cache: 'no-store', signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error(response.status === 401 || response.status === 403 ? 'Sesi admin research diperlukan.' : 'Data harian belum tersedia. Jalankan import sumber gratis pada backend.');
        return parse(await response.json());
      })
      .then(result => { if (!disposed) { setData(result); setStatus('Data pasar harian tersedia.'); } })
      .catch(error => { if (!disposed) { setData(null); setStatus(error instanceof Error && error.name !== 'AbortError' ? error.message : 'Data harian gagal dimuat.'); } })
      .finally(() => clearTimeout(timeout));
    return () => { disposed = true; controller.abort(); clearTimeout(timeout); };
  }, [retry]);
  const visible = data?.rows.filter(row => row.symbol.includes(query.trim().toUpperCase())) ?? [];
  return <main className="eod-page">
    <Link href="/">← Dashboard simulasi</Link><h1>Riset saham harian</h1>
    <p>Data pasar harian gratis · Aethereal · Lingkungan research</p>
    <section className="notice" aria-label="Batas penggunaan"><div><h2>Data akhir hari</h2><p>Harga penutupan dan indikator historis untuk riset harian. Sinyal intraday, peluang profit, dan eksekusi paper live belum diaktifkan.</p></div></section>
    <p role="status">{status}</p>
    <button onClick={() => { setData(null); setStatus('Memuat data harian…'); setRetry(n => n + 1); }}>Muat ulang data harian</button>
    {data && <>
      <section className="panel detail-section" aria-label="Sumber dan kualitas">
        <h2>Sumber dan kualitas</h2><p>Data terakhir: <strong>{dateLabel(data.latest_date)}</strong>. Snapshot diimpor {new Date(data.available_at).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' })} WIB.</p>
        <p>{integer.format(data.quality.accepted_rows)} baris lolos pemeriksaan · {integer.format(data.quality.rejected_rows)} ditolak · {data.rows.length} ticker tersedia.</p>
        {(data.stale || data.rows.some(r => r.stale)) && <p className="entry-warning">Ada data tertinggal lebih dari 7 hari kalender. Periksa tanggal setiap saham sebelum menggunakannya untuk riset.</p>}
        <p className="muted">Pemeriksaan struktur tidak menjamin kebenaran harga terhadap bursa. Indikator dihitung penyedia; universe historis dan delisting belum divalidasi untuk backtest.</p>
        <p><a href={source}>Sumber Aethereal</a> · <a href={license}>CC BY 4.0</a></p><p className="muted">{data.attribution}</p>
      </section>
      <label className="eod-search">Cari kode saham<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Contoh: BBCA" maxLength={8} /></label>
      <p>{visible.length} saham sesuai pencarian · urutan alfabet, tanpa ranking rekomendasi.</p>
      <ul className="eod-grid" aria-label="Data saham harian">{visible.map(row => <li key={row.symbol} className="eod-card">
        <h2>{row.symbol}</h2><p className="muted">Tanggal data: {dateLabel(row.date)}{row.stale ? ' · Tertinggal' : ''}</p>
        <dl className="plan-grid"><div><dt>Harga penutupan</dt><dd>{rupiah.format(Number(row.close_idr))}</dd></div>
          <div><dt>Return harian adjusted</dt><dd>{row.return_1d === null ? 'Belum tersedia' : `${(Number(row.return_1d) * 100).toFixed(2)}%`}</dd></div>
          <div><dt>Volume penyedia</dt><dd>{integer.format(BigInt(row.volume))}</dd></div>
          <div><dt>RSI 14 penyedia</dt><dd>{row.rsi_14 === null ? 'Belum tersedia' : Number(row.rsi_14).toFixed(2)}</dd></div></dl>
      </li>)}</ul>
      {!visible.length && <p>Tidak ada saham yang cocok.</p>}
    </>}
  </main>;
}

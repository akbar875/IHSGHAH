'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { publicConfig } from '@/lib/config';

import { parseDailyMarket as parse, type DailyData } from '@/lib/daily-market';
const source = 'https://dataset.aethereal.top/datasets/idx-stock-features';
const license = 'https://creativecommons.org/licenses/by/4.0/';
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
    const apiBase = new URL(`${publicConfig.apiBaseUrl}/`, window.location.origin);
    fetch(new URL('../research/eod', apiBase), { credentials: 'include', cache: 'no-store', signal: controller.signal })
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
    <Link href="/">← Daftar bullish & bearish</Link><h1>Riset saham harian</h1>
    <p>Data pasar harian gratis · Aethereal · Lingkungan research</p>
    <section className="notice" aria-label="Batas penggunaan"><div><h2>Data akhir hari</h2><p>Harga penutupan dan indikator historis untuk riset harian. Sinyal intraday, peluang profit, dan eksekusi paper live belum diaktifkan.</p></div></section>
    <p role="status">{status}</p>
    {!data && <p>Data harian dapat dibaca langsung tanpa kode akses. Coba muat ulang jika sumber data belum tersedia.</p>}
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
        <h2><Link href={`/stocks/${encodeURIComponent(row.symbol)}?source=daily`} aria-label={`Lihat detail ${row.symbol}`}>{row.symbol} →</Link></h2><p className="muted">Tanggal data: {dateLabel(row.date)}{row.stale ? ' · Tertinggal' : ''}</p>
        <dl className="plan-grid"><div><dt>Harga penutupan</dt><dd>{rupiah.format(Number(row.close_idr))}</dd></div>
          <div><dt>Return harian adjusted</dt><dd>{row.return_1d === null ? 'Belum tersedia' : `${(Number(row.return_1d) * 100).toFixed(2)}%`}</dd></div>
          <div><dt>Volume penyedia</dt><dd>{integer.format(BigInt(row.volume))}</dd></div>
          <div><dt>RSI 14 penyedia</dt><dd>{row.rsi_14 === null ? 'Belum tersedia' : Number(row.rsi_14).toFixed(2)}</dd></div></dl>
      </li>)}</ul>
      {!visible.length && <p>Tidak ada saham yang cocok.</p>}
    </>}
  </main>;
}

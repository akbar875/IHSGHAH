'use client';

import { useEffect, useState } from 'react';
import { publicConfig } from '@/lib/config';

type Candidate = {
  symbol: string; date: string; direction: 'bullish' | 'bearish'; reference: string;
  take_profit: string; stop_loss: string; potential_pct: string; risk_pct: string;
  reward_risk: string; rsi_14: string; momentum_20d_pct: string;
};
type Result = {
  method: string; latest_date: string; available_at: string; stale: boolean;
  source: string; license_url: string; attribution: string; rows: Candidate[];
  universe_count: number; needs_reimport: boolean;
};
const finite = (v: unknown) => typeof v === 'string' && v.trim() !== '' && Number.isFinite(Number(v));
function parse(value: unknown): Result {
  const data = value as Result;
  if (!data || data.method !== 'ma-rsi-momentum-2r-v1' || !Array.isArray(data.rows) || data.rows.length > 2000 ||
      !/^\d{4}-\d{2}-\d{2}$/.test(data.latest_date) || !Number.isFinite(Date.parse(data.latest_date)) ||
      !Number.isFinite(Date.parse(data.available_at)) || typeof data.stale !== 'boolean' ||
      typeof data.needs_reimport !== 'boolean' || !Number.isSafeInteger(data.universe_count) || data.universe_count < data.rows.length ||
      typeof data.attribution !== 'string' || data.source !== 'https://dataset.aethereal.top/datasets/idx-stock-features' ||
      data.license_url !== 'https://creativecommons.org/licenses/by/4.0/' ||
      new Set(data.rows.map(r => r?.symbol)).size !== data.rows.length ||
      (data.stale && data.rows.length > 0) || data.rows.some(r => {
        if (!r || !/^[A-Z][A-Z0-9]{1,7}$/.test(r.symbol) || r.date !== data.latest_date ||
            !['bullish', 'bearish'].includes(r.direction) ||
            ![r.reference, r.take_profit, r.stop_loss, r.potential_pct, r.risk_pct, r.reward_risk, r.rsi_14, r.momentum_20d_pct].every(finite)) return true;
        const [entry, tp, sl, potential, risk, rr, rsi] = [r.reference, r.take_profit, r.stop_loss, r.potential_pct, r.risk_pct, r.reward_risk, r.rsi_14].map(Number);
        return entry < 50 || tp < 50 || sl <= 0 || risk < 1 || risk > 10 || rr < 2 || rsi < 0 || rsi > 100 ||
          (r.direction === 'bullish' ? !(tp > entry && entry > sl && potential > 0) : !(tp < entry && entry < sl && potential < 0)) ||
          Math.abs(potential - (tp / entry - 1) * 100) > 0.001 ||
          Math.abs(risk - Math.abs(sl / entry - 1) * 100) > 0.001 ||
          Math.abs(rr - Math.abs(tp - entry) / Math.abs(sl - entry)) > 0.001;
      })) throw new Error('Hasil analisis tidak valid.');
  return data;
}
const price = (v: string) => new Intl.NumberFormat('id-ID', { maximumFractionDigits: 2 }).format(Number(v));
const pct = (v: string, signed = false) => `${signed && Number(v) > 0 ? '+' : ''}${Number(v).toFixed(2)}%`;

export default function Screener() {
  const [data, setData] = useState<Result | null>(null);
  const [status, setStatus] = useState('Memuat analisis saham…');
  const [retry, setRetry] = useState(0);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('semua');
  useEffect(() => {
    const controller = new AbortController();
    let disposed = false;
    const timeout = setTimeout(() => controller.abort(), 10000);
    const base = new URL(`${publicConfig.apiBaseUrl}/`, window.location.origin);
    fetch(new URL('../research/screener', base), { credentials: 'include', cache: 'no-store', signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error([401, 403].includes(response.status) ? 'Masuk dengan sesi research untuk melihat analisis.' : 'Data belum tersedia. Impor data harian pada backend, lalu coba lagi.');
        return parse(await response.json());
      })
      .then(result => { if (!disposed) { setData(result); setStatus('Analisis selesai.'); } })
      .catch(error => { if (!disposed) { setData(null); setStatus(error instanceof Error && error.name !== 'AbortError' ? error.message : 'Analisis gagal dimuat. Coba lagi.'); } })
      .finally(() => clearTimeout(timeout));
    return () => { disposed = true; controller.abort(); clearTimeout(timeout); };
  }, [retry]);
  const visible = data?.rows.filter(row => row.symbol.includes(query.trim().toUpperCase()) && (filter === 'semua' || row.direction === filter)) ?? [];
  return <main className="signal-page">
    <header className="signal-heading"><div><p className="eyebrow">SAHAM SIGNAL · BEI</p><h1>Saham mana yang berpotensi bergerak?</h1><p className="intro">Bullish & bearish, lengkap dengan target harga dan batas risiko.</p></div>
      <button onClick={() => { setData(null); setStatus('Memuat analisis saham…'); setRetry(n => n + 1); }}>Perbarui analisis ↻</button></header>
    <div className="signal-meta"><span>Teknikal harian · skenario 5–15 sesi bursa</span><span>{data ? `Data ${new Date(`${data.latest_date}T00:00:00+07:00`).toLocaleDateString('id-ID', { timeZone: 'Asia/Jakarta', day: 'numeric', month: 'long', year: 'numeric' })}` : 'Menunggu data pasar'}</span></div>
    <div className="signal-controls"><div className="signal-tabs" role="group" aria-label="Filter arah">{['semua', 'bullish', 'bearish'].map(value => <button key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>{value === 'semua' ? 'Semua' : value === 'bullish' ? '↗ Bullish' : '↘ Bearish'}{data ? ` (${data.rows.filter(r => value === 'semua' || r.direction === value).length})` : ''}</button>)}</div>
      <label>Cari saham<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Kode saham, mis. BBCA" maxLength={8} /></label></div>
    <p className="muted" role="status">{status}</p>
    {data && <>
      {data.stale && <p className="signal-warning">Data sudah tertinggal lebih dari 7 hari. Perbarui sumber untuk mendapatkan daftar kandidat.</p>}
      {data.needs_reimport && <p className="signal-warning">Snapshot lama belum berisi indikator tren. Impor ulang data harian untuk menghitung kandidat dan TP/SL.</p>}
      <div className="signal-grid" aria-label="Hasil analisis saham">{visible.map(row => <article className={`signal-card ${row.direction}`} key={row.symbol}>
        <div className="signal-card-heading"><h2>{row.symbol}</h2><span className="direction">{row.direction === 'bullish' ? '↗ Bullish' : '↘ Bearish'}</span></div>
        <p className="signal-potential">{pct(row.potential_pct, true)}<span>potensi ke target</span></p>
        <dl className="signal-levels"><div><dt>Harga acuan</dt><dd>Rp {price(row.reference)}</dd></div><div><dt>{row.direction === 'bullish' ? 'Take profit' : 'Target penurunan'}</dt><dd className="target">Rp {price(row.take_profit)}</dd></div><div><dt>{row.direction === 'bullish' ? 'Stop loss' : 'Batas invalidasi'}</dt><dd>Rp {price(row.stop_loss)}</dd></div></dl>
        <p className="signal-risk">Risiko {pct(row.risk_pct)} <span>·</span> Reward/risk 1:{Number(row.reward_risk).toFixed(2)}</p>
        <p className="signal-reason">{row.direction === 'bullish' ? 'Harga > MA20 > MA50 > MA200' : 'Harga < MA20 < MA50 < MA200'} · RSI {Number(row.rsi_14).toFixed(0)} · momentum 20 hari {pct(row.momentum_20d_pct, true)}</p>
        {row.direction === 'bearish' && <p className="muted">Waspada untuk posisi beli. Target/invalidasi bearish bukan TP/SL posisi beli atau instruksi short.</p>}
      </article>)}</div>
      {!visible.length && <div className="signal-empty"><h2>Belum ada saham yang memenuhi kriteria.</h2><p>Ubah filter atau perbarui data. Saham netral dan data yang tidak lengkap tidak dimasukkan.</p></div>}
      <p className="muted">{visible.length} kandidat dari {data.universe_count} saham · urutan alfabet</p>
    </>}
    <footer className="signal-footer"><p>Target adalah skenario teknikal, bukan prediksi pasti atau peluang profit terkalibrasi. Harga acuan memakai penutupan harian; hitung ulang jika harga masuk berubah. Belum memperhitungkan biaya, slippage, atau gap.</p>
      <details><summary>Dasar analisis & sumber</summary><p>Konfirmasi tren MA20/50/200, RSI14, momentum 20 hari, dan rata-rata nilai transaksi ≥ Rp1 miliar/hari. Stop di MA20 dengan buffer 1%; target minimal dua kali jarak risiko (2R), dibulatkan ke fraksi harga reguler. Jarak stop dibatasi 1–10%. Rentang 5–15 sesi adalah horizon tinjauan, bukan estimasi waktu tercapainya target.</p>
        <p>Pendekatan filter tren MA dan momentum RSI mengacu pada <a href="https://github.com/sapatekno/skill-saham">skill-saham di GitHub</a>. Ini implementasi aturan tersendiri; bukan eksekusi engine lengkap repo tersebut. MACD, ADX, dan ATR belum tersedia dalam snapshot ini.</p>
        <p>Data: <a href="https://dataset.aethereal.top/datasets/idx-stock-features">Aethereal</a> · <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. {data?.attribution}</p></details></footer>
  </main>;
}

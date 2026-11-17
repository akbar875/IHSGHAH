'use client';

import Link from 'next/link';
import { useState } from 'react';
import { useDailyResource } from '@/lib/use-daily-resource';
import { parseScreener } from '@/lib/screener';

const price = (v: string) => new Intl.NumberFormat('id-ID', { maximumFractionDigits: 2 }).format(Number(v));
const pct = (v: string, signed = false) => `${signed && Number(v) > 0 ? '+' : ''}${Number(v).toFixed(2)}%`;

export default function Screener() {
  const [retry, setRetry] = useState(0);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('semua');
  const resource = useDailyResource('screener', parseScreener, retry);
  const data = resource.data;
  const status = resource.loading ? 'Memuat analisis saham…' : resource.error ?? 'Analisis selesai.';
  const visible = data?.rows.filter(row => row.symbol.includes(query.trim().toUpperCase()) && (filter === 'semua' || row.direction === filter)) ?? [];
  return <main className="signal-page">
    <header className="signal-heading"><div><p className="eyebrow">SAHAM SIGNAL · BEI · RESEARCH</p><h1>Sinyal teknikal</h1><p className="intro">Temukan kandidat bullish & bearish, lalu klik kode saham untuk melihat chart, target harga, dan backtest historis.</p></div>
      <button disabled={resource.loading} onClick={() => setRetry(n => n + 1)}>{resource.loading ? 'Memuat analisis…' : 'Perbarui analisis ↻'}</button></header>
    <section className="signal-guide" aria-label="Cara melihat saham">
      <h2>Mulai dari sini</h2><ol><li><strong>1. Cari saham</strong><span>Ketik kode atau pilih arah tren.</span></li><li><strong>2. Buka detail</strong><span>Klik baris saham untuk chart & backtest.</span></li><li><strong>3. Tinjau skenario</strong><span>Bandingkan harga acuan, target, dan risiko.</span></li></ol>
      <Link href="/research">Lihat semua saham di data harian →</Link>
    </section>
    <div className="signal-meta"><span>Data harian · diperiksa otomatis setiap 15 detik, bukan feed real time</span><span>{data ? `Data ${new Date(`${data.latest_date}T00:00:00+07:00`).toLocaleDateString('id-ID', { timeZone: 'Asia/Jakarta', day: 'numeric', month: 'long', year: 'numeric' })}` : resource.loading ? 'Menghubungkan ke sumber data…' : 'Data gagal dimuat'}</span></div>
    {data && <dl className="signal-summary" aria-label="Ringkasan analisis"><div><dt>Saham diperiksa</dt><dd>{data.universe_count}</dd></div><div><dt>Kandidat bullish</dt><dd>{data.rows.filter(row => row.direction === 'bullish').length}</dd></div><div><dt>Kandidat bearish</dt><dd>{data.rows.filter(row => row.direction === 'bearish').length}</dd></div></dl>}
    {!resource.loading && resource.error && <section className="signal-problem" aria-labelledby="problem-title">
      <span className="problem-icon" aria-hidden="true">!</span><div><h2 id="problem-title">{resource.errorStatus === 403 ? 'Akses research dibatasi' : 'Daftar saham belum dapat dimuat'}</h2>
      <p>{resource.errorStatus === 503 ? 'Sumber data harian belum siap atau tidak dapat dibaca. Minta pengelola memperbarui data, lalu coba lagi.' : resource.errorStatus === 403 ? 'Sesi atau lingkungan aplikasi tidak mengizinkan akses research. Hubungi pengelola untuk memeriksa akses.' : 'Periksa koneksi dan coba lagi. Jika masalah berlanjut, minta pengelola memeriksa sumber data.'}</p>
      <div className="signal-actions"><button onClick={() => setRetry(n => n + 1)}>Coba lagi</button><a href="#cara-membaca">Pelajari cara membaca analisis ↓</a></div></div>
    </section>}
    {resource.loading && <div className="signal-loading" aria-hidden="true"><div /><div /><div /></div>}
    <section className="signal-results" aria-label="Kandidat saham">
    <h2>Kandidat analisis</h2><p className="muted">Daftar ini hanya memuat saham yang memenuhi kriteria tren. Untuk saham lainnya, buka <Link href="/research">data harian</Link>.</p>
    <div className="signal-controls"><div className="signal-tabs" role="group" aria-label="Filter arah">{['semua', 'bullish', 'bearish'].map(value => <button key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>{value === 'semua' ? 'Semua' : value === 'bullish' ? '↗ Bullish' : '↘ Bearish'}{data ? ` (${data.rows.filter(r => value === 'semua' || r.direction === value).length})` : ''}</button>)}</div>
      <label>Cari saham<input value={query} disabled={!data} onChange={event => setQuery(event.target.value)} placeholder="Kode saham, mis. BBCA" maxLength={8} /></label></div>
    <p className="muted" role="status">{status}</p>
    {data && <>
      {data.stale && <p className="signal-warning">Data sudah tertinggal lebih dari 7 hari. Perbarui sumber untuk mendapatkan daftar kandidat.</p>}
      {data.needs_reimport && <p className="signal-warning">Snapshot lama belum berisi indikator tren. Impor ulang data harian untuk menghitung kandidat dan TP/SL.</p>}
      <div className="stock-list" aria-label="Hasil analisis saham">{visible.map(row => <article className={`stock-list-row ${row.direction}`} key={row.symbol}>
        <Link className="stock-row-link" href={`/stocks/${encodeURIComponent(row.symbol)}?source=daily`} aria-label={`Lihat detail ${row.symbol}`}>
          <div className="stock-row-name"><h2>{row.symbol}</h2><span className="direction">{row.direction === 'bullish' ? '↗ Bullish' : '↘ Bearish'}</span></div>
          <dl className="stock-row-levels"><div><dt>Harga acuan</dt><dd>Rp {price(row.reference)}</dd></div><div><dt>Potensi ke target</dt><dd className="target">{pct(row.potential_pct, true)}</dd></div><div><dt>{row.direction === 'bullish' ? 'Take profit' : 'Target penurunan'}</dt><dd>Rp {price(row.take_profit)}</dd></div><div><dt>{row.direction === 'bullish' ? 'Stop loss' : 'Batas invalidasi'}</dt><dd>Rp {price(row.stop_loss)}</dd></div></dl>
          <span className="stock-row-arrow" aria-hidden="true">↗</span>
        </Link>
      </article>)}</div>
      {!visible.length && <div className="signal-empty"><h2>{query || filter !== 'semua' ? 'Tidak ada kandidat yang cocok dengan filter.' : 'Belum ada saham yang memenuhi kriteria.'}</h2><p>{query || filter !== 'semua' ? 'Coba kode lain atau tampilkan semua kandidat.' : 'Data berhasil dimuat, tetapi belum ada kandidat tren. Saham netral dan data yang tidak lengkap tidak dimasukkan.'}</p><div className="signal-actions">{(query || filter !== 'semua') && <button onClick={() => { setQuery(''); setFilter('semua'); }}>Reset pencarian & filter</button>}<Link href="/research">Jelajahi semua saham →</Link></div></div>}
      <p className="muted">{visible.length} kandidat dari {data.universe_count} saham · urutan alfabet{resource.checked && ` · Diperiksa ${new Date(resource.checked).toLocaleTimeString('id-ID', { timeZone: 'Asia/Jakarta' })} WIB`}</p>
    </>}
    </section>
    <section className="signal-explainer" id="cara-membaca" aria-label="Cara membaca analisis"><h2>Cara membaca analisis</h2><dl><div><dt>↗ Bullish</dt><dd>Tren naik terkonfirmasi oleh aturan teknikal.</dd></div><div><dt>↘ Bearish</dt><dd>Tren turun; target menunjukkan skenario penurunan.</dd></div><div><dt>Target & batas risiko</dt><dd>Skenario dari harga penutupan, dengan batas saat analisis tidak berlaku.</dd></div></dl></section>
    <footer className="signal-footer"><p>Target adalah skenario teknikal, bukan prediksi pasti atau peluang profit terkalibrasi. Harga acuan memakai penutupan harian; hitung ulang jika harga masuk berubah. Belum memperhitungkan biaya, slippage, atau gap.</p>
      <details><summary>Dasar analisis & sumber</summary><p>Konfirmasi tren MA20/50/200, RSI14, momentum 20 hari, dan rata-rata nilai transaksi ≥ Rp1 miliar/hari. Stop di MA20 dengan buffer 1%; target minimal dua kali jarak risiko (2R), dibulatkan ke fraksi harga reguler. Jarak stop dibatasi 1–10%. Rentang 5–15 sesi adalah horizon tinjauan, bukan estimasi waktu tercapainya target.</p>
        <p>Pendekatan filter tren MA dan momentum RSI mengacu pada <a href="https://github.com/sapatekno/skill-saham">skill-saham di GitHub</a>. Ini implementasi aturan tersendiri; bukan eksekusi engine lengkap repo tersebut. MACD, ADX, dan ATR belum tersedia dalam snapshot ini.</p>
        <p>Data: <a href="https://dataset.aethereal.top/datasets/idx-stock-features">Aethereal</a> · <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. {data?.attribution}</p></details></footer>
  </main>;
}

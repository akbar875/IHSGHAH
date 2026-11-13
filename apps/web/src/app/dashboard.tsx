'use client';

import Link from 'next/link';
import { useEffect, useState, type FormEvent } from 'react';
import { fetchCandidates, MarketError, money, nominalValue, statusMessages, time, type Candidate } from '@/lib/market';
import type { CandidatesResponse } from '@/lib/generated/candidates';

type Result = { key: string; response: CandidatesResponse | null; error: string | null };
const labels = { WATCH: 'Tunggu', READY: 'Siap masuk', EXPIRED: 'Kedaluwarsa', CANCELLED: 'Dibatalkan' };

function CandidateCard({ signal, rank, now, blocked }: { signal: Candidate; rank: number; now: number; blocked: boolean }) {
  const expired = now >= Date.parse(signal.valid_until) || now >= Date.parse(signal.entry_until);
  const state = expired && ['WATCH', 'READY'].includes(signal.state) ? 'EXPIRED' : signal.state;
  return <article className="candidate" aria-label={`Kandidat ${signal.symbol}`}>
    <div className="candidate-heading">
      <div className="ticker"><span className="rank">{rank.toString().padStart(2, '0')}</span><div><h3>{signal.symbol}</h3><span className="muted">Simulasi · {signal.horizon_minutes} menit</span></div></div>
      <span className={`tag ${state === 'READY' && !blocked ? 'ready' : ''}`}>{state === 'READY' && blocked ? 'Entry ditahan' : labels[state]}</span>
    </div>
    <dl className="plan-grid">
      <div className="entry"><dt>Zona entry</dt><dd>{money(signal.entry_zone.lower_idr)} – {money(signal.entry_zone.upper_idr)}</dd></div>
      <div><dt>Stop loss</dt><dd>{money(signal.stop_idr)}</dd></div>
      <div><dt>Target TP1</dt><dd>{money(signal.targets_idr[0])}</dd></div>
      {signal.targets_idr[1] && <div><dt>Target TP2</dt><dd>{money(signal.targets_idr[1])}</dd></div>}
      <div><dt>Peluang target</dt><dd>{signal.target_probability.value === null ? 'Tidak tersedia' : `${(signal.target_probability.value * 100).toLocaleString('id-ID')}%`}</dd></div>
      <div><dt>Estimasi hasil bersih</dt><dd>{signal.return_quantiles === null ? 'Tidak tersedia' : `${(Number(signal.return_quantiles.p50) * 100).toLocaleString('id-ID')}%`}</dd></div>
      <div><dt>Peluang masuk / keluar</dt><dd>Tidak tersedia</dd></div>
      <div><dt>Nominal rencana</dt><dd>{money(signal.assumptions.nominal_idr)}</dd></div>
    </dl>
    <dl className="timing-grid">
      <div><dt>Jendela entry</dt><dd>{time(signal.entry_from)} – {time(signal.entry_until)}</dd></div>
      <div><dt>Batas exit</dt><dd>{time(signal.exit_deadline)}</dd></div>
      <div><dt>Berlaku sampai</dt><dd>{time(signal.valid_until)}</dd></div>
      <div><dt>Waktu data kandidat</dt><dd>{time(signal.data_as_of)}</dd></div>
    </dl>
    {(blocked || expired) && <p className="entry-warning">Entry ditahan · {expired ? 'rencana kedaluwarsa' : 'data atau model belum siap'}</p>}
  </article>;
}

export default function Dashboard() {
  const [input, setInput] = useState('1000000');
  const [nominal, setNominal] = useState('1000000.00');
  const [inputError, setInputError] = useState('');
  const [query, setQuery] = useState('');
  const [activeOnly, setActiveOnly] = useState(true);
  const [revision, setRevision] = useState(0);
  const [now, setNow] = useState(0);
  const [result, setResult] = useState<Result>({ key: '', response: null, error: null });
  const key = `${nominal}:${revision}`;
  const loading = result.key !== key;
  const response = loading ? null : result.response;
  const error = loading ? null : result.error;

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
        const data = await fetchCandidates(nominal, controller.signal);
        if (!disposed) {
          setNow(Date.now());
          setResult({ key, response: data, error: null });
        }
      } catch (cause) {
        if (!disposed) setResult({ key, response: null, error: cause instanceof MarketError ? cause.message : 'Koneksi terputus. Periksa koneksi lalu coba lagi.' });
      } finally {
        clearTimeout(timeout);
        pending = false;
      }
    }
    void load();
    const refresh = setInterval(() => void load(), 15000);
    return () => { disposed = true; clearInterval(refresh); controller?.abort(); };
  }, [key, nominal]);

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  function applyNominal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = nominalValue(input);
    if (!value) { setInputError('Masukkan nominal rupiah bulat antara 1 dan 999999999999.'); return; }
    setInputError('');
    setNominal(value);
    setRevision(v => v + 1);
  }

  const messages = response ? statusMessages(response) : [];
  const candidates = response?.data.map((signal, index) => ({ signal, rank: index + 1 })).filter(({ signal }) =>
    signal.symbol.includes(query.trim().toUpperCase()) && (!activeOnly || (
      ['WATCH', 'READY'].includes(signal.state) && Date.parse(signal.valid_until) > now && Date.parse(signal.entry_until) > now
    ))) ?? [];
  const blocked = !response || response.quality.status !== 'healthy' || response.quality.feed !== 'live' || response.quality.reasons.length > 0;
  const feed = !response ? 'Belum terhubung' : ({ live: 'Live', delayed: 'Delayed', disconnected: 'Terputus', unavailable: 'Belum tersedia' })[response.quality.feed];

  return <>
    <a className="skip-link" href="#utama">Lewati ke konten</a>
    <header className="header">
      <Link className="brand" href="/" aria-label="Saham Signal, beranda"><span className="brand-icon" aria-hidden="true">S</span><span>Saham<span className="brand-light"> Signal</span></span></Link>
      <span className="mode">Research / Simulasi</span>
    </header>
    <main id="utama" className="workspace">
      <div className="eyebrow">RUANG KERJA RESEARCH</div>
      <h1>Kandidat saham.</h1>
      <p className="intro">Tinjau rencana, risiko, dan jendela entry sesuai nominal Anda.</p>
      <section className="notice" aria-labelledby="simulation-title"><span className="notice-icon" aria-hidden="true">i</span><div>
        <h2 id="simulation-title">Lingkungan simulasi</h2>
        <p>Seluruh harga dan kandidat adalah data sintetis untuk mencoba tampilan. Belum ada feed pasar atau model tervalidasi. Jangan gunakan untuk transaksi nyata.</p>
      </div></section>
      <dl className="status-grid overview">
        <div><dt>Sesi pasar</dt><dd>{response?.quality.reasons.includes('MARKET_CLOSED') ? 'Pasar tutup' : 'Tidak tersedia'}</dd></div>
        <div><dt>Status data</dt><dd>{error ? 'Terputus / tidak tersedia' : feed}{response?.quality.status === 'stale' ? ' · Kedaluwarsa' : ''}</dd></div>
        <div><dt>Data terakhir</dt><dd>{response ? time(response.as_of) : 'Tidak tersedia'}</dd></div>
        <div><dt>Nominal diterapkan</dt><dd>{money(nominal)}</dd></div>
      </dl>
      <section className="panel" aria-labelledby="candidates-title">
        <div className="panel-heading"><h2 id="candidates-title">Daftar kandidat</h2><span className="tag">Simulasi</span></div>
        <div className="controls">
          <form className="nominal-form" onSubmit={applyNominal}>
            <label htmlFor="nominal">Nominal transaksi (Rp)</label>
            <div className="input-action"><input id="nominal" inputMode="numeric" value={input} onChange={e => setInput(e.target.value)} aria-invalid={!!inputError} aria-describedby={inputError ? 'nominal-error' : undefined} /><button type="submit">Terapkan</button></div>
            {inputError && <p id="nominal-error" className="field-error" role="alert">{inputError}</p>}
          </form>
          <div className="search-control"><label htmlFor="search">Cari kode saham</label><input id="search" type="search" placeholder="Cari ticker, mis. TEST" value={query} onChange={e => setQuery(e.target.value)} /></div>
          <label className="checkbox"><input type="checkbox" checked={activeOnly} onChange={e => setActiveOnly(e.target.checked)} />Kandidat aktif</label>
        </div>
        <div className="results" aria-live="polite" aria-busy={loading}>
          {loading ? <div className="empty-state"><span className="empty-icon" aria-hidden="true">…</span><h3>Memuat kandidat…</h3><p>Menyiapkan daftar untuk nominal {money(nominal)}.</p></div>
            : error ? <div className="empty-state"><h3>Data belum dapat dimuat</h3><p>{error}</p><button className="retry" onClick={() => setRevision(v => v + 1)}>Coba lagi</button></div>
            : response && <>
              {messages.length > 0 && <div className="data-notices">{messages.map(message => <p key={message}>{message}</p>)}</div>}
              <div className="results-heading"><span>{candidates.length} kandidat</span><span>Urutan dari layanan · simulasi</span></div>
              {candidates.length ? candidates.map(({ signal, rank }) => <CandidateCard key={signal.signal_id} signal={signal} rank={rank} now={now} blocked={blocked || signal.target_probability.status !== 'validated'} />)
                : <div className="empty-state"><span className="empty-icon" aria-hidden="true">—</span><h3>{query.trim() ? 'Tidak ada kandidat yang cocok' : 'Belum ada kandidat aktif'}</h3><p>{query.trim() ? 'Coba kode saham lain atau hapus pencarian.' : 'Daftar boleh kosong. Tunggu pembaruan data atau sesuaikan filter kandidat aktif.'}</p></div>}
            </>}
        </div>
      </section>
      <p className="footnote">READY tidak membuka posisi. Keputusan dan pencatatan transaksi tetap dilakukan secara manual.</p>
    </main>
    <footer className="footer"><span>Saham Signal</span><span>Research / Simulasi · Asia/Jakarta</span></footer>
  </>;
}

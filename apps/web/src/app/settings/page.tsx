'use client';

import Link from 'next/link';
import { useEffect, useState, type FormEvent } from 'react';
import { preference } from '@/lib/preferences';
import { money } from '@/lib/market';
import type { RiskProfile, SettingsEligibility } from '@/lib/generated/candidates';

type Fields = { nominal: string; capital: string; risk: string; combined: string; positions: string; buy: string; sell: string; from: string; to: string; source: string };
const empty: Fields = { nominal: '', capital: '', risk: '', combined: '', positions: '', buy: '', sell: '', from: '', to: '', source: '' };
function fields(settings: RiskProfile): Fields {
  const fee = settings.fee_schedule;
  return { nominal: settings.nominal_idr, capital: settings.capital_idr, risk: settings.risk_per_position_ratio,
    combined: settings.max_combined_risk_ratio, positions: String(settings.max_positions), buy: fee?.buy_ratio ?? '', sell: fee?.sell_ratio ?? '',
    from: fee.effective_from.slice(0, -1), to: fee.effective_to.slice(0, -1), source: fee.source };
}
const labels: [keyof Fields, string, string][] = [
  ['nominal', 'Nominal transaksi (Rp)', 'text'], ['capital', 'Modal (Rp)', 'text'],
  ['risk', 'Risiko per posisi (rasio, maksimal 0.01)', 'text'], ['combined', 'Risiko gabungan (rasio, maksimal 0.02)', 'text'],
  ['positions', 'Maksimum posisi (1–3)', 'text'], ['buy', 'Biaya beli (rasio)', 'text'], ['sell', 'Biaya jual (rasio)', 'text'],
  ['from', 'Biaya berlaku mulai (UTC)', 'datetime-local'], ['to', 'Biaya berakhir sebelum (UTC)', 'datetime-local'], ['source', 'Sumber asumsi biaya', 'text'],
];
function fixed(value: string, digits: number): string {
  if (!new RegExp(`^(?:0|[1-9][0-9]{0,15})(?:\\.[0-9]{1,${digits}})?$`).test(value)) throw new Error('Gunakan angka positif dengan titik desimal; tanpa pemisah ribuan.');
  const [whole, fraction = ''] = value.split('.');
  return `${whole}.${fraction.padEnd(digits, '0')}`;
}

export default function SettingsPage() {
  const [form, setForm] = useState<Fields>(empty);
  const [symbols, setSymbols] = useState<string[]>([]);
  const [ticker, setTicker] = useState('');
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [evaluation, setEvaluation] = useState<SettingsEligibility | null>(null);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let disposed = false;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    Promise.all([preference('/settings/profile', undefined, controller.signal), preference('/watchlist', undefined, controller.signal), preference('/settings/eligibility', undefined, controller.signal)])
      .then(([risk, watchlist, result]) => {
        if (disposed) return;
        setForm(risk ? fields(risk.data) : empty); setSymbols(watchlist?.data.symbols ?? []);
        setEvaluation(result?.data.configuration_version === risk?.data.configuration_version ? result?.data ?? null : null); setError('');
        setLoaded(true);
      }).catch(cause => { if (!disposed) setError(cause instanceof Error ? cause.message : 'Gagal memuat pengaturan.'); })
      .finally(() => { clearTimeout(timeout); if (!disposed) setLoading(false); });
    return () => { disposed = true; controller.abort(); clearTimeout(timeout); };
  }, [reload]);

  async function saveRisk(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setMessage(''); setEvaluation(null);
    try {
      const feeVersion = `fee-${crypto.randomUUID()}`;
      const data: RiskProfile = { configuration_version: `config-${crypto.randomUUID()}`, nominal_idr: fixed(form.nominal, 2), capital_idr: fixed(form.capital, 2),
        risk_per_position_ratio: fixed(form.risk, 6), max_combined_risk_ratio: fixed(form.combined, 6), max_positions: Number(form.positions), fee_schedule_version: feeVersion,
        fee_schedule: { version: feeVersion, buy_ratio: fixed(form.buy, 6), sell_ratio: fixed(form.sell, 6), effective_from: new Date(`${form.from}Z`).toISOString(),
          effective_to: new Date(`${form.to}Z`).toISOString(), source: form.source.trim(), verification: 'user_assumption' } };
      const saved = await preference('/settings/profile', data);
      if (saved) setForm(fields(saved.data));
      setMessage('Pengaturan tersimpan. Kandidat dan kelayakan memakai konfigurasi baru.');
      const result = await preference('/settings/eligibility');
      if (result?.data.configuration_version !== saved?.data.configuration_version) throw new Error('Konfigurasi berubah. Muat ulang untuk menampilkan kelayakan terkini.');
      setEvaluation(result?.data ?? null);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Gagal menyimpan pengaturan.'); }
    finally { setBusy(false); }
  }
  async function saveWatchlist(next: string[]) {
    setBusy(true); setError(''); setMessage('');
    try { const saved = await preference('/watchlist', { symbols: next }); if (saved) setSymbols(saved.data.symbols); setTicker(''); setMessage('Watchlist tersimpan.'); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Gagal menyimpan watchlist.'); }
    finally { setBusy(false); }
  }
  function add(event: FormEvent) {
    event.preventDefault(); const value = ticker.trim().toUpperCase();
    if (!/^[A-Z][A-Z0-9.]{0,11}$/.test(value) || symbols.includes(value) || symbols.length >= 200) { setError('Kode saham tidak valid, duplikat, atau batas 200 saham tercapai.'); return; }
    void saveWatchlist([...symbols, value]);
  }

  return <>
    <header className="header"><Link className="brand" href="/">Saham Signal</Link><span className="mode">Research / Simulasi</span></header>
    <main className="workspace preferences-workspace"><Link href="/">← Kembali ke kandidat</Link><h1>Pengaturan & watchlist.</h1>
      <p className="intro">Simpan rencana dan saham yang Anda pantau untuk akun ini.</p>
      <section className="notice"><div><h2>Biaya adalah asumsi pengguna</h2><p>Belum diverifikasi oleh broker. Masukkan tarif lengkap Anda sebagai rasio (contoh format: 0.001500), sumber dan masa berlaku. Angka contoh bukan rekomendasi tarif.</p><p>Batas desain pilot: risiko per posisi ≤ 1%, gabungan ≤ 2%, maksimal 3 posisi. Batas ini bukan jaminan kerugian.</p></div></section>
      {loading && <p role="status">Memuat pengaturan…</p>}
      {error && <div role="alert" className="field-error"><p>{error}</p><button onClick={() => { setLoading(true); setReload(v => v + 1); }}>Muat ulang</button></div>}
      {message && <p role="status">{message}</p>}
      <section className="panel"><h2>Nominal, risiko & biaya</h2><form onSubmit={saveRisk}>
        <fieldset disabled={loading || busy || !loaded} className="settings-fields"><legend>Konfigurasi rencana</legend>
          {labels.map(([key, label, type]) => <label key={key} htmlFor={`setting-${key}`}>{label}<input id={`setting-${key}`} type={type} step={type === 'datetime-local' ? 'any' : undefined} required maxLength={key === 'source' ? 256 : 30} value={form[key]} onChange={e => setForm({ ...form, [key]: e.target.value })} /></label>)}
          <button type="submit">{busy ? 'Menyimpan…' : 'Simpan pengaturan'}</button>
        </fieldset>
      </form></section>
      {evaluation && <section className="panel" aria-label="Kelayakan simulasi"><h2>Anggaran simulasi TEST</h2><p>Risiko per posisi {money(evaluation.risk_budget_idr)} · gabungan {money(evaluation.combined_budget_idr)}.</p><p>Batas lot menurut anggaran: {evaluation.budget_lots_ceiling}. Lot layak eksekusi: {evaluation.eligible_lots}.</p><p>{evaluation.reason === 'FEE_SCHEDULE_EXPIRED' ? 'Biaya belum berlaku atau sudah berakhir. Entry ditahan.' : 'Entry ditahan: feed, model, likuiditas dan portofolio belum tervalidasi. Batas anggaran bukan kapasitas eksekusi atau estimasi fill.'}</p></section>}
      <section className="panel"><h2>Watchlist</h2><p>Daftar tersimpan per akun dan mode. Hanya TEST memiliki data simulasi; ticker lain dapat disimpan tanpa data pasar.</p>
        <form onSubmit={add} className="nominal-form"><label htmlFor="ticker">Tambah kode saham</label><div className="input-action"><input id="ticker" value={ticker} maxLength={12} disabled={busy || loading || !loaded} onChange={e => setTicker(e.target.value)} /><button disabled={busy || loading || !loaded}>Tambah</button></div></form>
        {symbols.length === 0 ? <p>Watchlist kosong.</p> : <ul className="watchlist">{symbols.map(symbol => <li key={symbol}><Link href={`/stocks/${encodeURIComponent(symbol)}`}>{symbol}</Link><button disabled={busy || loading} onClick={() => void saveWatchlist(symbols.filter(s => s !== symbol))} aria-label={`Hapus ${symbol}`}>Hapus</button></li>)}</ul>}
      </section>
    </main>
  </>;
}

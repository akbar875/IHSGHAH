'use client';

import Link from 'next/link';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { positions } from '@/lib/positions';
import { money } from '@/lib/market';
import type { Position, PositionMonitor } from '@/lib/generated/candidates';

const wib = (value: string) => new Date(value).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' });
function amount(value: string) {
  if (!/^(?:0|[1-9][0-9]{0,15})(?:\.[0-9]{1,2})?$/.test(value)) throw new Error('Gunakan angka dengan titik desimal, tanpa pemisah ribuan.');
  const [whole, cents = ''] = value.split('.'); return `${whole}.${cents.padEnd(2, '0')}`;
}
function utc(value: string) { return new Date(`${value}:00+07:00`).toISOString(); }

export default function PositionsPage() {
  const [items, setItems] = useState<Position[]>([]);
  const [detail, setDetail] = useState<PositionMonitor | null>(null);
  const [selected, setSelected] = useState('');
  const [form, setForm] = useState({ symbol: '', side: 'BUY', price: '', lots: '', fees: '', time: '' });
  const [plan, setPlan] = useState({ stop: '', target: '', deadline: '', fee: '' });
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [refresh, setRefresh] = useState(0);
  const pending = useRef<{ payload: string; key: string } | null>(null);
  const lock = useRef(false);
  useEffect(() => {
    const timer = setInterval(() => setRefresh(v => v + 1), 30000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    let disposed = false;
    positions('', 'PositionsResponse').then(result => { if (!disposed) { setItems(result.data); setLoading(false); } })
      .catch(cause => { if (!disposed) { setError(cause.message); setLoading(false); } });
    return () => { disposed = true; };
  }, [refresh]);
  useEffect(() => {
    let disposed = false;
    if (selected) positions(`/${selected}/monitor`, 'PositionMonitorResponse')
      .then(result => { if (!disposed) setDetail(result.data); })
      .catch(cause => { if (!disposed) setError(cause.message); });
    return () => { disposed = true; };
  }, [selected, refresh]);
  async function mutate(path: string, method: 'POST' | 'PUT', body: unknown) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(''); setMessage('');
    const payload = JSON.stringify({ path, method, body });
    // Retain the key for an unchanged retry after timeout or a lost response.
    if (pending.current?.payload !== payload) pending.current = { payload, key: crypto.randomUUID() };
    try {
      if (path.endsWith('/plan')) await positions(path, 'PositionMonitorResponse', { method, body, key: pending.current.key });
      else {
        const result = await positions(path, 'PositionResponse', { method, body, key: pending.current.key });
        setSelected(result.data.position_id); setDetail(null);
      }
      if (!path || path.endsWith('/fills')) setConfirmed(false);
      pending.current = null; setMessage('Catatan tersimpan. Lot hanya berubah berdasarkan fill yang dikonfirmasi.');
      setRefresh(v => v + 1);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Gagal menyimpan.'); }
    finally { lock.current = false; setBusy(false); }
  }
  function record(event: FormEvent) {
    event.preventDefault();
    try {
      const fill = { side: selected ? form.side : 'BUY', price_idr: amount(form.price), lots: Number(form.lots), fees_idr: amount(form.fees), filled_at: utc(form.time) };
      void mutate(selected ? `/${selected}/fills` : '', 'POST', selected ? fill : { symbol: form.symbol.trim().toUpperCase(), signal_id: null, fill });
    } catch (cause) { setError((cause as Error).message); }
  }
  function savePlan(event: FormEvent) {
    event.preventDefault();
    try {
      if (!/^(?:0\.[0-9]{6}|1\.000000)$/.test(plan.fee)) throw new Error('Biaya jual harus rasio enam desimal, misalnya format 0.001000.');
      void mutate(`/${selected}/plan`, 'PUT', { stop_idr: amount(plan.stop), target_idr: amount(plan.target), exit_deadline: utc(plan.deadline), sell_fee_ratio: plan.fee });
    } catch (cause) { setError((cause as Error).message); }
  }
  function choose(id: string) { setSelected(id); setDetail(null); setError(''); setMessage(''); setConfirmed(false); }
  return <>
    <header className="header"><Link className="brand" href="/">Saham Signal</Link><span className="mode">Research / Simulasi</span></header>
    <main className="workspace preferences-workspace"><Link href="/">← Kembali ke kandidat</Link><h1>Catatan posisi manual.</h1>
      <section className="notice"><div><h2>Konfirmasi fill aktual Anda</h2><p>Sentuhan harga chart dan status READY tidak mencatat pembelian. Permintaan exit tidak menjual saham. Catatan manual terpisah dari hasil simulasi; lingkungan ini tetap research, tanpa koneksi broker atau harga live.</p><p>1 lot = 100 saham. Masukkan rata-rata harga eksekusi, biaya total aktual dan waktu WIB. Risiko/target adalah perkiraan atas lot tersisa dengan asumsi biaya jual, tanpa jaminan fill.</p></div></section>
      {loading && <p role="status">Memuat posisi…</p>}
      {error && <p className="field-error" role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      <button disabled={busy} onClick={() => { setError(''); setRefresh(v => v + 1); }}>Muat ulang posisi</button>
      <section className="panel"><h2>Posisi akun ini</h2>
        {!loading && items.length === 0 && <p>Belum ada fill yang dicatat.</p>}
        <div className="settings-fields">{items.map(p => <button key={p.position_id} disabled={busy} onClick={() => choose(p.position_id)}>{p.symbol} · {p.remaining_lots} lot · {p.status}{p.overnight_risk ? ' · Risiko overnight' : ''}</button>)}</div>
        <button disabled={busy} onClick={() => choose('')}>Catat posisi baru</button>
      </section>
      {detail && detail.position.position_id === selected && <section className="panel"><h2>{detail.position.symbol} · {detail.position.status}</h2>
        <p>Sisa {detail.position.remaining_lots} lot · Rata-rata beli {money(detail.position.average_price_idr)} · Biaya aktual total {money(detail.position.fees_idr)}</p>
        <p>Modal beli aktual {money(detail.invested_idr)} · Basis biaya tersisa {money(detail.remaining_cost_idr)} · Hasil terealisasi {money(detail.realized_pnl_idr)}</p>
        {detail.plan && <p>Stop {money(detail.plan.stop_idr)} · Target {money(detail.plan.target_idr)} · Tenggat {wib(detail.plan.exit_deadline)} WIB · Versi {detail.position.plan_version}<br />Perkiraan risiko stop {money(detail.stop_loss_idr ?? '0.00')} · Potensi target bersih {money(detail.target_net_idr ?? '0.00')}</p>}
        {detail.position.overnight_risk && <p role="alert">Risiko overnight: lot belum terjual. Peringatan konservatif mulai 15.30 WIB atau setelah hari pembelian; bukan kalender bursa tervalidasi.</p>}
        {detail.exit_reason && <p role="alert">Exit diminta ({detail.exit_reason}). Catat fill jual aktual untuk mengurangi lot.</p>}
        <h3>Riwayat fill</h3><ul>{detail.position.fills.map(f => <li key={f.fill_id}>{f.side} {f.lots} lot × {money(f.price_idr)}, biaya {money(f.fees_idr)} · {wib(f.filled_at)} WIB · manual</li>)}</ul>
        {detail.position.status !== 'CLOSED' && <div className="settings-fields">{(['MANUAL', 'STOP', 'TARGET', 'DEADLINE'] as const).map(reason => <button key={reason} disabled={busy} onClick={() => void mutate(`/${selected}/exit-request`, 'POST', { reason })}>Minta exit: {reason}</button>)}</div>}
      </section>}
      <section className="panel"><h2>{selected ? 'Tambah fill pada posisi terpilih' : 'Catat fill beli pertama'}</h2>
        <form onSubmit={record}><fieldset className="settings-fields" disabled={busy || loading || Boolean(selected && (!detail || detail.position.status === 'CLOSED'))}>
          {!selected && <label>Kode saham<input required value={form.symbol} maxLength={12} onChange={e => setForm({ ...form, symbol: e.target.value })} /></label>}
          {selected && <label>Sisi fill<select value={form.side} onChange={e => setForm({ ...form, side: e.target.value })}><option value="BUY">BUY</option><option value="SELL">SELL</option></select></label>}
          <label>Harga rata-rata fill (Rp)<input required inputMode="decimal" value={form.price} onChange={e => setForm({ ...form, price: e.target.value })} /></label>
          <label>Lot aktual<input required type="number" min="1" max="2147483647" step="1" value={form.lots} onChange={e => setForm({ ...form, lots: e.target.value })} /></label>
          <label>Biaya total aktual (Rp)<input required inputMode="decimal" value={form.fees} onChange={e => setForm({ ...form, fees: e.target.value })} /></label>
          <label>Waktu fill (WIB)<input required type="datetime-local" value={form.time} onChange={e => setForm({ ...form, time: e.target.value })} /></label>
          <label><input required type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />Saya mengonfirmasi fill ini sudah terjadi.</label><button type="submit">{busy ? 'Menyimpan…' : 'Simpan fill terkonfirmasi'}</button>
        </fieldset></form>
      </section>
      {selected && <section className="panel"><h2>Rencana atas lot tersisa</h2><p>Masukkan level rencana Anda. Perhitungan memakai fill aktual dan basis biaya tersisa. Stop/target belum dipantau dengan feed live.</p>
        <form onSubmit={savePlan}><fieldset className="settings-fields" disabled={busy || !detail || detail.position.status === 'CLOSED'}>
          <label>Stop (Rp)<input required value={plan.stop} onChange={e => setPlan({ ...plan, stop: e.target.value })} /></label>
          <label>Target (Rp)<input required value={plan.target} onChange={e => setPlan({ ...plan, target: e.target.value })} /></label>
          <label>Tenggat exit (WIB)<input required type="datetime-local" value={plan.deadline} onChange={e => setPlan({ ...plan, deadline: e.target.value })} /></label>
          <label>Asumsi biaya jual (rasio enam desimal)<input required value={plan.fee} onChange={e => setPlan({ ...plan, fee: e.target.value })} /></label>
          <button type="submit">Simpan rencana posisi</button>
        </fieldset></form></section>}
    </main>
  </>;
}

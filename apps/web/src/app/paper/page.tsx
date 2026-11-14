'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { publicConfig } from '@/lib/config';

type Summary = { at: string; fills: number; openShares: number };

function summary(value: unknown): Summary | null {
  const data = value as { mode?: string; origin?: string; paper_live_enabled?: boolean; receipt?: {
    mode?: string; origin?: string; as_of?: string; actual_fills?: unknown[];
    paper_fills?: unknown[]; paper_positions?: Record<string, number>;
    readiness?: { paper_live_enabled?: boolean };
  } | null };
  if (!data || data.mode !== 'paper' || data.origin !== 'simulation' || data.paper_live_enabled !== false) throw new Error('Laporan paper tidak valid.');
  const report = data.receipt;
  if (report === null) return null;
  if (!report || report.mode !== 'paper' || report.origin !== 'simulation' || report.readiness?.paper_live_enabled !== false ||
      !Array.isArray(report.actual_fills) || report.actual_fills.length !== 0 || !Array.isArray(report.paper_fills) ||
      !report.paper_positions || typeof report.paper_positions !== 'object' || Array.isArray(report.paper_positions) ||
      typeof report.as_of !== 'string' || !Number.isFinite(Date.parse(report.as_of)) ||
      Object.values(report.paper_positions).some(n => !Number.isSafeInteger(n) || n < 0)) throw new Error('Laporan paper tidak valid.');
  const openShares = Object.values(report.paper_positions).reduce((a, b) => a + b, 0);
  if (!Number.isSafeInteger(openShares)) throw new Error('Laporan paper tidak valid.');
  return { at: report.as_of, fills: report.paper_fills.length, openShares };
}

export default function PaperPage() {
  const [report, setReport] = useState<Summary | null>(null);
  const [status, setStatus] = useState('Memuat laporan paper…');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    let disposed = false;
    fetch(new URL('../ops/paper', `${publicConfig.apiBaseUrl}/`), { credentials: 'include', cache: 'no-store', signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error(response.status === 401 || response.status === 403 ? 'Sesi admin paper diperlukan.' : 'Layanan paper belum tersedia.');
        return summary(await response.json());
      })
      .then(next => { if (!disposed) { setReport(next); setStatus(next ? 'Laporan simulasi tersedia.' : 'Belum ada laporan paper tersimpan.'); } })
      .catch(error => { if (!disposed) { setReport(null); setStatus(error instanceof Error && error.name !== 'AbortError' ? error.message : 'Layanan paper belum tersedia.'); } })
      .finally(() => clearTimeout(timeout));
    return () => { disposed = true; controller.abort(); clearTimeout(timeout); };
  }, [retry]);
  return <main className="alerts-page">
    <Link href="/">← Dashboard research</Link>
    <h1>Laporan paper</h1>
    <p className="muted">Paper · Simulasi offline</p>
    <section className="notice" aria-label="Status observasi">
      <div><h2>Paper live belum dimulai</h2><p>G0 menunggu bukti data berizin. G1 belum lulus. Toleransi kalibrasi, fill, dan drawdown menunggu validasi. Simulasi ini tidak dihitung sebagai observasi G2.</p></div>
    </section>
    <p role="status">{status}</p>
    <button onClick={() => { setReport(null); setStatus('Memuat laporan paper…'); setRetry(n => n + 1); }}>Muat ulang laporan</button>
    {report && <section className="panel detail-section" aria-label="Hasil simulasi paper">
      <h2>Hasil simulasi paper</h2>
      <dl className="plan-grid"><div><dt>Fill simulasi</dt><dd>{report.fills}</dd></div><div><dt>Saham simulasi tersisa</dt><dd>{report.openShares}</dd></div></dl>
      <p>Waktu laporan: <time dateTime={report.at}>{new Date(report.at).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' })} WIB</time></p>
    </section>}
    <section className="detail-section" aria-label="Fill aktual"><h2>Fill aktual</h2><p>Fill yang dicatat manual disimpan dan dilaporkan terpisah pada akun asalnya. Jumlah fill aktual tidak disimpulkan dari laporan simulasi.</p></section>
  </main>;
}

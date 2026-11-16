'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { publicConfig } from '@/lib/config';

type Overview = {
  paper: { at: string; fills: number; openShares: number } | null;
  actual: { fill_count: number; buy_lots: number; sell_lots: number; remaining_lots: number; realized_pnl_idr: string };
  acceptance: { acceptance_passed: boolean; can_advance: boolean; reasons: string[];
    gates: Record<'G0' | 'G1', { decision: 'passed' | 'pending' | 'no-go' }>;
    scenarios: { scenario: number; title: string; status: 'passed' | 'blocked' | 'missing'; evidence: { source: string; test: string; status: string }[] }[] };
};
const blockers: Record<string, string> = {
  CRITICAL_ACCEPTANCE_INCOMPLETE: 'Ada skenario kritis yang belum lulus atau belum memiliki bukti.',
  ACCEPTANCE_RELEASE_MISMATCH: 'Bukti acceptance belum terikat pada versi rilis ini.',
  LICENSED_E2E_EVIDENCE_MISSING: 'Bukti integrasi penuh dengan feed berizin belum tersedia.',
  G0_NOT_PASSED: 'G0 belum memiliki keputusan lulus yang berlaku.',
  G1_NOT_PASSED: 'G1 belum memiliki keputusan lulus yang berlaku.',
  VALIDATION_TOLERANCES_MISSING: 'Toleransi kalibrasi, fill, dan drawdown menunggu validasi.',
  PROTOCOL_VALIDATION_MISMATCH: 'Protokol observasi tidak sesuai review validasi G1.',
  OBSERVATION_START_REQUIRES_REVIEW: 'Waktu mulai observasi memerlukan review ulang.',
  OPERATIONS_BLOCKED: 'Kontrol operasi sedang menahan kemajuan.',
  MODEL_DATA_EVIDENCE_MISMATCH: 'Bukti acceptance dan keputusan model/data belum merujuk artefak yang sama.',
  GATE_EXPIRES_BEFORE_START: 'Keputusan gerbang kedaluwarsa sebelum jadwal mulai observasi.',
  E2E_REVIEW_MISMATCH: 'Review integrasi penuh belum cocok dengan keputusan gerbang terbaru.',
};
function invalid(): never { throw new Error('Laporan paper tidak valid.'); }
function parse(value: unknown): Overview {
  const data = value as { mode?: string; origin?: string; paper_live_enabled?: boolean;
    receipt?: { mode?: string; origin?: string; as_of?: string; actual_fills?: unknown[];
      paper_fills?: unknown[]; paper_positions?: Record<string, number>; readiness?: { paper_live_enabled?: boolean } } | null;
    acceptance?: Overview['acceptance'];
    fill_reports?: { combined_pnl?: unknown; actual?: Overview['actual'] & { origin?: string; source?: string; source_mode?: string; available?: boolean } } };
  if (!data || data.mode !== 'paper' || data.origin !== 'simulation' || data.paper_live_enabled !== false) invalid();
  const assessment = data.acceptance;
  if (!assessment || typeof assessment.acceptance_passed !== 'boolean' || typeof assessment.can_advance !== 'boolean' ||
      !Array.isArray(assessment.reasons) || assessment.reasons.some(r => typeof r !== 'string') ||
      !assessment.gates || ['G0', 'G1'].some(g => !['passed', 'pending', 'no-go'].includes(assessment.gates[g as 'G0' | 'G1']?.decision)) ||
      !Array.isArray(assessment.scenarios) || assessment.scenarios.length !== 12 ||
      new Set(assessment.scenarios.map(s => s.scenario)).size !== 12 ||
      assessment.scenarios.some(s => !Number.isInteger(s.scenario) || s.scenario < 1 || s.scenario > 12 || typeof s.title !== 'string' ||
        !['passed', 'blocked', 'missing'].includes(s.status) || !Array.isArray(s.evidence) ||
        (s.status === 'passed' && (s.evidence.length === 0 || s.evidence.some(e => e.status !== 'passed'))) ||
        s.evidence.some(e => typeof e.test !== 'string' || typeof e.source !== 'string'))) invalid();
  if ((assessment.acceptance_passed && assessment.scenarios.some(s => s.status !== 'passed')) ||
      (assessment.can_advance && (!assessment.acceptance_passed || assessment.reasons.length > 0 ||
        Object.values(assessment.gates).some(g => g.decision !== 'passed')))) invalid();
  const actual = data.fill_reports?.actual;
  if (!actual || actual.origin !== 'manual' || actual.source !== 'manual_position_events' || actual.source_mode !== 'paper' ||
      actual.available !== true || data.fill_reports?.combined_pnl !== null ||
      [actual.fill_count, actual.buy_lots, actual.sell_lots, actual.remaining_lots].some(n => !Number.isSafeInteger(n) || n < 0) ||
      typeof actual.realized_pnl_idr !== 'string' || !/^-?\d+\.\d{2}$/.test(actual.realized_pnl_idr)) invalid();
  const report = data.receipt;
  let paper: Overview['paper'] = null;
  if (report !== null) {
    if (!report || report.mode !== 'paper' || report.origin !== 'simulation' || report.readiness?.paper_live_enabled !== false ||
        !Array.isArray(report.actual_fills) || report.actual_fills.length !== 0 || !Array.isArray(report.paper_fills) ||
        !report.paper_positions || typeof report.paper_positions !== 'object' || Array.isArray(report.paper_positions) ||
        typeof report.as_of !== 'string' || !Number.isFinite(Date.parse(report.as_of)) ||
        Object.values(report.paper_positions).some(n => !Number.isSafeInteger(n) || n < 0)) invalid();
    const openShares = Object.values(report.paper_positions).reduce((a, b) => a + b, 0);
    if (!Number.isSafeInteger(openShares)) invalid();
    paper = { at: report.as_of, fills: report.paper_fills.length, openShares };
  }
  return { paper, actual, acceptance: assessment };
}

export default function PaperPage() {
  const [report, setReport] = useState<Overview | null>(null);
  const [status, setStatus] = useState('Memuat laporan paper…');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    let disposed = false;
    const apiBase = new URL(`${publicConfig.apiBaseUrl}/`, window.location.origin);
    fetch(new URL('../ops/paper', apiBase), { credentials: 'include', cache: 'no-store', signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error(response.status === 401 || response.status === 403 ? 'Sesi admin paper diperlukan.' : 'Layanan paper belum tersedia.');
        return parse(await response.json());
      })
      .then(next => { if (!disposed) { setReport(next); setStatus(next.paper ? 'Laporan simulasi tersedia.' : 'Belum ada laporan paper tersimpan.'); } })
      .catch(error => { if (!disposed) { setReport(null); setStatus(error instanceof Error && error.name !== 'AbortError' ? error.message : 'Layanan paper belum tersedia.'); } })
      .finally(() => clearTimeout(timeout));
    return () => { disposed = true; controller.abort(); clearTimeout(timeout); };
  }, [retry]);
  return <main className="alerts-page paper-review">
    <Link href="/">← Dashboard research</Link><h1>Laporan paper</h1>
    <p className="muted">Paper · Simulasi offline</p>
    <section className="notice" aria-label="Status observasi"><div><h2>Paper live belum dimulai</h2>
      <p>Keputusan gerbang dan bukti acceptance ditampilkan di bawah. Hasil simulasi tidak dihitung sebagai observasi G2.</p></div></section>
    <p role="status">{status}</p>
    <button onClick={() => { setReport(null); setStatus('Memuat laporan paper…'); setRetry(n => n + 1); }}>Muat ulang laporan</button>
    {report && <>
      <section className="panel detail-section" aria-label="Gerbang dan kemajuan"><h2>Gerbang dan kemajuan</h2>
        <dl className="plan-grid">{(['G0', 'G1'] as const).map(g => <div key={g}><dt>{g}</dt><dd>{({ passed: 'Lulus', pending: 'Menunggu keputusan yang berlaku', 'no-go': 'Tidak lulus' })[report.acceptance.gates[g].decision]}</dd></div>)}</dl>
        <p>{report.acceptance.can_advance ? 'Prasyarat bukti lengkap; aktivasi tetap memerlukan jalur paper yang disetujui.' : 'Kemajuan ditahan.'}</p>
        <ul>{report.acceptance.reasons.map(reason => <li key={reason}>{blockers[reason] ?? 'Review tambahan diperlukan.'}</li>)}</ul>
      </section>
      <section className="panel detail-section" aria-label="Acceptance PRD 14"><h2>Acceptance PRD 14</h2>
        <p>{report.acceptance.scenarios.filter(s => s.status === 'passed').length}/12 skenario lulus. Bukti komponen/browser tidak meluluskan gerbang data dan model.</p>
        <ol>{report.acceptance.scenarios.map(s => <li key={s.scenario}><strong>{s.title}</strong> · {({ passed: 'Lulus', blocked: 'Gagal/ditahan', missing: 'Bukti belum tersedia' })[s.status]}
          {s.evidence.length > 0 && <details><summary>Bukti pengujian</summary><ul>{s.evidence.map((e, i) => <li key={i}>{e.source}: {e.test} · {e.status === 'passed' ? 'Lulus' : 'Ditahan'}</li>)}</ul></details>}</li>)}</ol>
      </section>
      {report.paper && <section className="panel detail-section" aria-label="Hasil simulasi paper"><h2>Hasil simulasi paper</h2>
        <dl className="plan-grid"><div><dt>Fill simulasi</dt><dd>{report.paper.fills}</dd></div><div><dt>Saham simulasi tersisa</dt><dd>{report.paper.openShares}</dd></div></dl>
        <p>Waktu laporan: <time dateTime={report.paper.at}>{new Date(report.paper.at).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' })} WIB</time></p></section>}
      <section className="panel detail-section" aria-label="Fill aktual"><h2>Fill aktual tercatat</h2>
        <p>Catatan manual akun ini pada mode paper, dilaporkan terpisah dari simulasi. Belum diverifikasi broker.</p>
        <dl className="plan-grid"><div><dt>Fill aktual</dt><dd>{report.actual.fill_count}</dd></div><div><dt>Lot beli / jual</dt><dd>{report.actual.buy_lots} / {report.actual.sell_lots}</dd></div><div><dt>Lot tersisa</dt><dd>{report.actual.remaining_lots}</dd></div><div><dt>PnL terealisasi tercatat (IDR)</dt><dd>{report.actual.realized_pnl_idr}</dd></div></dl>
        <p>PnL aktual dan simulasi tidak dijumlahkan.</p></section>
    </>}
  </main>;
}

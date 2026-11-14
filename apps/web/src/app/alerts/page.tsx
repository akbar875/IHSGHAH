'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { alertLabels, fetchAlerts, priority } from '@/lib/alerts';
import type { Alert } from '@/lib/generated/candidates';

const exits = new Set<Alert['type']>(['TP', 'STOP', 'TIME_EXIT']);
export default function AlertsPage() {
  const [items, setItems] = useState<Alert[]>([]);
  const [status, setStatus] = useState('Memuat notifikasi…');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let disposed = false;
    let active: AbortController | undefined;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      clearTimeout(timer);
      active?.abort();
      if (!navigator.onLine) {
        setStatus('Offline. Alert tidak dijamin diterima tepat waktu. Daftar terakhir mungkin tertinggal.');
        return;
      }
      const controller = new AbortController();
      active = controller;
      const timeout = setTimeout(() => controller.abort(), 10000);
      try {
        const next = await fetchAlerts(controller.signal);
        if (!disposed && active === controller) {
          setItems(next);
          setStatus(next.length ? 'Daftar diperbarui. Tersimpan di inbox; penerimaan perangkat belum dikonfirmasi.' : 'Belum ada notifikasi.');
        }
      } catch (error) {
        if (!disposed && active === controller) setStatus(error instanceof Error ? `${error.message} Daftar terakhir mungkin tertinggal.` : 'Notifikasi tidak tersedia.');
      } finally {
        clearTimeout(timeout);
        if (!disposed && active === controller) timer = setTimeout(load, 5000);
      }
    }
    function offline() {
      active?.abort(); active = undefined; clearTimeout(timer);
      setStatus('Offline. Alert tidak dijamin diterima tepat waktu. Daftar terakhir mungkin tertinggal.');
    }
    void load();
    window.addEventListener('online', load);
    window.addEventListener('offline', offline);
    return () => {
      disposed = true; active?.abort(); clearTimeout(timer);
      window.removeEventListener('online', load); window.removeEventListener('offline', offline);
    };
  }, [retry]);
  return <main className="alerts-page">
    <Link href="/">← Dashboard</Link>
    <h1>Notifikasi</h1>
    <p className="muted">Research · Simulasi · Tidak ada alert live</p>
    <p>Alert tidak menjamin diterima tepat waktu saat perangkat offline atau halaman ditutup. Inbox dimuat ulang setiap 5 detik saat halaman ini terbuka. Push browser belum tersedia.</p>
    <p role="status">{status}</p>
    <button onClick={() => setRetry(value => value + 1)}>Muat ulang notifikasi</button>
    <ol className="alerts-list" aria-label="Daftar notifikasi">
      {items.map(item => <li key={item.dedup_key} className="candidate">
        <span className="tag">Simulasi · {priority[item.type] === 0 ? 'Prioritas risiko/data' : 'Informasi rencana'}</span>
        <h2>{alertLabels[item.type]}</h2>
        <p>{item.position_id ? `Posisi ${item.position_id}` : `Sinyal ${item.signal_id}`}</p>
        <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' })} WIB</time>
        {exits.has(item.type) && <p className="entry-warning">Saat alert dibuat, fill jual untuk permintaan exit ini belum dikonfirmasi. Alert tidak mengurangi lot atau menutup posisi. Periksa catatan fill jual aktual.</p>}
        {item.type === 'DATA_DISCONNECTED' && <p>Data tidak sehat atau belum tersedia. Entry ditahan; pantau posisi dan jangan menganggap exit sudah tereksekusi.</p>}
        {item.type === 'ENTRY_READY' && <p>Pemicu entry aktif. Posisi hanya terbuka setelah fill beli dikonfirmasi.</p>}
        {item.type === 'INVALIDATED' && <p>Rencana batal atau kedaluwarsa. Jangan gunakan rencana ini untuk entry baru.</p>}
        <p className="muted">{item.status === 'pending' ? 'Tersimpan · penerimaan perangkat belum dikonfirmasi' : item.status === 'failed' ? 'Pengiriman gagal' : 'Diterima kanal in-app'}</p>
        {item.position_id && <Link href="/positions">Periksa posisi dan fill</Link>}
      </li>)}
    </ol>
  </main>;
}

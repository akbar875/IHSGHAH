'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';
import { publicConfig } from '@/lib/config';

export default function ResearchAccess() {
  const router = useRouter();
  const [token, setToken] = useState('');
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState('');
  async function activate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setMessage('Mengaktifkan sesi…');
    try {
      const base = new URL(`${publicConfig.apiBaseUrl}/`, window.location.origin);
      const response = await fetch(new URL('../research/session', base), {
        method: 'POST', credentials: 'include', cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token.trim() }), signal: AbortSignal.timeout(10000),
      });
      setToken('');
      if (!response.ok) throw new Error(response.status === 401 ? 'Kode akses tidak valid atau sudah kedaluwarsa. Minta kode baru dari pengelola.' : response.status === 403 ? 'Aktivasi tidak diizinkan. Minta pengelola memeriksa akses research untuk alamat situs ini.' : 'Sesi belum dapat diaktifkan. Coba lagi sebentar.');
      router.push('/');
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error && error.name !== 'TimeoutError' && error.name !== 'TypeError' ? error.message : 'Tidak dapat terhubung. Periksa koneksi, lalu coba lagi.');
    } finally { setPending(false); }
  }
  return <main className="signal-page access-page">
    <Link href="/">← Kembali ke daftar saham</Link>
    <p className="eyebrow">AKSES RESEARCH</p><h1>Aktifkan sesi research</h1>
    <p className="intro">Masukkan kode akses dari pengelola untuk melihat data saham, chart, dan analisis harian.</p>
    <form className="access-form" onSubmit={activate}>
      <label htmlFor="research-token">Kode akses research</label>
      <input id="research-token" type="password" autoComplete="off" value={token} onChange={event => setToken(event.target.value)} required maxLength={256} disabled={pending} aria-describedby="access-help" />
      <p id="access-help">Belum punya kode? Minta pengelola aplikasi menerbitkan kode sesi research. Kode memiliki masa berlaku.</p>
      <button disabled={pending || !token.trim()}>{pending ? 'Mengaktifkan…' : 'Aktifkan & lihat saham'}</button>
      <p role="status">{message}</p>
    </form>
    <p className="muted">Setelah sesi aktif, aplikasi akan memuat ulang daftar saham. Jika data belum tersedia, pengelola perlu memperbarui sumber data harian.</p>
  </main>;
}

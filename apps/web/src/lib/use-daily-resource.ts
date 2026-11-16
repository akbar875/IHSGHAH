'use client';

import { useEffect, useState } from 'react';
import { publicConfig } from './config';

export function useDailyResource<T>(path: string, parse: (value: unknown) => T, revision: number) {
  const key = `${path}:${revision}`;
  const [result, setResult] = useState<{ key: string; data: T | null; error: string | null; checked: string | null }>({ key: '', data: null, error: null, checked: null });
  useEffect(() => {
    let disposed = false;
    let pending = false;
    let controller: AbortController | null = null;
    async function load() {
      if (pending || document.hidden) return;
      pending = true;
      controller = new AbortController();
      const timeout = setTimeout(() => controller?.abort(), 10000);
      try {
        const base = new URL(`${publicConfig.apiBaseUrl}/`, window.location.origin);
        const response = await fetch(new URL(`../research/${path}`, base), { credentials: 'include', cache: 'no-store', signal: controller.signal });
        if (!response.ok) throw new Error([401, 403].includes(response.status) ? 'Masuk dengan sesi research untuk melihat analisis.' : response.status === 404 ? 'Saham tidak ditemukan.' : 'Data belum tersedia. Impor data harian pada backend, lalu coba lagi.');
        const data = parse(await response.json());
        if (!disposed) setResult({ key, data, error: null, checked: new Date().toISOString() });
      } catch (error) {
        if (!disposed) setResult({ key, data: null, error: error instanceof Error && error.name !== 'AbortError' ? error.message : 'Data gagal dimuat. Coba lagi.', checked: null });
      } finally { pending = false; clearTimeout(timeout); }
    }
    void load();
    const timer = setInterval(() => void load(), 15000);
    const onVisible = () => { if (!document.hidden) void load(); };
    document.addEventListener('visibilitychange', onVisible);
    return () => { disposed = true; clearInterval(timer); controller?.abort(); document.removeEventListener('visibilitychange', onVisible); };
  }, [path, parse, key]);
  return result.key === key ? { ...result, loading: false } : { data: null, error: null, checked: null, loading: true };
}

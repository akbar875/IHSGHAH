'use client';

import { useEffect, useState } from 'react';
import { publicConfig } from './config';

class ResourceError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

export function useDailyResource<T>(path: string, parse: (value: unknown) => T, revision: number) {
  const key = `${path}:${revision}`;
  const [result, setResult] = useState<{ key: string; data: T | null; error: string | null; errorStatus: number | null; checked: string | null }>({ key: '', data: null, error: null, errorStatus: null, checked: null });
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
        if (!response.ok) throw new ResourceError(response.status === 401 ? 'Sesi research belum aktif atau sudah berakhir.' : response.status === 403 ? 'Akses research tidak diizinkan.' : response.status === 404 ? 'Saham tidak ditemukan.' : response.status === 429 ? 'Terlalu banyak permintaan. Tunggu sebentar, lalu coba lagi.' : 'Data belum tersedia. Sumber data perlu diperiksa oleh pengelola.', response.status);
        const data = parse(await response.json());
        if (!disposed) setResult({ key, data, error: null, errorStatus: null, checked: new Date().toISOString() });
      } catch (error) {
        if (!disposed) setResult({ key, data: null, error: error instanceof Error && error.name !== 'AbortError' ? error.message : 'Data gagal dimuat. Coba lagi.', errorStatus: error instanceof ResourceError ? error.status : null, checked: null });
      } finally { pending = false; clearTimeout(timeout); }
    }
    void load();
    const timer = setInterval(() => void load(), 15000);
    const onVisible = () => { if (!document.hidden) void load(); };
    document.addEventListener('visibilitychange', onVisible);
    return () => { disposed = true; clearInterval(timer); controller?.abort(); document.removeEventListener('visibilitychange', onVisible); };
  }, [path, parse, key]);
  return result.key === key ? { ...result, loading: false } : { data: null, error: null, errorStatus: null, checked: null, loading: true };
}

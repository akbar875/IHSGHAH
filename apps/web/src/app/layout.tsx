import type { Metadata, Viewport } from 'next';
import type { ReactNode } from 'react';
import Link from 'next/link';
import './globals.css';

export const metadata: Metadata = {
  title: 'Saham Signal — Daftar saham & chart harian',
  description: 'Jelajahi saham BEI, pilih saham untuk melihat chart harga, volume, dan analisis harian.',
  robots: { index: false, follow: false },
};

export const viewport: Viewport = { width: 'device-width', initialScale: 1 };

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="id"><body><nav className="alerts-nav" aria-label="Navigasi"><Link className="nav-brand" href="/">↗ Saham Signal</Link><div><Link href="/">Daftar saham</Link><Link href="/screener">Sinyal teknikal</Link><Link href="/research">Data harian</Link></div></nav>{children}</body></html>;
}

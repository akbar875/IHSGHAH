import type { Metadata, Viewport } from 'next';
import type { ReactNode } from 'react';
import Link from 'next/link';
import './globals.css';

export const metadata: Metadata = {
  title: 'Saham Signal — Bullish & Bearish',
  description: 'Screener teknikal saham BEI dengan potensi pergerakan, target take profit, dan stop loss.',
  robots: { index: false, follow: false },
};

export const viewport: Viewport = { width: 'device-width', initialScale: 1 };

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="id"><body><nav className="alerts-nav" aria-label="Navigasi"><Link className="nav-brand" href="/">↗ Saham Signal</Link><div><Link href="/research">Data harian</Link><Link href="/access">Akses research</Link></div></nav>{children}</body></html>;
}

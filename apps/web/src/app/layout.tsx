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
  return <html lang="id"><body><nav className="alerts-nav" aria-label="Navigasi"><Link href="/">Saham Signal</Link><Link href="/research">Data harian</Link></nav>{children}</body></html>;
}

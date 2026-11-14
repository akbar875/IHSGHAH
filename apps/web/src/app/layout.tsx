import type { Metadata, Viewport } from 'next';
import type { ReactNode } from 'react';
import Link from 'next/link';
import './globals.css';

export const metadata: Metadata = {
  title: 'Saham Signal — Research',
  description: 'Lingkungan research Saham Signal. Shell simulasi tanpa data pasar atau sinyal live.',
  robots: { index: false, follow: false },
};

export const viewport: Viewport = { width: 'device-width', initialScale: 1 };

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="id"><body><nav className="alerts-nav" aria-label="Notifikasi"><Link href="/alerts">Notifikasi</Link></nav>{children}</body></html>;
}

'use client';

import { useState } from 'react';
import { useDailyResource } from '@/lib/use-daily-resource';
import { parseDailyMarket } from '@/lib/daily-market';
import DailyStockDetail from './stocks/[symbol]/daily-stock-detail';

const price = (value: string) => new Intl.NumberFormat('id-ID', { maximumFractionDigits: 2 }).format(Number(value));
const dateLabel = (value: string) => new Date(`${value}T00:00:00+07:00`).toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Jakarta' });
const names: Record<string, string> = { BBCA: 'Bank Central Asia', BBRI: 'Bank Rakyat Indonesia', BMRI: 'Bank Mandiri', BBNI: 'Bank Negara Indonesia', TLKM: 'Telkom Indonesia', ASII: 'Astra International', GOTO: 'GoTo Gojek Tokopedia', UNVR: 'Unilever Indonesia', ICBP: 'Indofood CBP', INDF: 'Indofood Sukses Makmur' };
const favorites = ['BBCA', 'BBRI', 'BMRI', 'BBNI', 'TLKM', 'ASII'];

export default function StockWorkspace() {
  const [revision, setRevision] = useState(0);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<string | null>(null);
  const [mobileDetail, setMobileDetail] = useState(false);
  const resource = useDailyResource('eod', parseDailyMarket, revision);
  const rows = resource.data?.rows ?? [];
  const symbol = selected && rows.some(row => row.symbol === selected) ? selected : rows.find(row => row.symbol === 'BBCA')?.symbol ?? rows[0]?.symbol;
  const visible = rows.filter(row => `${row.symbol} ${names[row.symbol] ?? ''}`.toLowerCase().includes(query.trim().toLowerCase())).sort((a, b) => {
    const rank = (ticker: string) => favorites.includes(ticker) ? favorites.indexOf(ticker) : favorites.length;
    return rank(a.symbol) - rank(b.symbol) || a.symbol.localeCompare(b.symbol);
  });
  return <main className={`market-terminal ${mobileDetail ? 'show-detail' : ''}`}>
    <aside className="market-sidebar" aria-label="Daftar saham BEI">
      <header><p className="eyebrow">BURSA EFEK INDONESIA</p><h1>Daftar saham <span>{rows.length || '—'}</span></h1><p>Pilih saham untuk membuka chart & analisis.</p></header>
      <label className="market-search">Cari saham<input placeholder="Cari kode atau nama saham" value={query} onChange={event => setQuery(event.target.value)} /></label>
      <div className="market-list-heading"><span>Saham</span><span>Penutupan / perubahan</span></div>
      <div className="market-list" role="list" aria-label="Saham tersedia">
        {resource.loading && <p className="market-list-message" role="status">Memuat daftar saham…</p>}
        {resource.error && <div className="market-list-message"><p role="status">Daftar saham gagal dimuat. {resource.error}</p><button onClick={() => setRevision(n => n + 1)}>Coba lagi</button></div>}
        {!resource.loading && !resource.error && !visible.length && <div className="market-list-message"><p>Tidak ada saham yang cocok.</p><button onClick={() => setQuery('')}>Reset pencarian</button></div>}
        {visible.map(row => <div role="listitem" key={row.symbol}><button className={`market-stock ${symbol === row.symbol ? 'selected' : ''}`} aria-pressed={symbol === row.symbol} aria-label={`Lihat saham ${row.symbol}`} onClick={() => { setSelected(row.symbol); setMobileDetail(true); }}>
          <span className="market-avatar" aria-hidden="true">{row.symbol.slice(0, 2)}</span><span className="market-stock-name"><strong>{row.symbol}</strong><small>{names[row.symbol] ?? 'Saham BEI'}{row.stale ? ' · data tertinggal' : ''}</small></span>
          <span className="market-stock-price"><strong>{price(row.close_idr)}</strong><small className={row.return_1d === null ? '' : Number(row.return_1d) >= 0 ? 'market-up' : 'market-down'}>{row.return_1d === null ? 'Perubahan belum tersedia' : `${Number(row.return_1d) > 0 ? '+' : ''}${(Number(row.return_1d) * 100).toFixed(2)}%`}</small></span>
        </button></div>)}
      </div>
      <footer><span className="market-dot" /> Data harian{resource.data && ` · ${dateLabel(resource.data.latest_date)}`}<button disabled={resource.loading} onClick={() => setRevision(n => n + 1)} aria-label="Perbarui daftar saham">↻</button></footer>
    </aside>
    <div className="market-detail" aria-label="Detail saham terpilih">
      <button className="market-back" onClick={() => setMobileDetail(false)}>← Daftar saham</button>
      {symbol && resource.data ? <DailyStockDetail key={symbol} symbol={symbol} embedded /> : <div className="market-welcome"><span aria-hidden="true">↗</span><h2>{resource.loading ? 'Menyiapkan daftar saham' : 'Pilih saham untuk mulai'}</h2><p>Chart harga, volume, dan analisis saham akan tampil di sini.</p></div>}
    </div>
  </main>;
}

'use client';

import { useEffect, useRef, useState } from 'react';
import { createChart, HistogramSeries, LineSeries, type Time } from 'lightweight-charts';
import type { DailyStock, Backtest } from '@/lib/daily-stock';

const money = (n: number) => new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 }).format(n);
const isoDay = (t: Time) => typeof t === 'string' ? t : typeof t === 'number' ? new Date(t * 1000).toISOString().slice(0, 10) : `${t.year}-${String(t.month).padStart(2, '0')}-${String(t.day).padStart(2, '0')}`;
const label = (t: Time) => {
  const day = isoDay(t);
  return new Date(`${day}T00:00:00+07:00`).toLocaleDateString('id-ID', { timeZone: 'Asia/Jakarta', day: 'numeric', month: 'short', year: 'numeric' });
};

export function DailyHistoryChart({ data, range }: { data: DailyStock; range: number }) {
  const container = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<string | null>(null);
  const points = data.history.slice(-range);
  useEffect(() => {
    if (!container.current || !data.history.length) return;
    const points = data.history.slice(-range);
    const chart = createChart(container.current, {
      autoSize: true, height: 350, layout: { textColor: '#18312c', attributionLogo: true },
      timeScale: { timeVisible: false, tickMarkFormatter: (t: Time) => label(t).replace(/\s\d{4}$/, '') },
      localization: { timeFormatter: (t: Time) => `${label(t)} · EOD WIB` },
      handleScroll: { vertTouchDrag: false, horzTouchDrag: true },
    });
    const close = chart.addSeries(LineSeries, { color: '#2864cf', lineWidth: 2, title: 'Penutupan', priceFormat: { type: 'price', precision: 2, minMove: 0.01 } });
    close.priceScale().applyOptions({ scaleMargins: { top: .12, bottom: .28 } });
    close.setData(points.map(p => ({ time: p.date, value: Number(p.close_idr) })));
    const volume = chart.addSeries(HistogramSeries, { priceScaleId: 'volume', priceFormat: { type: 'volume' }, lastValueVisible: false, priceLineVisible: false });
    volume.priceScale().applyOptions({ scaleMargins: { top: .82, bottom: 0 } });
    volume.setData(points.map(p => ({ time: p.date, value: Number(p.volume), color: '#94a3b888' })));
    if (data.plan) for (const [title, value, color] of [
      ['Acuan', data.plan.reference, '#64748b'],
      [data.plan.direction === 'bullish' ? 'Take profit' : 'Target turun', data.plan.take_profit, '#13845c'],
      [data.plan.direction === 'bullish' ? 'Stop loss' : 'Invalidasi', data.plan.stop_loss, '#c84645'],
    ]) close.createPriceLine({ title, price: Number(value), color, lineStyle: 2, axisLabelVisible: true });
    chart.subscribeCrosshairMove(event => {
      const point = event.seriesData.get(close);
      setHover(event.time && point && 'value' in point ? `${label(event.time)} · EOD WIB · Rp ${money(point.value)}` : null);
    });
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [data, range]);
  return <>
    <p className="chart-hover">{hover ?? (points.length ? `${label(points[0].date)} – ${label(points.at(-1)!.date)} · penutupan harian, WIB` : 'Riwayat belum tersedia. Impor ulang snapshot dengan riwayat harga.')}</p>
    {!!points.length && <div ref={container} className="daily-history-chart" role="img" aria-label="Chart harga penutupan harian berwarna biru dan volume abu-abu. Waktu EOD dalam WIB." />}
    <ul className="chart-key"><li><i style={{ background: '#2864cf' }} />Biru: penutupan historis</li><li><i style={{ background: '#94a3b8' }} />Abu-abu: volume penyedia</li><li><i style={{ background: '#13845c' }} />Hijau: target</li><li><i style={{ background: '#c84645' }} />Merah: stop / invalidasi</li></ul>
    <p className="muted">Data sumber hanya menyediakan penutupan harian pada snapshot ini, sehingga candle OHLC dan waktu transaksi intraday belum ditampilkan. Geser atau sentuh chart untuk melihat tanggal dan harga.</p>
  </>;
}

export function BacktestChart({ backtest }: { backtest: Backtest }) {
  const container = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<string | null>(null);
  useEffect(() => {
    if (!container.current || !backtest.trades.length) return;
    const chart = createChart(container.current, {
      autoSize: true, height: 300, layout: { textColor: '#18312c', attributionLogo: true },
      timeScale: { timeVisible: false, tickMarkFormatter: (t: Time) => label(t).replace(/\s\d{4}$/, '') },
      localization: { timeFormatter: (t: Time) => `${label(t)} · EOD WIB` },
      handleScroll: { vertTouchDrag: false, horzTouchDrag: true },
    });
    const equity = chart.addSeries(LineSeries, { color: '#7357aa', lineWidth: 2, title: 'Indeks hasil', priceFormat: { type: 'price', precision: 2, minMove: 0.01 } });
    equity.priceScale().applyOptions({ scaleMargins: { top: .1, bottom: .3 } });
    equity.setData([{ time: backtest.trades[0].signal_date, value: 100 }, ...backtest.trades.map(t => ({ time: t.exit_date, value: t.equity * 100 }))]);
    equity.createPriceLine({ price: 100, color: '#64748b', lineStyle: 2, title: 'Awal 100', axisLabelVisible: true });
    const trades = chart.addSeries(HistogramSeries, { priceScaleId: 'returns', lastValueVisible: false, priceLineVisible: false });
    trades.priceScale().applyOptions({ scaleMargins: { top: .8, bottom: 0 } });
    trades.setData(backtest.trades.map(t => ({ time: t.exit_date, value: t.net_return_pct, color: t.net_return_pct >= 0 ? '#13845c' : '#c84645' })));
    chart.subscribeCrosshairMove(event => {
      const at = event.time ? isoDay(event.time) : null;
      const t = at && backtest.trades.find(t => t.exit_date === at);
      setHover(t ? `${label(t.exit_date)} · EOD WIB · hasil bersih ${t.net_return_pct.toFixed(2)}% · indeks ${(t.equity * 100).toFixed(2)}` : null);
    });
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [backtest]);
  return <>
    <p className="chart-hover">{hover ?? `${backtest.start_date} – ${backtest.end_date} · waktu transaksi berupa tanggal EOD, WIB`}</p>
    <div ref={container} className="backtest-chart" role="img" aria-label="Chart hasil backtest historis: garis ungu indeks hasil, batang hijau transaksi untung, merah transaksi rugi. Tanggal keluar dalam WIB." />
    <ul className="chart-key"><li><i style={{ background: '#7357aa' }} />Ungu: indeks hasil (awal 100)</li><li><i style={{ background: '#13845c' }} />Hijau: hasil transaksi positif</li><li><i style={{ background: '#c84645' }} />Merah: hasil transaksi negatif</li><li><i style={{ background: '#64748b' }} />Abu-abu: indeks awal</li></ul>
  </>;
}


'use client';

import { useEffect, useRef } from 'react';
import { CandlestickSeries, HistogramSeries, LineSeries, LineStyle, createChart, type AutoscaleInfo, type IPrimitivePaneRenderer, type UTCTimestamp } from 'lightweight-charts';
import type { ChartResponse } from '@/lib/stock';
import type { Signal } from '@/lib/generated/candidates';

const stamp = (at: string) => Math.floor(Date.parse(at) / 1000) as UTCTimestamp;
const clock = (value: number) => new Intl.DateTimeFormat('id-ID', { timeZone: 'Asia/Jakarta', hour: '2-digit', minute: '2-digit' }).format(new Date(value * 1000));

export default function PriceChart({ response, signal, projectionAllowed }: { response: ChartResponse; signal: Signal | null; projectionAllowed: boolean }) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current) return;
    const chart = createChart(container.current, {
      autoSize: true, height: 380,
      layout: { textColor: '#18312c', attributionLogo: true },
      timeScale: { timeVisible: true, secondsVisible: false, tickMarkFormatter: (t: number) => clock(t) },
      localization: { timeFormatter: (t: number) => `${clock(t)} WIB` },
      handleScroll: { vertTouchDrag: false, horzTouchDrag: true },
    });
    const levels = signal ? [signal.entry_zone.lower_idr, signal.entry_zone.upper_idr, signal.stop_idr, ...signal.targets_idr].map(Number) : [];
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: '#16614b', downColor: '#b3413a', borderVisible: false, wickUpColor: '#16614b', wickDownColor: '#b3413a',
      autoscaleInfoProvider: (original: () => AutoscaleInfo | null) => {
        const info = original();
        return info?.priceRange && levels.length ? { ...info, priceRange: { minValue: Math.min(info.priceRange.minValue, ...levels), maxValue: Math.max(info.priceRange.maxValue, ...levels) } } : info;
      },
    });
    candles.priceScale().applyOptions({ scaleMargins: { top: .1, bottom: .28 } });
    candles.setData([
      ...response.data.candles.map(c => ({ time: stamp(c.at), open: Number(c.open_idr), high: Number(c.high_idr), low: Number(c.low_idr), close: Number(c.close_idr) })),
      ...(signal && (!response.data.candles.length || stamp(signal.valid_until) > stamp(response.data.candles.at(-1)!.at)) ? [{ time: stamp(signal.valid_until) }] : []),
    ]);
    const volume = chart.addSeries(HistogramSeries, { priceScaleId: 'volume', priceFormat: { type: 'volume' }, lastValueVisible: false, priceLineVisible: false });
    volume.priceScale().applyOptions({ scaleMargins: { top: .8, bottom: 0 } });
    volume.setData(response.data.candles.map(c => ({ time: stamp(c.at), value: c.volume_lots, color: '#8db9a5' })));
    if (signal) {
      for (const [title, price, color] of [
        ['Entry bawah', signal.entry_zone.lower_idr, '#16614b'], ['Entry atas', signal.entry_zone.upper_idr, '#16614b'],
        ['Stop', signal.stop_idr, '#b3413a'], ...signal.targets_idr.map((p, i) => [`TP${i + 1}`, p, '#345cc2']),
      ]) candles.createPriceLine({ price: Number(price), color, title, lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true });
    }
    const projection = projectionAllowed ? response.data.projection : [];
    const groups = [...new Set(projection.map(p => p.coverage))].sort((a, b) => b - a).map(coverage => projection.filter(p => p.coverage === coverage));
    for (const points of groups) {
      for (const field of ['lower_idr', 'median_idr', 'upper_idr'] as const) {
        const line = chart.addSeries(LineSeries, { color: field === 'median_idr' ? '#7357aa' : '#a992cc', lineWidth: field === 'median_idr' ? 2 : 1, lineStyle: LineStyle.Dashed, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: true });
        line.setData(points.map(p => ({ time: stamp(p.at), value: Number(p[field]) })));
      }
    }
    const renderer: IPrimitivePaneRenderer = { draw(target) {
      target.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => {
        const x = (at: string) => chart.timeScale().timeToCoordinate(stamp(at));
        ctx.save();
        if (projection.length) {
          const start = x(projection.reduce((first, p) => Date.parse(p.at) < Date.parse(first) ? p.at : first, projection[0].at));
          if (start !== null) {
            ctx.fillStyle = '#7357aa12';
            ctx.fillRect(start, 0, mediaSize.width - start, mediaSize.height);
          }
          for (const points of groups) {
            const upper = points.map(p => [x(p.at), candles.priceToCoordinate(Number(p.upper_idr))]);
            const lower = [...points].reverse().map(p => [x(p.at), candles.priceToCoordinate(Number(p.lower_idr))]);
            if ([...upper, ...lower].some(p => p[0] === null || p[1] === null)) continue;
            ctx.beginPath();
            [...upper, ...lower].forEach(([px, py], i) => { if (i === 0) ctx.moveTo(px!, py!); else ctx.lineTo(px!, py!); });
            ctx.closePath(); ctx.fillStyle = '#7357aa22'; ctx.fill();
          }
        }
        if (signal) {
          const at = x(signal.valid_until);
          if (at !== null) {
            ctx.strokeStyle = '#9d3029'; ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(at, 0); ctx.lineTo(at, mediaSize.height); ctx.stroke();
            ctx.fillStyle = '#9d3029'; ctx.fillText('Kedaluwarsa', Math.max(4, Math.min(at + 4, mediaSize.width - 78)), 16);
          }
        }
        ctx.restore();
      });
    } };
    candles.attachPrimitive({ paneViews: () => [{ zOrder: () => 'bottom', renderer: () => renderer }] });
    chart.timeScale().fitContent();
    // fitContent omits trailing whitespace; include expiry explicitly in the viewport.
    if (signal) {
      const times = new Set([...response.data.candles.map(c => stamp(c.at)), ...projection.map(p => stamp(p.at)), stamp(signal.valid_until)]);
      chart.timeScale().setVisibleLogicalRange({ from: -1, to: times.size });
    }
    return () => chart.remove();
  }, [response, signal, projectionAllowed]);

  return <div ref={container} className="price-chart" role="img" aria-label="Chart candle dan volume simulasi, waktu WIB. Geser untuk menelusuri, cubit untuk zoom. Proyeksi bergaris putus-putus dengan latar ungu; kedaluwarsa bergaris merah." />;
}

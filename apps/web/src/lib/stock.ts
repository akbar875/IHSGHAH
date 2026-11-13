import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import schema from './generated/candidates.schema.json';
import type { StockDetailResponse, ChartResponse, SignalHistoryResponse, Depth } from './generated/candidates';
import { publicConfig } from './config';
import { MarketError } from './market';

export type { StockDetailResponse, ChartResponse, SignalHistoryResponse, Depth };
export type Interval = ChartResponse['data']['interval'];
const ajv = new Ajv2020({ strict: true, strictTypes: false });
addFormats(ajv);
const validators = {
  StockDetailResponse: ajv.compile<StockDetailResponse>({ $ref: '#/$defs/StockDetailResponse', $defs: schema.$defs }),
  ChartResponse: ajv.compile<ChartResponse>({ $ref: '#/$defs/ChartResponse', $defs: schema.$defs }),
  SignalHistoryResponse: ajv.compile<SignalHistoryResponse>({ $ref: '#/$defs/SignalHistoryResponse', $defs: schema.$defs }),
};
type Responses = { StockDetailResponse: StockDetailResponse; ChartResponse: ChartResponse; SignalHistoryResponse: SignalHistoryResponse };

export function consistentBook(book: Depth, symbol: string): boolean {
  if (book.symbol !== symbol || book.available_levels !== Math.max(book.bids.length, book.asks.length)) return false;
  for (const [rows, direction] of [[book.bids, -1], [book.asks, 1]] as const) {
    let total = 0;
    for (let i = 0; i < rows.length; i++) {
      total += rows[i].lots;
      if (!Number.isSafeInteger(total) || rows[i].cumulative_lots !== total ||
        (i > 0 && direction * (Number(rows[i].price_idr) - Number(rows[i - 1].price_idr)) <= 0)) return false;
    }
  }
  return !book.bids.length || !book.asks.length || Number(book.bids[0].price_idr) < Number(book.asks[0].price_idr);
}

export async function fetchStock<K extends keyof Responses>(kind: K, symbol: string, signal: AbortSignal, interval?: Interval): Promise<Responses[K]> {
  const suffix = kind === 'ChartResponse' ? `/chart?interval=${interval}` : kind === 'SignalHistoryResponse' ? '/signals' : '';
  const response = await fetch(`${publicConfig.apiBaseUrl}/stocks/${encodeURIComponent(symbol)}${suffix}`, { signal, credentials: 'include', cache: 'no-store' });
  if (!response.ok) throw new MarketError(response.status === 404 ? 'Saham tidak ditemukan.' : response.status === 401 || response.status === 403 ? 'Sesi research tidak tersedia.' : 'Data belum dapat dimuat. Coba lagi.');
  const value = await response.json();
  if (!validators[kind](value) || value.mode !== 'research' || value.data_origin !== 'simulation') throw new MarketError('Data tidak sesuai kontrak. Coba muat ulang.');
  if (kind === 'StockDetailResponse') {
    const { data } = value as StockDetailResponse;
    if (data.symbol !== symbol || data.rule.symbol !== symbol || (data.signal && data.signal.symbol !== symbol) ||
      (data.depth && !consistentBook(data.depth, symbol)) || (data.liquidity && (!data.signal || data.liquidity.signal_id !== data.signal.signal_id || data.liquidity.signal_version !== data.signal.version || data.liquidity.nominal_idr !== data.signal.assumptions.nominal_idr))) throw new MarketError('Snapshot tidak konsisten. Muat ulang seluruh snapshot.');
  }
  if (kind === 'SignalHistoryResponse' && (value as SignalHistoryResponse).data.some(s => s.symbol !== symbol)) throw new MarketError('Riwayat tidak sesuai saham.');
  if (kind === 'ChartResponse') {
    const chart = value as ChartResponse;
    const { data } = chart;
    const times = data.candles.map(c => Date.parse(c.at));
    if (data.symbol !== symbol || data.interval !== interval || times.some((t, i) => t > Date.parse(chart.as_of) || (i > 0 && t <= times[i - 1])) ||
      data.candles.some(c => Number(c.low_idr) > Math.min(Number(c.open_idr), Number(c.close_idr)) || Number(c.high_idr) < Math.max(Number(c.open_idr), Number(c.close_idr)) || Number(c.low_idr) > Number(c.high_idr)) ||
      data.projection.some(p => Date.parse(p.at) <= Math.max(Date.parse(chart.as_of), ...times) || Number(p.lower_idr) > Number(p.median_idr) || Number(p.median_idr) > Number(p.upper_idr))) throw new MarketError('Chart tidak konsisten. Coba muat ulang.');
    for (const coverage of new Set(data.projection.map(p => p.coverage))) {
      const points = data.projection.filter(p => p.coverage === coverage);
      if (points.some((p, i) => i > 0 && Date.parse(p.at) <= Date.parse(points[i - 1].at))) throw new MarketError('Urutan proyeksi tidak konsisten.');
    }
  }
  return value as Responses[K];
}

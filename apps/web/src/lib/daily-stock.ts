import { parseScreener, type Candidate } from './screener';

export type HistoryPoint = { date: string; close_idr: string; volume: string; return_1d: string | null };
export type BacktestTrade = { signal_date: string; entry_date: string; exit_date: string; entry_close: string; exit_close: string; net_return_pct: number; equity: number; exit_reason: 'stop_close' | 'target_close' | 'time_exit' };
export type Backtest = {
  origin: 'simulation'; method: 'ma-rsi-close-replay-v1'; direction: 'long_only'; sample: 'exploratory_in_sample';
  target_trades: 1000; completed_trades: number; target_reached: boolean;
  status: 'data_gap' | 'complete' | 'insufficient_trades'; start_date: string | null; end_date: string | null;
  unclosed_position: boolean; win_count: number; loss_count: number; flat_count: number;
  total_return_pct: number | null; max_drawdown_pct: number | null;
  buy_fee: number; sell_fee: number; slippage_each_side: number; holding_sessions: 15; trades: BacktestTrade[];
};
export type DailyStock = {
  origin: 'market'; feed: 'daily'; symbol: string; date: string; as_of: string;
  available_at: string; stale: boolean; close_idr: string; history: HistoryPoint[];
  plan: Candidate | null; backtest: Backtest | null;
  order_book: null; individual_queue: null; depth_status: 'feed_not_connected';
  source: string; license_url: string; attribution: string;
};
const decimal = (value: unknown): value is string => typeof value === 'string' && value.trim() !== '' && value.length < 80 && Number.isFinite(Number(value));
const date = (value: unknown): value is string => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;

function validateBacktest(b: Backtest) {
  if (!b || b.origin !== 'simulation' || b.method !== 'ma-rsi-close-replay-v1' || b.direction !== 'long_only' || b.sample !== 'exploratory_in_sample' ||
      b.target_trades !== 1000 || !Number.isSafeInteger(b.completed_trades) || b.completed_trades < 0 || b.completed_trades > 1000 ||
      typeof b.target_reached !== 'boolean' || b.target_reached !== (b.completed_trades === 1000) ||
      !['data_gap', 'complete', 'insufficient_trades'].includes(b.status) ||
      (b.status === 'complete' && !b.target_reached) || (b.status === 'insufficient_trades' && b.target_reached) ||
      !date(b.start_date) || !date(b.end_date) || b.start_date > b.end_date || typeof b.unclosed_position !== 'boolean' ||
      [b.win_count, b.loss_count, b.flat_count].some(n => !Number.isSafeInteger(n) || n < 0) || b.win_count + b.loss_count + b.flat_count !== b.completed_trades ||
      b.holding_sessions !== 15 || [b.buy_fee, b.sell_fee, b.slippage_each_side].some(n => typeof n !== 'number' || !Number.isFinite(n) || n < 0 || n >= .05) ||
      !Array.isArray(b.trades) || b.trades.length !== b.completed_trades || b.trades.some((t, i) => !t ||
        !date(t.signal_date) || !date(t.entry_date) || !date(t.exit_date) || t.signal_date < b.start_date! || t.signal_date >= t.entry_date || t.entry_date >= t.exit_date || t.exit_date > b.end_date! ||
        (i > 0 && t.entry_date <= b.trades[i - 1].exit_date) ||
        !decimal(t.entry_close) || Number(t.entry_close) <= 0 || !decimal(t.exit_close) || Number(t.exit_close) <= 0 ||
        typeof t.net_return_pct !== 'number' || !Number.isFinite(t.net_return_pct) || t.net_return_pct <= -100 ||
        typeof t.equity !== 'number' || !Number.isFinite(t.equity) || t.equity <= 0 || !['stop_close', 'target_close', 'time_exit'].includes(t.exit_reason) ||
        Math.abs(t.equity - (i ? b.trades[i - 1].equity : 1) * (1 + t.net_return_pct / 100)) > 1e-6 * Math.max(1, t.equity)) ||
      b.trades.filter(t => t.net_return_pct > 0).length !== b.win_count || b.trades.filter(t => t.net_return_pct < 0).length !== b.loss_count ||
      [b.total_return_pct, b.max_drawdown_pct].some(n => n !== null && (typeof n !== 'number' || !Number.isFinite(n))) ||
      (b.max_drawdown_pct !== null && (b.max_drawdown_pct < 0 || b.max_drawdown_pct > 100)) ||
      ((b.status === 'data_gap' || !b.completed_trades) && (b.total_return_pct !== null || b.max_drawdown_pct !== null)) ||
      (b.status !== 'data_gap' && b.completed_trades > 0 && (b.total_return_pct === null || b.max_drawdown_pct === null || Math.abs(b.total_return_pct - (b.trades.at(-1)!.equity - 1) * 100) > .001))) throw new Error('Hasil backtest tidak valid.');
}

export function parseDailyStock(value: unknown, symbol: string): DailyStock {
  const d = value as DailyStock;
  if (!d || d.origin !== 'market' || d.feed !== 'daily' || d.symbol !== symbol || !date(d.date) ||
      !Number.isFinite(Date.parse(d.as_of)) || !Number.isFinite(Date.parse(d.available_at)) ||
      Date.parse(d.available_at) > Date.parse(d.as_of) || typeof d.stale !== 'boolean' ||
      !decimal(d.close_idr) || Number(d.close_idr) <= 0 || Number(d.close_idr) >= 1e16 ||
      d.order_book !== null || d.individual_queue !== null || d.depth_status !== 'feed_not_connected' ||
      d.source !== 'https://dataset.aethereal.top/datasets/idx-stock-features' ||
      d.license_url !== 'https://creativecommons.org/licenses/by/4.0/' || typeof d.attribution !== 'string' ||
      !Array.isArray(d.history) || d.history.length > 253 || d.history.some((p, i) =>
        !p || !date(p.date) || p.date > d.date || (i > 0 && p.date <= d.history[i - 1].date) ||
        !decimal(p.close_idr) || Number(p.close_idr) <= 0 || Number(p.close_idr) >= 1e16 ||
        typeof p.volume !== 'string' || !/^(?:0|[1-9][0-9]{0,18})$/.test(p.volume) || BigInt(p.volume) > BigInt('1000000000000000000') ||
        (p.return_1d !== null && (!decimal(p.return_1d) || Number(p.return_1d) < -1)))) throw new Error('Data detail saham tidak valid.');
  if (d.history.length && (d.history.at(-1)!.date !== d.date || Number(d.history.at(-1)!.close_idr) !== Number(d.close_idr))) throw new Error('Harga dan riwayat tidak konsisten.');
  if (d.plan !== null) {
    if (d.plan?.symbol !== symbol) throw new Error('Rencana tidak sesuai saham.');
    parseScreener({ method: 'ma-rsi-momentum-2r-v1', latest_date: d.date, available_at: d.available_at, stale: d.stale, needs_reimport: false, universe_count: 1, rows: [d.plan], source: d.source, license_url: d.license_url, attribution: d.attribution });
  }
  if (d.backtest !== null) {
    validateBacktest(d.backtest);
    if (d.backtest.end_date! > d.date) throw new Error('Tanggal backtest melampaui data.');
  }
  return d;
}

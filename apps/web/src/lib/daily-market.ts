export type DailyRow = { symbol: string; date: string; close_idr: string; volume: string; return_1d: string | null; rsi_14: string | null; stale: boolean };
export type DailyData = { mode: 'research'; origin: 'market'; frequency: 'daily'; provider: 'Aethereal'; license: 'CC BY 4.0'; source: string; license_url: string; attribution: string; available_at: string; latest_date: string; stale: boolean; signals_enabled: false; sha256: string; rows: DailyRow[]; quality: { rows: number; accepted_rows: number; rejected_rows: number; published_symbols: number } };
const source = 'https://dataset.aethereal.top/datasets/idx-stock-features';
const license = 'https://creativecommons.org/licenses/by/4.0/';
const decimal = (value: unknown) => typeof value === 'string' && value.length < 80 && Number.isFinite(Number(value)) && value.trim() !== '';
const day = (value: unknown): value is string => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;
export function parseDailyMarket(value: unknown): DailyData {
  const data = value as DailyData;
  if (!data || data.mode !== 'research' || data.origin !== 'market' || data.frequency !== 'daily' || data.provider !== 'Aethereal' ||
      data.license !== 'CC BY 4.0' || data.source !== source || data.license_url !== license || data.signals_enabled !== false ||
      typeof data.attribution !== 'string' || !data.attribution || !Number.isFinite(Date.parse(data.available_at)) || !day(data.latest_date) ||
      typeof data.stale !== 'boolean' || !/^[a-f0-9]{64}$/.test(data.sha256) || !Array.isArray(data.rows) || !data.rows.length || data.rows.length > 2000 ||
      new Set(data.rows.map(r => r?.symbol)).size !== data.rows.length || data.rows.some(r =>
        !r || typeof r.symbol !== 'string' || !/^[A-Z][A-Z0-9]{1,7}$/.test(r.symbol) || !day(r.date) || r.date > data.latest_date ||
        !decimal(r.close_idr) || Number(r.close_idr) <= 0 || Number(r.close_idr) >= 1e16 ||
        typeof r.volume !== 'string' || !/^(?:0|[1-9][0-9]{0,18})$/.test(r.volume) || BigInt(r.volume) > BigInt('1000000000000000000') ||
        typeof r.stale !== 'boolean' || (r.return_1d !== null && (!decimal(r.return_1d) || Number(r.return_1d) < -1 || Number(r.return_1d) > 1e12)) ||
        (r.rsi_14 !== null && (!decimal(r.rsi_14) || Number(r.rsi_14) < 0 || Number(r.rsi_14) > 100)))) throw new Error('Data harian tidak valid.');
  if (!data.quality || [data.quality.rows, data.quality.accepted_rows, data.quality.rejected_rows, data.quality.published_symbols].some(n => !Number.isSafeInteger(n) || n < 0) ||
      data.quality.rows !== data.quality.accepted_rows + data.quality.rejected_rows || data.quality.published_symbols !== data.rows.length) throw new Error('Laporan kualitas tidak valid.');
  return data;
}

export type Candidate = {
  symbol: string; date: string; direction: 'bullish' | 'bearish'; reference: string;
  take_profit: string; stop_loss: string; potential_pct: string; risk_pct: string;
  reward_risk: string; rsi_14: string; momentum_20d_pct: string;
};
type Result = {
  method: string; latest_date: string; available_at: string; stale: boolean;
  source: string; license_url: string; attribution: string; rows: Candidate[];
  universe_count: number; needs_reimport: boolean;
};
const finite = (v: unknown) => typeof v === 'string' && v.trim() !== '' && Number.isFinite(Number(v));
export function parseScreener(value: unknown): Result {
  const data = value as Result;
  if (!data || data.method !== 'ma-rsi-momentum-2r-v1' || !Array.isArray(data.rows) || data.rows.length > 2000 ||
      !/^\d{4}-\d{2}-\d{2}$/.test(data.latest_date) || !Number.isFinite(Date.parse(data.latest_date)) ||
      !Number.isFinite(Date.parse(data.available_at)) || typeof data.stale !== 'boolean' ||
      typeof data.needs_reimport !== 'boolean' || !Number.isSafeInteger(data.universe_count) || data.universe_count < data.rows.length ||
      typeof data.attribution !== 'string' || data.source !== 'https://dataset.aethereal.top/datasets/idx-stock-features' ||
      data.license_url !== 'https://creativecommons.org/licenses/by/4.0/' ||
      new Set(data.rows.map(r => r?.symbol)).size !== data.rows.length ||
      (data.stale && data.rows.length > 0) || data.rows.some(r => {
        if (!r || !/^[A-Z][A-Z0-9]{1,7}$/.test(r.symbol) || r.date !== data.latest_date ||
            !['bullish', 'bearish'].includes(r.direction) ||
            ![r.reference, r.take_profit, r.stop_loss, r.potential_pct, r.risk_pct, r.reward_risk, r.rsi_14, r.momentum_20d_pct].every(finite)) return true;
        const [entry, tp, sl, potential, risk, rr, rsi] = [r.reference, r.take_profit, r.stop_loss, r.potential_pct, r.risk_pct, r.reward_risk, r.rsi_14].map(Number);
        return entry < 50 || tp < 50 || sl <= 0 || risk < 1 || risk > 10 || rr < 2 || rsi < 0 || rsi > 100 ||
          (r.direction === 'bullish' ? !(tp > entry && entry > sl && potential > 0) : !(tp < entry && entry < sl && potential < 0)) ||
          Math.abs(potential - (tp / entry - 1) * 100) > 0.001 ||
          Math.abs(risk - Math.abs(sl / entry - 1) * 100) > 0.001 ||
          Math.abs(rr - Math.abs(tp - entry) / Math.abs(sl - entry)) > 0.001;
      })) throw new Error('Hasil analisis tidak valid.');
  return data;
}

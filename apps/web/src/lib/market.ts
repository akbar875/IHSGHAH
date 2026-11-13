import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import schema from './generated/candidates.schema.json';
import type { CandidatesResponse } from './generated/candidates';
import { publicConfig } from './config';

export type Candidate = CandidatesResponse['data'][number];
// Conditional refinements inherit types from their parent in the canonical schema.
const ajv = new Ajv2020({ strict: true, strictTypes: false });
addFormats(ajv);
const valid = ajv.compile<CandidatesResponse>({ $ref: '#/$defs/CandidatesResponse', $defs: schema.$defs });
export class MarketError extends Error {}

export function parseCandidates(value: unknown, nominal: string): CandidatesResponse {
  if (!valid(value) || value.mode !== publicConfig.mode || value.data_origin !== 'simulation' ||
    value.data.some(signal => signal.assumptions.nominal_idr !== nominal)) {
    throw new MarketError('Data tidak sesuai permintaan. Coba muat ulang.');
  }
  return value;
}

export async function fetchCandidates(nominal: string, signal: AbortSignal): Promise<CandidatesResponse> {
  const url = new URL(`${publicConfig.apiBaseUrl}/candidates`);
  url.searchParams.set('nominal_idr', nominal);
  const response = await fetch(url, { credentials: 'include', cache: 'no-store', signal });
  if (!response.ok) {
    throw new MarketError(response.status === 401 || response.status === 403
      ? 'Sesi tidak tersedia. Siapkan sesi research lokal lalu coba lagi.'
      : response.status === 503 ? 'Data belum tersedia. Coba lagi setelah layanan research tersedia.'
      : 'Data gagal dimuat. Silakan coba lagi.');
  }
  return parseCandidates(await response.json(), nominal);
}

const rupiah = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 2 });
export const money = (value: string) => rupiah.format(Number(value));
export const time = (value: string) => new Intl.DateTimeFormat('id-ID', {
  timeZone: 'Asia/Jakarta', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit',
}).format(new Date(value)) + ' WIB';
export function nominalValue(value: string): string | null {
  if (!/^[1-9][0-9]{0,11}$/.test(value)) return null;
  return `${value}.00`;
}

export function statusMessages(response: CandidatesResponse): string[] {
  const { quality } = response;
  const messages: string[] = [];
  if (quality.reasons.includes('MARKET_CLOSED')) messages.push('Pasar tutup. Tunggu sesi berikutnya.');
  if (quality.feed === 'delayed' || quality.reasons.includes('DELAYED_FEED')) messages.push('Data delayed. Harga dapat tertinggal dari pasar.');
  if (quality.status === 'stale' || quality.reasons.includes('SEQUENCE_GAP') || quality.reasons.includes('RESYNC_REQUIRED')) messages.push('Data kedaluwarsa. Tunggu pembaruan sebelum mempertimbangkan entry.');
  if (quality.status === 'disconnected' || quality.feed === 'disconnected') messages.push('Koneksi terputus. Entry ditahan sampai data pulih.');
  if (quality.reasons.includes('MODEL_UNVALIDATED') || response.data.some(s => s.target_probability.status === 'unvalidated')) messages.push('Model belum tervalidasi. Peluang dan estimasi hasil tidak tersedia.');
  if (quality.status === 'unavailable') messages.push('Data pasar belum tersedia. Kandidat simulasi hanya untuk mencoba tampilan.');
  if (quality.status === 'degraded') messages.push('Kualitas data menurun. Tunggu data pulih sebelum entry.');
  return messages;
}

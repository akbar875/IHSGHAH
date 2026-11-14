import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import schema from './generated/candidates.schema.json';
import { publicConfig } from './config';
import type { RiskProfileResponse, WatchlistResponse, SettingsEligibilityResponse } from './generated/candidates';

const ajv = new Ajv2020({ strict: true, strictTypes: false });
addFormats(ajv);
const validators = {
  '/settings/profile': ajv.compile<RiskProfileResponse>({ $ref: '#/$defs/RiskProfileResponse', $defs: schema.$defs }),
  '/watchlist': ajv.compile<WatchlistResponse>({ $ref: '#/$defs/WatchlistResponse', $defs: schema.$defs }),
  '/settings/eligibility': ajv.compile<SettingsEligibilityResponse>({ $ref: '#/$defs/SettingsEligibilityResponse', $defs: schema.$defs }),
};
type Responses = { '/settings/profile': RiskProfileResponse; '/watchlist': WatchlistResponse; '/settings/eligibility': SettingsEligibilityResponse };

export async function preference<T extends keyof Responses>(path: T, body?: unknown, signal?: AbortSignal): Promise<Responses[T] | null> {
  const response = await fetch(`${publicConfig.apiBaseUrl}${path}`, {
    credentials: 'include', cache: 'no-store', signal: signal ?? AbortSignal.timeout(10000),
    ...(body === undefined ? {} : { method: 'PUT', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify(body) }),
  });
  if (response.status === 404 && body === undefined && path !== '/watchlist') return null;
  if (!response.ok) throw new Error(response.status === 422 ? 'Input ditolak. Periksa nominal, batas risiko, dan periode biaya.'
    : response.status === 409 ? 'Versi sudah digunakan. Muat ulang lalu coba lagi.'
    : response.status === 401 || response.status === 403 ? 'Sesi research tidak tersedia atau akses ditolak.'
    : 'Pengaturan belum dapat dimuat atau disimpan. Coba lagi.');
  const value = await response.json();
  if (!validators[path](value) || value.mode !== publicConfig.mode || value.data_origin !== 'simulation') throw new Error('Data pengaturan tidak sesuai kontrak.');
  return value as Responses[T];
}


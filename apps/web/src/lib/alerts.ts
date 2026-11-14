import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import schema from './generated/candidates.schema.json';
import type { Alert, AlertsResponse } from './generated/candidates';
import { publicConfig } from './config';

const ajv = new Ajv2020({ strict: true, strictTypes: false });
addFormats(ajv);
const check = ajv.compile<AlertsResponse>({ $ref: '#/$defs/AlertsResponse', $defs: schema.$defs });
export const alertLabels: Record<Alert['type'], string> = {
  ENTRY_READY: 'Entry aktif', INVALIDATED: 'Rencana tidak berlaku', TP: 'Target exit',
  STOP: 'Stop exit', TIME_EXIT: 'Batas waktu exit', PLAN_CHANGED: 'Rencana berubah',
  DATA_DISCONNECTED: 'Gangguan data',
};
export const priority: Record<Alert['type'], number> = {
  STOP: 0, DATA_DISCONNECTED: 0, TIME_EXIT: 1, TP: 1, INVALIDATED: 2, PLAN_CHANGED: 3, ENTRY_READY: 4,
};
export async function fetchAlerts(signal: AbortSignal): Promise<Alert[]> {
  const response = await fetch(`${publicConfig.apiBaseUrl}/alerts`, {
    credentials: 'include', cache: 'no-store', signal,
  });
  if (!response.ok) throw new Error('Notifikasi belum dapat dimuat. Periksa sesi dan koneksi.');
  const body = await response.json();
  if (!check(body) || body.mode !== publicConfig.mode || body.data_origin !== 'simulation') {
    throw new Error('Notifikasi ditolak karena mode atau kontrak tidak sesuai.');
  }
  return Array.from(new Map(body.data.map(item => [item.dedup_key, item])).values())
    .sort((a, b) => priority[a.type] - priority[b.type] || Date.parse(b.created_at) - Date.parse(a.created_at));
}

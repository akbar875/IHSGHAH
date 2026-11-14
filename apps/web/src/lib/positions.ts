import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import schema from './generated/candidates.schema.json';
import { publicConfig } from './config';
import type { Position, PositionsResponse, PositionResponse, PositionMonitorResponse } from './generated/candidates';
const ajv = new Ajv2020({ strict: true, strictTypes: false });
addFormats(ajv);
const checks = {
  PositionsResponse: ajv.compile<PositionsResponse>({ $ref: '#/$defs/PositionsResponse', $defs: schema.$defs }),
  PositionResponse: ajv.compile<PositionResponse>({ $ref: '#/$defs/PositionResponse', $defs: schema.$defs }),
  PositionMonitorResponse: ajv.compile<PositionMonitorResponse>({ $ref: '#/$defs/PositionMonitorResponse', $defs: schema.$defs }),
};
type Responses = { PositionsResponse: PositionsResponse; PositionResponse: PositionResponse; PositionMonitorResponse: PositionMonitorResponse };
export async function positions<T extends keyof Responses>(path: string, kind: T, command?: { method: 'POST' | 'PUT'; body: unknown; key: string }): Promise<Responses[T]> {
  const response = await fetch(`${publicConfig.apiBaseUrl}/positions${path}`, {
    credentials: 'include', cache: 'no-store', signal: AbortSignal.timeout(10000),
    ...(command ? { method: command.method, headers: { 'Content-Type': 'application/json', 'Idempotency-Key': command.key }, body: JSON.stringify(command.body) } : {}),
  });
  if (!response.ok) throw new Error(response.status === 409 ? 'Konflik: periksa lot tersisa atau key yang sudah digunakan.'
    : response.status === 422 ? 'Input ditolak. Periksa harga, lot, biaya, dan urutan waktu fill.'
    : 'Posisi belum dapat dimuat/disimpan. Periksa sesi dan koneksi lalu coba lagi.');
  const data = await response.json();
  if (!checks[kind](data) || data.mode !== publicConfig.mode || data.data_origin !== 'simulation') throw new Error('Data posisi tidak sesuai kontrak pencatatan manual.');
  const payload = data as Responses[T];
  const records: Position[] = kind === 'PositionsResponse' ? (payload as PositionsResponse).data
    : [kind === 'PositionMonitorResponse' ? (payload as PositionMonitorResponse).data.position : (payload as PositionResponse).data];
  if (records.some(p => p.fills.some(f => f.origin !== 'manual'))) throw new Error('Hasil simulasi tidak dapat ditampilkan sebagai catatan manual.');
  return data as Responses[T];
}

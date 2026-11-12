// The shell cannot switch into paper/live before server-owned mode exists.
function apiBaseUrl(value: string): string {
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error('NEXT_PUBLIC_API_BASE_URL must be an HTTP(S) base URL without credentials, query or fragment');
  }
  return url.toString().replace(/\/$/, '');
}

export const publicConfig = Object.freeze({
  mode: 'research',
  dataOrigin: 'simulation',
  displayTimezone: 'Asia/Jakarta',
  apiBaseUrl: apiBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000/api/v1'),
});

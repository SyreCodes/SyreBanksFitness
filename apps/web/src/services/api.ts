let accessToken: string | null = null;
export const setAccessToken = (token: string | null) => { accessToken = token; };
export const getAccessToken = () => accessToken;
export type ListResult<T> = { items: T[]; total: number };
export class ApiError extends Error {
  constructor(message: string, public status: number, public code?: string, public requestId?: string) { super(message); this.name = 'ApiError'; }
}
export function csrfToken(): string {
  return document.cookie.split('; ').find(value => value.startsWith('sbf_csrf='))?.split('=')[1] ?? '';
}
export function apiUrl(path: string): string { return `${import.meta.env.VITE_API_URL || '/api/v1'}${path}`; }
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  if (options.method && !['GET', 'HEAD'].includes(options.method.toUpperCase())) headers.set('X-CSRF-Token', csrfToken());
  let response: Response;
  try { response = await fetch(apiUrl(path), { ...options, headers, credentials: 'include' }); }
  catch { throw new ApiError('Unable to reach the coaching platform. Please try again.', 0, 'NETWORK_ERROR'); }
  if (response.status === 204) return undefined as T;
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const body = data as { error?: { message?: string; code?: string; request_id?: string }; detail?: unknown } | null;
    const detail = typeof body?.detail === 'string' ? body.detail : undefined;
    throw new ApiError(body?.error?.message ?? detail ?? 'That request could not be completed.', response.status, body?.error?.code, body?.error?.request_id);
  }
  return data as T;
}
export async function downloadFile(path: string, filename: string): Promise<void> {
  const headers = new Headers();
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  let response: Response;
  try { response = await fetch(apiUrl(path), {headers,credentials:'include'}); }
  catch { throw new ApiError('Unable to reach the platform. Please try again.',0,'NETWORK_ERROR'); }
  if (!response.ok) {
    const body = await response.json().catch(()=>null) as {error?:{message?:string;code?:string;request_id?:string}} | null;
    throw new ApiError(body?.error?.message || 'The document could not be downloaded.',response.status,body?.error?.code,body?.error?.request_id);
  }
  if (!response.headers.get('Content-Type')?.includes('application/pdf')) throw new ApiError('The server returned an unexpected document format.',502,'INVALID_DOCUMENT');
  const url=URL.createObjectURL(await response.blob());const link=document.createElement('a');link.href=url;link.download=filename;link.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);
}

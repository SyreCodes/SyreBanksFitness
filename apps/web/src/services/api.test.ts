import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, setAccessToken } from './api';
afterEach(() => { vi.unstubAllGlobals(); setAccessToken(null); });
describe('API boundary', () => {
  it('sends credentials and bearer identity without persisting tokens', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 'client' }), { status: 200 })); vi.stubGlobal('fetch', fetch); setAccessToken('short-lived');
    expect(await api('/clients/me/profile')).toEqual({ id: 'client' });
    expect(fetch.mock.calls[0][0]).toBe('/api/v1/clients/me/profile');
    expect(fetch.mock.calls[0][1].credentials).toBe('include');
    expect(fetch.mock.calls[0][1].headers.get('Authorization')).toBe('Bearer short-lived');
  });
  it('exposes friendly API errors and correlation IDs', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'FORBIDDEN', message: 'You cannot access this client.', request_id: 'req-1' } }), { status: 403 })));
    await expect(api('/clients/private')).rejects.toMatchObject({ status: 403, code: 'FORBIDDEN', requestId: 'req-1' });
  });
  it('handles network failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    await expect(api('/products')).rejects.toBeInstanceOf(ApiError);
  });
});

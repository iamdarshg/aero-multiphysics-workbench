import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiBaseUrl, checkingApiStatus, probeApi } from './api';

describe('local API capability probe', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('uses a configurable base URL without a trailing slash', () => {
    vi.stubEnv('NEXT_PUBLIC_API_BASE_URL', 'http://127.0.0.1:8123/');
    expect(apiBaseUrl()).toBe('http://127.0.0.1:8123');
  });

  it('reports readiness from both health and workbench state', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => Promise.resolve(new Response(
      String(input).endsWith('/health')
        ? JSON.stringify({ status: 'ready', native_solvers: {} })
        : JSON.stringify({ default_coupling_strength: 0.9, available_result_sources: ['analytical', 'benchmark'] }),
      { status: 200, headers: { 'content-type': 'application/json' } },
    )));
    vi.stubGlobal('fetch', fetchMock);

    const status = await probeApi();
    expect(status.state).toBe('ready');
    expect(status.label).toContain('analytical routes');
    expect(status.detail).toContain('2 result source contracts');
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('fails closed and remains explicit when the API is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('offline'))));
    const status = await probeApi();
    expect(status).toEqual({
      state: 'offline',
      label: 'API disconnected · sample-only state',
      detail: expect.stringContaining('Native solver execution remains fail-closed.'),
    });
  });

  it('provides a non-solver checking state for initial paint', () => {
    expect(checkingApiStatus.state).toBe('checking');
    expect(checkingApiStatus.detail).toContain('No solver process');
  });
});

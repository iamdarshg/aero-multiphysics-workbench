export type ApiStatus =
  | { state: 'checking'; label: string; detail: string }
  | { state: 'ready'; label: string; detail: string }
  | { state: 'offline'; label: string; detail: string };

export interface WorkbenchState {
  default_coupling_strength: number;
  available_result_sources: string[];
}

const DEFAULT_API_BASE = 'http://localhost:8000';
const REQUEST_TIMEOUT_MS = 1800;

export const apiBaseUrl = (): string => {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  return (configured || DEFAULT_API_BASE).replace(/\/$/, '');
};

const fetchJson = async <T>(path: string, signal: AbortSignal): Promise<T> => {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    method: 'GET',
    headers: { accept: 'application/json' },
    signal,
  });
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  return response.json() as Promise<T>;
};

export const probeApi = async (): Promise<ApiStatus> => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const [health, state] = await Promise.all([
      fetchJson<{ status: string; native_solvers: Record<string, unknown> }>('/health', controller.signal),
      fetchJson<WorkbenchState>('/api/v1/workbench/state', controller.signal),
    ]);
    if (health.status !== 'ready') throw new Error('API is not ready');
    const nativeCount = Object.keys(health.native_solvers ?? {}).length;
    const sourceCount = state.available_result_sources.length;
    return {
      state: 'ready',
      label: 'API ready · analytical routes available',
      detail: `${sourceCount} result source contracts · ${nativeCount} native solver capabilities verified`,
    };
  } catch {
    return {
      state: 'offline',
      label: 'API disconnected · sample-only state',
      detail: 'Start the local API to inspect live analytical receipts. Native solver execution remains fail-closed.',
    };
  } finally {
    clearTimeout(timeout);
  }
};

export const checkingApiStatus: ApiStatus = {
  state: 'checking',
  label: 'Checking local API…',
  detail: 'No solver process is launched by this capability check.',
};

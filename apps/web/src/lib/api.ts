// Backwards-compatible capability probe built on the single typed client.
// New code should import from './job-client' directly.

import { getHealth, getWorkbenchState } from './job-client';

export type ApiStatus =
  | { state: 'checking'; label: string; detail: string }
  | { state: 'ready'; label: string; detail: string }
  | { state: 'offline'; label: string; detail: string };

export interface WorkbenchState {
  default_coupling_strength: number;
  available_result_sources: string[];
}

export { apiBaseUrl } from './job-client';

export const probeApi = async (): Promise<ApiStatus> => {
  try {
    const [health, state] = await Promise.all([getHealth(), getWorkbenchState()]);
    if (health.status !== 'ready') throw new Error('API is not ready');
    const nativeCount = Object.keys(health.nativeSolvers ?? {}).length;
    const sourceCount = state.availableResultSources.length;
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
  }
};

export const checkingApiStatus: ApiStatus = {
  state: 'checking',
  label: 'Checking local API…',
  detail: 'No solver process is launched by this capability check.',
};

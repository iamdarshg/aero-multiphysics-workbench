import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  artifactFileUrl,
  JobApiError,
  cancelJob,
  downloadJobArtifact,
  getCapabilities,
  getHealth,
  getJob,
  getJobArtifacts,
  getJobEvents,
  getJobProvenance,
  getJobResult,
  getParticipants,
  getResultManifest,
  getWorkbenchState,
  parseSseBody,
  resultManifestUrl,
  submitJob,
  subscribeJobEvents,
} from './job-client';

const jsonResponse = (payload: unknown, status = 200): Response =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { 'content-type': 'application/json' },
  });

afterEach(() => vi.unstubAllGlobals());

describe('typed job API client', () => {
  it('loads health with analytical models and native solver map', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(jsonResponse({ status: 'ready', analytical_models: ['edf'], native_solvers: {} }))),
    );
    const health = await getHealth();
    expect(health.status).toBe('ready');
    expect(health.analyticalModels).toEqual(['edf']);
    expect(health.nativeSolvers).toEqual({});
  });

  it('loads workbench state with typed result sources', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({ default_coupling_strength: 0.9, available_result_sources: ['analytical', 'benchmark'] }),
        ),
      ),
    );
    const state = await getWorkbenchState();
    expect(state.defaultCouplingStrength).toBe(0.9);
    expect(state.availableResultSources).toEqual(['analytical', 'benchmark']);
  });

  it('loads capability success with ready and unavailable entries', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ready: [
              {
                participant_id: 'rotor-campbell',
                solver_id: 'ross',
                executable: 'python',
                version: '4.6.0',
                detail: 'ross-rotordynamics 4.6.0 installed',
              },
            ],
            unavailable: [
              {
                participant_id: 'incompressible-steady-flow',
                solver_id: 'openfoam',
                executable: 'simpleFoam',
                detail: 'simpleFoam is not installed',
              },
            ],
          }),
        ),
      ),
    );
    const report = await getCapabilities();
    expect(report.ready).toHaveLength(1);
    expect(report.ready[0]?.participantId).toBe('rotor-campbell');
    expect(report.unavailable).toHaveLength(1);
    expect(report.unavailable[0]?.solverId).toBe('openfoam');
  });

  it('surfaces capability load failure without inventing entries', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('offline'))));
    await expect(getCapabilities()).rejects.toBeInstanceOf(JobApiError);
  });

  it('loads participant manifests for allowed-analysis validation', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            manifest_version: '2',
            participants: [
              {
                participant_id: 'rotor-campbell',
                physics_domain: 'rotordynamics',
                solver_id: 'ross',
                execution_mode: 'in-process',
                inputs: [],
                outputs: [],
                fidelity_levels: ['beam-campbell'],
                coupling_direction: 'none',
                benchmark_ref: 'milestone-2:rotor-campbell',
              },
            ],
          }),
        ),
      ),
    );
    const manifests = await getParticipants();
    expect(manifests.manifestVersion).toBe('2');
    expect(manifests.participants[0]?.fidelityLevels).toEqual(['beam-campbell']);
  });

  it('submits exactly one job with the typed payload', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(jsonResponse({ job_id: 'job-1', state: 'QUEUED', participant_id: 'rotor-campbell' })),
    );
    vi.stubGlobal('fetch', fetchMock);
    const submitted = await submitJob({
      participantId: 'rotor-campbell',
      inputs: { analysis: 'campbell' },
      designId: 'edf-90',
      analysis: 'campbell',
      fidelity: 'beam-campbell',
    });
    expect(submitted.jobId).toBe('job-1');
    expect(submitted.state).toBe('QUEUED');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [callUrl, callInit] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(String(callUrl)).toContain('/v1/native/analyses');
    expect(callInit.method).toBe('POST');
    const body = JSON.parse(String(callInit.body)) as Record<string, unknown>;
    expect(body.participant_id).toBe('rotor-campbell');
    expect(body.fidelity).toBe('beam-campbell');
  });

  it('reads one job status with typed error fields', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({ job_id: 'job-9', state: 'FAILED', error_code: 'CAPABILITY_UNAVAILABLE', error_detail: 'no solver' }),
        ),
      ),
    );
    const status = await getJob('job-9');
    expect(status.state).toBe('FAILED');
    expect(status.errorCode).toBe('CAPABILITY_UNAVAILABLE');
    expect(status.errorDetail).toBe('no solver');
  });

  it('reads persisted job events as JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            job_id: 'job-2',
            events: [
              { sequence: 1, state: 'QUEUED', at: 't0', detail: 'input_hash=abc' },
              { sequence: 2, state: 'PREPARING', at: 't1', detail: 'participant=rotor-campbell' },
            ],
          }),
        ),
      ),
    );
    const events = await getJobEvents('job-2');
    expect(events).toHaveLength(2);
    expect(events[1]?.state).toBe('PREPARING');
  });

  it('parses the SSE event body into the same typed events', () => {
    const body =
      'event: progress\ndata: {"sequence":1,"state":"QUEUED","at":"t0","detail":"queued"}\n\n' +
      'event: progress\ndata: {"sequence":2,"state":"CANCELLED","at":"t1","detail":"cancelled"}\n\n';
    const events = parseSseBody(body);
    expect(events.map((event) => event.state)).toEqual(['QUEUED', 'CANCELLED']);
    expect(events[0]?.sequence).toBe(1);
  });

  it('delivers subscribed events in sequence until the terminal state', async () => {
    const queued = jsonResponse({
      job_id: 'job-3',
      events: [{ sequence: 1, state: 'QUEUED', at: 't0', detail: '' }],
    });
    const done = jsonResponse({
      job_id: 'job-3',
      events: [
        { sequence: 1, state: 'QUEUED', at: 't0', detail: '' },
        { sequence: 2, state: 'CANCELLED', at: 't1', detail: 'cancelled while queued' },
      ],
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(queued).mockResolvedValue(done));
    const seen: string[] = [];
    const finalEvents = await subscribeJobEvents('job-3', {
      pollIntervalMs: 1,
      onEvent: (event) => seen.push(event.state),
    });
    expect(seen).toEqual(['QUEUED', 'CANCELLED']);
    expect(finalEvents).toHaveLength(2);
  });

  it('cancels a job against the backend and returns the state', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse({ job_id: 'job-4', state: 'CANCELLED' })));
    vi.stubGlobal('fetch', fetchMock);
    const result = await cancelJob('job-4');
    expect(result.state).toBe('CANCELLED');
    const [cancelUrl, cancelInit] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(String(cancelUrl)).toContain('/v1/native/analyses/job-4/cancel');
    expect(cancelInit.method).toBe('POST');
  });

  it('reads completed result metadata with native solver identity', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            source: 'native_solver',
            fidelity: 'beam-campbell',
            solver_identity: 'ross',
            solver_version: '4.6.0',
            run_id: 'run-1',
            provenance_id: 'prov-1',
            warnings: [],
            scalars: { first_critical_rpm: 9000 },
            units: { first_critical_rpm: 'rpm' },
            validity: { participant_id: 'rotor-campbell', passed: true, checks: {}, detail: '' },
          }),
        ),
      ),
    );
    const envelope = await getJobResult('job-5');
    expect(envelope.source).toBe('native_solver');
    expect(envelope.solverIdentity).toBe('ross');
    expect(envelope.scalars.first_critical_rpm).toBe(9000);
  });

  it('reads job provenance lineage', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            job_id: 'job-6',
            events: [{ event_id: 'launch-job-6', event_type: 'native.launch-accepted', sequence: 1 }],
          }),
        ),
      ),
    );
    const lineage = await getJobProvenance('job-6');
    expect(lineage.jobId).toBe('job-6');
    expect(lineage.events).toHaveLength(1);
  });

  it('carries backend error codes on typed failures', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(jsonResponse({ detail: { code: 'JOB_NOT_FOUND' } }, 404))));
    let failure: JobApiError | null = null;
    try {
      await getJob('missing');
    } catch (error) {
      failure = error as JobApiError;
    }
    expect(failure).toBeInstanceOf(JobApiError);
    expect(failure?.code).toBe('JOB_NOT_FOUND');
    expect(failure?.status).toBe(404);
  });

  it('reads registered artifact metadata with hashes and download routes', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            job_id: 'job-7',
            artifacts: [
              {
                id: 'result.json',
                name: 'result.json',
                display_name: 'result.json',
                mime: 'application/json',
                category: 'report',
                bytes: 42,
                sha256: 'a'.repeat(64),
                solver_id: 'ross',
                run_id: 'run-1',
                provenance_id: 'prov-1',
                download_url: '/v1/native/artifacts/job-7/result.json',
                uri: 'jobs/job-7/result.json',
              },
              { id: '', name: '', sha256: 'bogus' },
            ],
          }),
        ),
      ),
    );
    const artifacts = await getJobArtifacts('job-7');
    expect(artifacts).toHaveLength(1);
    expect(artifacts[0]?.sha256).toBe('a'.repeat(64));
    expect(artifacts[0]?.downloadUrl).toContain('/v1/native/artifacts/job-7/result.json');
  });

  it('builds absolute artifact and manifest export URLs', () => {
    expect(artifactFileUrl('/v1/native/artifacts/job-8/result.json')).toContain(
      '/v1/native/artifacts/job-8/result.json',
    );
    expect(resultManifestUrl('job-8')).toContain('/v1/native/results/job-8/manifest');
  });

  it('downloads one registered artifact as a blob', async () => {
    const blob = new Blob(['{}'], { type: 'application/json' });
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(new Response(blob, { status: 200 }))),
    );
    const downloaded = await downloadJobArtifact('job-9', 'result.json');
    expect(await downloaded.text()).toBe('{}');
  });

  it('carries the artifact error code when a download is rejected', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(jsonResponse({ detail: { code: 'ARTIFACT_NOT_FOUND' } }, 404))),
    );
    await expect(downloadJobArtifact('job-9', '../sibling')).rejects.toMatchObject({
      code: 'ARTIFACT_NOT_FOUND',
    });
  });

  it('reads the machine-readable result manifest with lineage and hashes', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            job_id: 'job-10',
            design_id: 'edf-90-rotor',
            revision_id: null,
            result_id: 'b'.repeat(64),
            run_id: 'run-2',
            provenance_id: 'prov-2',
            source: 'native_solver',
            fidelity: 'beam-campbell',
            validity: { passed: true, detail: '' },
            solver_identity: 'ross',
            solver_version: '4.6.0',
            input_hash: 'c'.repeat(64),
            artifacts: [{ name: 'result.json', sha256: 'a'.repeat(64), bytes: 42 }],
          }),
        ),
      ),
    );
    const manifest = await getResultManifest('job-10');
    expect(manifest.designId).toBe('edf-90-rotor');
    expect(manifest.provenanceId).toBe('prov-2');
    expect(manifest.artifacts[0]?.sha256).toBe('a'.repeat(64));
  });
});

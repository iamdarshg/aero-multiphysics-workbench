// Typed field-inspection client. The API shape is untrusted until the
// field-manifest contract validates it; unreachable or missing endpoints are
// reported as honest unavailable/error states, never as loaded fields.

import { classifyFieldCollection, type FieldInspectionState } from './field-manifest';
import { JobApiError, getResultFieldPayload } from './job-client';

export const loadFieldInspectionState = async (jobId: string): Promise<FieldInspectionState> => {
  try {
    const payload = await getResultFieldPayload(jobId);
    return classifyFieldCollection(payload);
  } catch (error) {
    if (error instanceof JobApiError) {
      if (error.status === 404) {
        return { status: 'unavailable', reason: 'result-publishes-no-fields' };
      }
      return { status: 'error', reason: error.code || 'field-fetch-failed' };
    }
    return { status: 'error', reason: 'field-fetch-failed' };
  }
};

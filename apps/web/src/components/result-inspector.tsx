'use client';

import { useState } from 'react';
import {
  apiBaseUrl,
  artifactFileUrl,
  downloadJobArtifact,
  type ArtifactMetadata,
} from '../lib/job-client';

export type ArtifactPreviewKind = 'image' | 'text' | 'unsupported';

/** Minimal preview policy: reuse the browser for images/text, export the rest. */
export const artifactPreviewKind = (name: string, mime: string): ArtifactPreviewKind => {
  const lower = name.toLowerCase();
  if (mime.startsWith('image/') || /\.(png|svg|jpg|jpeg|gif|webp)$/.test(lower)) return 'image';
  if (
    mime === 'application/json' ||
    mime.startsWith('text/') ||
    /\.(json|log|txt|dat|sif|comm|xml|py|export)$/.test(lower)
  ) {
    return 'text';
  }
  return 'unsupported';
};

export const PREVIEW_TEXT_LIMIT = 8000;

export const truncatePreviewText = (
  text: string,
  limit: number = PREVIEW_TEXT_LIMIT,
): { text: string; truncated: boolean } => {
  if (text.length <= limit) return { text, truncated: false };
  return { text: text.slice(0, limit), truncated: true };
};

export const buildManifestFilename = (jobId: string): string =>
  `result-manifest-${jobId.slice(0, 8)}.json`;

export const shortHash = (sha256: string): string => sha256.slice(0, 12);

export interface ResultInspectorProps {
  jobId: string;
  manifestUrl: string;
  artifacts: ArtifactMetadata[];
}

/** Compact result/artifact inspection in the current dialog design language. */
export default function ResultInspector({ jobId, manifestUrl, artifacts }: ResultInspectorProps) {
  const [openPreviews, setOpenPreviews] = useState<Record<string, boolean>>({});
  const [previewTexts, setPreviewTexts] = useState<Record<string, string>>({});
  const [previewTruncated, setPreviewTruncated] = useState<Record<string, boolean>>({});
  const [previewErrors, setPreviewErrors] = useState<Record<string, string>>({});
  const [previewLoading, setPreviewLoading] = useState<Record<string, boolean>>({});

  const toggleTextPreview = (artifactId: string): void => {
    const open = !openPreviews[artifactId];
    setOpenPreviews((previous) => ({ ...previous, [artifactId]: open }));
    if (!open || previewTexts[artifactId] !== undefined || previewLoading[artifactId]) return;
    setPreviewLoading((previous) => ({ ...previous, [artifactId]: true }));
    void downloadJobArtifact(jobId, artifactId)
      .then((blob) => blob.text())
      .then((full) => {
        const preview = truncatePreviewText(full);
        setPreviewTexts((previous) => ({ ...previous, [artifactId]: preview.text }));
        setPreviewTruncated((previous) => ({ ...previous, [artifactId]: preview.truncated }));
        setPreviewErrors((previous) => ({ ...previous, [artifactId]: '' }));
      })
      .catch((error: unknown) => {
        setPreviewErrors((previous) => ({
          ...previous,
          [artifactId]: error instanceof Error ? error.message : 'Preview unavailable.',
        }));
      })
      .finally(() => {
        setPreviewLoading((previous) => ({ ...previous, [artifactId]: false }));
      });
  };

  return (
    <section aria-label="Result artifacts">
      <span className="muted-label">RESULT ARTIFACTS</span>
      {artifacts.length === 0 ? (
        <p>No registered artifacts for this result. Nothing is listed from disk.</p>
      ) : (
        <div className="capability-list">
          {artifacts.map((artifact) => {
            const kind = artifactPreviewKind(artifact.displayName, artifact.mime);
            const fileUrl = artifactFileUrl(artifact.downloadUrl || `/v1/native/artifacts/${jobId}/${artifact.id}`);
            return (
              <div key={artifact.id}>
                <span title={`sha256 ${artifact.sha256}`}>
                  {artifact.displayName} · {artifact.category} · {artifact.bytes} B ·
                  sha256 {shortHash(artifact.sha256)}
                </span>
                <b>
                  <a href={fileUrl} download={artifact.displayName}>
                    Export
                  </a>
                </b>
                {kind === 'image' ? (
                  <img src={fileUrl} alt={`Preview of ${artifact.displayName}`} loading="lazy" />
                ) : null}
                {kind === 'text' ? (
                  <div>
                    <button type="button" onClick={() => toggleTextPreview(artifact.id)}>
                      {openPreviews[artifact.id] ? 'Hide preview' : 'Preview'}
                    </button>
                    {openPreviews[artifact.id] ? (
                      <pre>
                        {previewLoading[artifact.id]
                          ? 'Loading preview…'
                          : (previewErrors[artifact.id] ?? '') !== ''
                            ? previewErrors[artifact.id]
                            : (previewTexts[artifact.id] ?? '') +
                              (previewTruncated[artifact.id] ? '\n…truncated…' : '')}
                      </pre>
                    ) : null}
                  </div>
                ) : null}
                {kind === 'unsupported' ? (
                  <small>Metadata + export only — no in-browser renderer for this format.</small>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
      <p>
        <a href={manifestUrl || `${apiBaseUrl()}/v1/native/results/${jobId}/manifest`} download={buildManifestFilename(jobId)}>
          Export result manifest (JSON)
        </a>
      </p>
    </section>
  );
}

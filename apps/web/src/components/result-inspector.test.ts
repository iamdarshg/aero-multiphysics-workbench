import { describe, expect, it } from 'vitest';
import {
  artifactPreviewKind,
  buildManifestFilename,
  PREVIEW_TEXT_LIMIT,
  shortHash,
  truncatePreviewText,
} from './result-inspector';

describe('result inspector preview policy', () => {
  it('previews images with the existing browser renderer', () => {
    expect(artifactPreviewKind('field.png', 'image/png')).toBe('image');
    expect(artifactPreviewKind('sketch.svg', 'image/svg+xml')).toBe('image');
  });

  it('previews JSON and text reports inline', () => {
    expect(artifactPreviewKind('result.json', 'application/json')).toBe('text');
    expect(artifactPreviewKind('solver.log', 'text/plain')).toBe('text');
    expect(artifactPreviewKind('case.sif', 'text/plain')).toBe('text');
  });

  it('falls back to metadata plus export for heavy formats', () => {
    expect(artifactPreviewKind('field.vtu', 'application/octet-stream')).toBe('unsupported');
    expect(artifactPreviewKind('solution.h5', 'application/octet-stream')).toBe('unsupported');
    expect(artifactPreviewKind('domain.msh', 'application/octet-stream')).toBe('unsupported');
    expect(artifactPreviewKind('product.step', 'application/step')).toBe('unsupported');
  });

  it('truncates long previews instead of rendering unbounded text', () => {
    const full = 'x'.repeat(PREVIEW_TEXT_LIMIT + 10);
    const preview = truncatePreviewText(full);
    expect(preview.truncated).toBe(true);
    expect(preview.text).toHaveLength(PREVIEW_TEXT_LIMIT);
    expect(truncatePreviewText('short').truncated).toBe(false);
  });

  it('names manifest exports after the result they describe', () => {
    expect(buildManifestFilename('abcdef123456')).toBe('result-manifest-abcdef12.json');
  });

  it('shortens hashes for compact rows without losing the full digest', () => {
    const digest = 'a'.repeat(64);
    expect(shortHash(digest)).toBe('a'.repeat(12));
  });
});

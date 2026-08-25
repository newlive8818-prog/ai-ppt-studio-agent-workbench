const ARTIFACT_REFERENCE_PATTERN = /^artifact:\/\/([a-z][a-z0-9-]*)\/([0-9a-f]{64})$/;

export interface ParsedArtifactReference {
  readonly kind: string;
  readonly digest: string;
}

export function parseArtifactReference(value: unknown): ParsedArtifactReference | null {
  const match = typeof value === "string"
    ? ARTIFACT_REFERENCE_PATTERN.exec(value)
    : null;
  return match ? { kind: match[1], digest: match[2] } : null;
}

export function isArtifactReference(value: unknown, kind: string): value is string {
  return parseArtifactReference(value)?.kind === kind;
}

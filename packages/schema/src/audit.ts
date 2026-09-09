export const AUDIT_STATUSES = ["PASS", "PARTIAL", "FAIL", "BLOCKED"] as const;
export type AuditStatus = (typeof AUDIT_STATUSES)[number];

export type RequirementId = `section:${number}` | `stopping:${number}`;

export interface EvidenceRef {
  kind: "file" | "test" | "command" | "artifact" | "receipt";
  path: string;
  detail: string;
  sha256: string;
  verified?: boolean;
  supportsPass?: boolean;
  command?: string;
  exitCode?: number;
  receiptId?: string;
}

export interface SourceRef {
  briefId: string;
  section: number;
  lineStart: number;
  lineEnd: number;
}

export interface RequirementEvidence {
  id: RequirementId;
  title: string;
  status: AuditStatus;
  statusExplanation: string;
  sourceRef: SourceRef;
  evidence: EvidenceRef[];
  lastVerifiedAt: string | null;
}

export interface RequirementsAuditDocument {
  schemaVersion: 1;
  statusSemantics: string;
  source: {
    briefId: string;
    sha256: string;
    lineCount: number;
    sectionsRange: string;
    stoppingConditionsRange: string;
  };
  sections: RequirementEvidence[];
  stoppingConditions: RequirementEvidence[];
}

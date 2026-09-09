export const AUDIT_STATUSES = ["PASS", "PARTIAL", "FAIL", "BLOCKED"] as const;
export type AuditStatus = (typeof AUDIT_STATUSES)[number];

export type RequirementId = `section:${number}` | `stopping:${number}`;

export interface EvidenceRef {
  kind: "file" | "test" | "command" | "artifact" | "receipt";
  path: string;
  detail: string;
}

export interface RequirementEvidence {
  id: RequirementId;
  title: string;
  status: AuditStatus;
  evidence: EvidenceRef[];
  lastVerifiedAt: string | null;
}

export interface RequirementsAuditDocument {
  schemaVersion: 1;
  source: {
    brief: string;
    sectionsRange: string;
    stoppingConditionsRange: string;
  };
  sections: RequirementEvidence[];
  stoppingConditions: RequirementEvidence[];
}

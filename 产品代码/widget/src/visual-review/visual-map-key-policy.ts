const RESERVED_COMPACT_VISUAL_MAP_KEY_SEQUENCES = [
  "compiler",
  "compilerversion",
  "handoffprotocolversion",
  "roleruns",
  "releasetargetpolicyref",
  "targetevidencerefs",
  "targetevidenceidentities",
  "internalreviewrefs",
  "rawlineage",
  "visualcompilationplan",
  "visualcompilationplanref",
  "technicalledger",
  "headref",
  "gatestatus",
  "gatestate",
  "artifactheads",
  "processedcommands",
  "lasttransactionid",
  "lineage",
  "futurebackendgovernance",
  "materialinventory",
  "materialdetails",
  "auditlog",
  "internalprocessstate",
  "toolexecution",
  "toolcalls",
] as const;

function visualMapKeyCompact(value: string): string {
  return value.trim()
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");
}

export function isReviewableVisualMapKey(value: string): boolean {
  if (typeof value !== "string" || !value.trim()) return false;
  const compact = visualMapKeyCompact(value);
  return !RESERVED_COMPACT_VISUAL_MAP_KEY_SEQUENCES.includes(
    compact as (typeof RESERVED_COMPACT_VISUAL_MAP_KEY_SEQUENCES)[number],
  );
}

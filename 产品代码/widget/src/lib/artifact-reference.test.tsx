import { describe, expect, it } from "vitest";

import * as artifactReference from "./artifact-reference";

type ArtifactParser = (value: unknown) => { kind: string; digest: string } | null;

describe("artifact reference parser", () => {
  it("exports one closed parser for validation and display", () => {
    const candidate = Reflect.get(artifactReference, "parseArtifactReference");
    expect(candidate).toBeTypeOf("function");
    const parseArtifactReference = candidate as ArtifactParser;
    const digest = "a".repeat(64);

    const visualContractSet = `artifact://visual-contract-set/${digest}`;
    expect(parseArtifactReference(visualContractSet)).toEqual({
      kind: "visual-contract-set",
      digest,
    });
    expect(artifactReference.isArtifactReference(visualContractSet, "visual-contract-set")).toBe(true);
    expect(artifactReference.isArtifactReference(visualContractSet, "visual-contract")).toBe(false);
    expect(parseArtifactReference(`artifact://constructor/${digest}`)).toEqual({
      kind: "constructor",
      digest,
    });
    for (const invalid of [
      null,
      "visual-v1",
      `artifact://Visual-contract/${digest}`,
      `artifact://-visual-contract/${digest}`,
      `artifact://visual-contract/${"A".repeat(64)}`,
      `artifact://visual-contract/${"a".repeat(63)}`,
      `artifact://visual-contract/${digest}/extra`,
    ]) {
      expect(parseArtifactReference(invalid)).toBeNull();
    }
  });
});

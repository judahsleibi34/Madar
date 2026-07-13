import { describe, expect, it } from "vitest";

import {
  getBuilderConflictMessage,
  isBuilderRevisionError,
} from "./PageBuilder.errors";

describe("builder revision recovery", () => {
  it("recognizes stale and missing revision responses without discarding edits", () => {
    expect(isBuilderRevisionError({ code: "project_revision_conflict" })).toBe(true);
    expect(isBuilderRevisionError({ code: "project_revision_required" })).toBe(true);
    expect(
      getBuilderConflictMessage({
        code: "project_revision_conflict",
        context: { current_revision: 9 },
      })
    ).toContain("revision 9");
    expect(
      getBuilderConflictMessage({ code: "project_revision_conflict" })
    ).toContain("local edits are still here");
  });
});

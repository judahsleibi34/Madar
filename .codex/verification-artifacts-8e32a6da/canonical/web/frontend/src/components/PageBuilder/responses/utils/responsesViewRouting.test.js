import { describe, expect, it } from "vitest";
import {
  getResponseView,
  getResponseViewPath,
  hasResponseViewPath,
} from "./responsesViewRouting";

describe("responses view routing", () => {
  const base = "/builder-responses/projects/project-1/responses";

  it("reads completed and incomplete from their own paths", () => {
    expect(getResponseView(`${base}/completed`)).toBe("completed");
    expect(getResponseView(`${base}/incomplete`)).toBe("incomplete");
  });

  it("upgrades the legacy query URL", () => {
    expect(getResponseView(base, "?view=incomplete")).toBe("incomplete");
    expect(hasResponseViewPath(base)).toBe(false);
  });

  it("builds a clean route when switching views", () => {
    expect(getResponseViewPath(`${base}/completed`, "incomplete")).toBe(
      `${base}/incomplete`,
    );
    expect(getResponseViewPath(`${base}/incomplete`, "completed")).toBe(
      `${base}/completed`,
    );
  });
});
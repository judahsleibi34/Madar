import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createResponsesCacheKey,
  getOrCreateResponsesRequest,
  readResponsesCache,
  writeResponsesCache,
} from "./responsesCache";

beforeEach(() => {
  window.sessionStorage.clear();
});

describe("responses cache", () => {
  it("keeps cached pages isolated by user, project, form, and offset", () => {
    const firstKey = createResponsesCacheKey({
      userScope: "user-1",
      projectId: "project-1",
      formId: "form-1",
      limit: 20,
      offset: 0,
    });
    const nextPageKey = createResponsesCacheKey({
      userScope: "user-1",
      projectId: "project-1",
      formId: "form-1",
      limit: 20,
      offset: 20,
    });

    writeResponsesCache(firstKey, [{ id: "response-1" }], {
      limit: 20,
      offset: 0,
      has_more: false,
    });

    expect(readResponsesCache(firstKey)?.responses).toEqual([
      { id: "response-1" },
    ]);
    expect(readResponsesCache(nextPageKey)).toBeNull();
  });

  it("deduplicates simultaneous requests for the same cached page", async () => {
    const loader = vi.fn(async () => ({ submissions: [] }));

    const first = getOrCreateResponsesRequest("shared-page", loader);
    const second = getOrCreateResponsesRequest("shared-page", loader);

    expect(first).toBe(second);
    await Promise.all([first, second]);
    expect(loader).toHaveBeenCalledTimes(1);
  });
});

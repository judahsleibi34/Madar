import { describe, expect, it } from "vitest";

import { getAssistedAnalysisRequest } from "../utils/versionAwareAnalysis";

const body = {
  cleaning_actions: [],
  question: "What is the average cost?",
  language: "en",
  symbols: { currency: "$" },
};

describe("version-aware assisted analysis request", () => {
  it("uses persistent identities without sending the private filename", () => {
    const request = getAssistedAnalysisRequest({
      dataset: {
        persistent_dataset_id: "dataset-1",
        dataset_version_id: "version-1",
        file_path: "private-opaque.csv",
      },
      projectId: "project-1",
      body,
    });

    expect(request).toEqual({
      path: "/analysis/projects/project-1/datasets/dataset-1/versions/version-1/assist",
      body,
      versionAware: true,
    });
    expect(JSON.stringify(request.body)).not.toContain("private-opaque.csv");
  });

  it("preserves the legacy filename-based request when persistent identities are absent", () => {
    expect(
      getAssistedAnalysisRequest({
        dataset: { file_path: "legacy.csv" },
        projectId: "",
        body,
      })
    ).toEqual({
      path: "/analysis/assist",
      body: { input_path: "legacy.csv", ...body },
      versionAware: false,
    });
  });
});

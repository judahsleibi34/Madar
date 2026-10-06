import { beforeEach, expect, it, vi } from "vitest";
import { apiFetch } from "../utils/apiClient";
import { commandAssessment } from "./elearningAssessments";
vi.mock("../utils/apiClient", () => ({
  apiFetch: vi.fn(),
  getApiUrl: path => `/api${path}`,
  readApiResponse: response => response.json(),
  createApiError: (response, data) => Object.assign(new Error(data.message), { status: response.status }),
}));
beforeEach(() => vi.resetAllMocks());
it.each(["update_question", "duplicate_question", "reorder_question", "archive_question", "delete_question", "restore_question"])("posts %s to the existing course and lesson command endpoints", async action => {
  const payload = action === "reorder_question" ? { direction: "up" } : ["archive_question", "delete_question"].includes(action) ? { confirmed: true } : {};
  const body = { action, question_id: "q", expected_revision: 7, payload };
  const result = { block_id: "b", assessment: { revision: 8 }, questions: [] };
  apiFetch.mockResolvedValue({ ok: true, json: async () => result });
  for (const lesson of [null, "lesson/id"]) {
    expect(await commandAssessment("course/id", lesson, "block/id", body)).toEqual(result);
    expect(apiFetch).toHaveBeenLastCalledWith(`/api/elearning/courses/course%2Fid${lesson ? "/lessons/lesson%2Fid" : ""}/assessments/block%2Fid/commands`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
  }
});
it("surfaces rejected commands rather than treating failed requests as saved", async () => {
  apiFetch.mockResolvedValue({ ok: false, status: 409, json: async () => ({ message: "Revision conflict" }) });
  await expect(commandAssessment("c", null, "b", { action: "duplicate_question" })).rejects.toMatchObject({ status: 409, message: "Revision conflict" });
});

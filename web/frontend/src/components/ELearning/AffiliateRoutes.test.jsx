import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import "../../i18n";
import ELearningPlayer from "./ELearningPlayer";
import { fetchMyLearning, fetchLearningAccountContext } from "../../services/elearningPlayer";
vi.mock("../../services/elearningPlayer", () => ({ fetchMyLearning: vi.fn(), fetchLearningAccountContext: vi.fn(), fetchReferralAccount: vi.fn().mockResolvedValue({ available: false }), fetchLearningCourse: vi.fn(), fetchLearningLesson: vi.fn(), completeLearningLesson: vi.fn() }));
vi.mock("./AffiliateDashboard", () => ({ default: () => <h1>Affiliate summary</h1> }));
vi.mock("../../utils/apiClient", async original => ({ ...await original(), apiFetch: vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) }) }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
it("bootstraps affiliate-only access without reading courses or enrollment", async () => {
  fetchMyLearning.mockRejectedValue(new Error("Course API must not be required"));
  fetchLearningAccountContext.mockResolvedValue({ settings: {}, academy: { subdomain: "academy", brand: "Academy" } });
  render(<MemoryRouter initialEntries={["/my-learning/affiliate"]}><Routes><Route path="/my-learning/*" element={<ELearningPlayer />} /></Routes></MemoryRouter>);
  await screen.findByRole("heading", { name: "Affiliate summary" });
  expect(fetchLearningAccountContext).toHaveBeenCalledOnce();
  expect(fetchMyLearning).not.toHaveBeenCalled();
});

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import BuilderProjectLoadError from "./BuilderProjectLoadError";

const mocks = vi.hoisted(() => ({ settings: vi.fn(), initialize: vi.fn() }));
vi.mock("../../../services/elearningSettings", () => ({ fetchELearningSettings: mocks.settings }));
vi.mock("../../../services/elearningAcademy", () => ({ initializeAcademyLanding: mocks.initialize }));

function mount(status, lang) {
  return render(<MemoryRouter initialEntries={["/page-builder/projects/deleted/pages/sections"]}>
    <Routes>
      <Route path="/page-builder/projects/deleted/pages/sections" element={<BuilderProjectLoadError status={status} lang={lang} />} />
      <Route path="/e-learning/landing-page/projects/current/pages" element={<h1>Current Academy editor</h1>} />
      <Route path="/page-builder" element={<h1>Projects</h1>} />
    </Routes>
  </MemoryRouter>);
}

describe("missing Builder project recovery", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mocks.settings.mockResolvedValue({ available: true, academy_management: { full_builder_available: true } });
    mocks.initialize.mockResolvedValue({ id: "current", usage_profile: "academy" });
  });
  afterEach(cleanup);

  it("explicitly opens the durable tenant Academy without creating anything on load", async () => {
    mount(404);
    const button = await screen.findByRole("button", { name: "Open Academy Builder" });
    expect(mocks.initialize).not.toHaveBeenCalled();
    fireEvent.click(button);
    expect(await screen.findByRole("heading", { name: "Current Academy editor" })).toBeTruthy();
    expect(mocks.initialize).toHaveBeenCalledTimes(1);
  });

  it.each([403, 401, 500, 0, null])("does not offer Academy recovery for status %s", async status => {
    mount(status);
    fireEvent.click(screen.getByRole("link", { name: "Back to Projects" }));
    expect(await screen.findByRole("heading", { name: "Projects" })).toBeTruthy();
    expect(mocks.settings).not.toHaveBeenCalled();
    expect(mocks.initialize).not.toHaveBeenCalled();
  });

  it.each([
    { available: false, academy_management: { full_builder_available: true } },
    { available: true },
    { available: true, academy_management: { full_builder_available: false } },
  ])("requires authorized management metadata %j", async data => {
    mocks.settings.mockResolvedValue(data);
    mount(404);
    await waitFor(() => expect(mocks.settings).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: "Open Academy Builder" })).toBeNull();
    expect(mocks.initialize).not.toHaveBeenCalled();
  });

  it("keeps a rejected recovery on the error page and allows retry", async () => {
    mocks.initialize.mockRejectedValueOnce({ status: 403 });
    mount(404);
    fireEvent.click(await screen.findByRole("button", { name: "Open Academy Builder" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Current Academy editor" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Open Academy Builder" }));
    expect(await screen.findByRole("heading", { name: "Current Academy editor" })).toBeTruthy();
  });

  it("never navigates to a non-Academy project returned in error", async () => {
    mocks.initialize.mockResolvedValue({ id: "current", usage_profile: "website" });
    mount(404);
    fireEvent.click(await screen.findByRole("button", { name: "Open Academy Builder" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Current Academy editor" })).toBeNull();
  });

  it("renders the recovery in Arabic and RTL", async () => {
    const { container } = mount(404, "ar");
    expect(container.querySelector("main").dir).toBe("rtl");
    expect(await screen.findByRole("button", { name: "فتح منشئ الأكاديمية" })).toBeTruthy();
  });
});

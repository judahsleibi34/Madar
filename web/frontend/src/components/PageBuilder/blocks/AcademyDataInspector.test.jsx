import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import "../../../i18n";
import AcademyDataInspector from "./AcademyDataInspector";
import { fetchELearningSettings } from "../../../services/elearningSettings";
import { fetchAcademy } from "../../../services/elearningAcademy";
vi.mock("../../../services/elearningSettings", () => ({ fetchELearningSettings: vi.fn() }));
vi.mock("../../../services/elearningAcademy", () => ({ fetchAcademy: vi.fn() }));
afterEach(cleanup);
beforeEach(() => {
  vi.resetAllMocks();
  fetchELearningSettings.mockResolvedValue({ academy_management: { subdomain: "owner-academy" } });
  fetchAcademy.mockResolvedValue({ courses: [], plans: [], instructors: [] });
});
it("loads choices using the owner's persisted Academy address and explains an empty list", async () => {
  render(<AcademyDataInspector element={{ type: "academyPlans" }} onChange={vi.fn()} />);
  expect(await screen.findByText(/No eligible items available/)).toBeTruthy();
  expect(fetchAcademy).toHaveBeenCalledWith("owner-academy");
});
it("shows an error and retries instead of silently leaving choices empty", async () => {
  fetchAcademy.mockRejectedValueOnce(new Error("offline"));
  render(<AcademyDataInspector element={{ type: "academyCourseCollection" }} onChange={vi.fn()} />);
  expect(await screen.findByRole("alert")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText(/No eligible items available/)).toBeTruthy();
  expect(fetchAcademy).toHaveBeenCalledTimes(2);
});
it("references course IDs without copying course records into the project", async () => {
  fetchAcademy.mockResolvedValue({ courses: [{ id: "course", name: "Real course", price: 49 }] });
  const onChange = vi.fn();
  render(<AcademyDataInspector element={{ type: "academyFeaturedCourses", academy: { heading: "Featured" } }} onChange={onChange} />);
  fireEvent.click(await screen.findByRole("checkbox", { name: "Real course" }));
  expect(onChange).toHaveBeenCalledWith({ academy: { heading: "Featured", courseIds: ["course"] } });
});
it("explains public-course eligibility and selects all available course IDs", async () => {
  fetchAcademy.mockResolvedValue({ courses: [{ id: "free", name: "Free course" }, { id: "paid", name: "Paid course" }] });
  const onChange = vi.fn();
  render(<AcademyDataInspector element={{ type: "academyFeaturedCourses", academy: { courseIds: ["free"], maxItems: 4 } }} onChange={onChange} />);
  expect(screen.getByText(/Private and draft courses stay hidden/)).toBeTruthy();
  fireEvent.click(await screen.findByRole("button", { name: "Select all available courses" }));
  expect(onChange).toHaveBeenCalledWith({ academy: { courseIds: ["free", "paid"], maxItems: 4 } });
});

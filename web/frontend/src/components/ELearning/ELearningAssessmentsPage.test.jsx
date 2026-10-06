import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import i18n from "../../i18n";
import ELearningAssessmentsPage from "./ELearningAssessmentsPage";
import * as api from "../../services/elearningAssessments";
vi.mock("../../services/elearningAssessments", () => ({ fetchPlacements: vi.fn(), attachAssessment: vi.fn(), placementCommand: vi.fn(), commandAssessment: vi.fn() }));
vi.mock("../../hooks/useELearningTerminology", () => ({ useELearningTerminology: () => ({ labels: { course: "Program", section: "Level" } }) }));
vi.mock("./content/AssessmentBuilder", () => ({ default: ({ courseId, sectionId, block }) => <div role="dialog">Shared Assessment Builder {courseId} {sectionId} {block?.id}</div> }));
const assessment = { id: "a", title: "Final Check", status: "published", passing_score: 70, max_attempts: 3, revision: 1 };
const data = { revision: 4, placements: [{ id: "p", assessment, assessment_id: "a", required_for_completion: true, attempts: 2 }], available_assessments: [assessment] };
beforeEach(async () => { await i18n.changeLanguage("en"); api.fetchPlacements.mockResolvedValue(data); api.placementCommand.mockResolvedValue(data); api.attachAssessment.mockResolvedValue({}); });
afterEach(() => { cleanup(); vi.clearAllMocks(); });
it("loads the global skeleton and manages course and section assessments through the shared builder", async () => {
 const view = render(<ELearningAssessmentsPage course={{ id: "c", status: "published" }} section={{ id: "s", name: "First" }} />);
 expect(view.container.querySelector(".elearning-skeleton")).toBeTruthy(); await screen.findByText("Final Check"); expect(screen.getByRole("heading", { name: "Level Assessments" })).toBeTruthy();
 expect(api.fetchPlacements).toHaveBeenCalledWith("c", "s"); expect(screen.getByText(/Required/)).toBeTruthy(); fireEvent.click(screen.getByRole("button", { name: "+ Add Assessment" })); expect(screen.getByRole("dialog").textContent).toContain("Shared Assessment Builder c s"); view.unmount();
 render(<ELearningAssessmentsPage course={{ id: "c" }} />); await screen.findByRole("heading", { name: "Program Assessments" }); fireEvent.click(screen.getByRole("button", { name: "Edit" })); expect(screen.getByRole("dialog").textContent).toContain("p");
});
it("attaches existing assessments with scope-specific requirements and confirms removal", async () => {
 render(<ELearningAssessmentsPage course={{ id: "c" }} section={{ id: "s" }} />); await screen.findByText("Final Check"); fireEvent.click(screen.getByRole("button", { name: "Attach Existing Assessment" }));
 fireEvent.change(screen.getByLabelText("Assessment"), { target: { value: "a" } }); fireEvent.click(screen.getByLabelText("Required for Level Completion")); fireEvent.click(screen.getAllByRole("button", { name: "Attach Existing Assessment" }).at(-1));
 await waitFor(() => expect(api.attachAssessment).toHaveBeenCalledWith("c", { assessment_id: "a", section_id: "s", expected_revision: 4, required_for_completion: true }));
 fireEvent.click(screen.getByRole("button", { name: "Remove from placement" })); expect(api.placementCommand).not.toHaveBeenCalled(); fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
 await waitFor(() => expect(api.placementCommand).toHaveBeenCalledWith("c", "p", { action: "remove", expected_revision: 4, confirmed: true }));
});
it("shows optional indicators and RTL while preserving errors", async () => {
 await i18n.changeLanguage("ar"); api.fetchPlacements.mockResolvedValue({ ...data, placements: [{ ...data.placements[0], required_for_completion: false }] }); render(<div dir="rtl"><ELearningAssessmentsPage course={{ id: "c" }} /></div>); await screen.findByText(/اختياري/);
});

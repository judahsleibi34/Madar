import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "../../i18n";
import AcademyOwnerOverview from "./AcademyOwnerOverview";
import useAcademyCapabilities from "../../hooks/useAcademyCapabilities";
import { academyOwnerApi } from "./academyOwnerApi";
import { fetchELearningSettings } from "../../services/elearningSettings";
import { fetchPlans } from "../../services/elearningCommerce";
import { LearningExperienceContext } from "./LearningExperienceContext";

vi.mock("../../hooks/useAcademyCapabilities", () => ({ default: vi.fn() }));
vi.mock("./academyOwnerApi", () => ({ academyOwnerApi: vi.fn() }));
vi.mock("../../services/elearningSettings", () => ({ fetchELearningSettings: vi.fn() }));
vi.mock("../../services/elearningCommerce", () => ({ fetchPlans: vi.fn() }));

const dashboard = { total_learners: 12, active_learners: 9, purchases: 5, affiliates: 2, applications: [{ kind: "tuition", status: "submitted", count: 3 }, { kind: "tuition", status: "approved", count: 1 }], rewards: [{ currency: "USD", status: "earned", sales: 4, amount: "40" }] };
const settings = { referral_rewards_enabled: true, referral_reward_amount: "10", referral_reward_currency: "USD", minimum_withdrawal_amount: "50", tuition_sales_threshold: 4, withdrawal_methods: ["Palestinian Bank Transfer", "PayPal"], institution_enabled: true, institution_email_domains: ["paluniv.edu.ps"], institution_student_label: "PAU Student" };
const view = experience => render(<LearningExperienceContext.Provider value={experience}><MemoryRouter><AcademyOwnerOverview user={{ id: 1 }} /></MemoryRouter></LearningExperienceContext.Provider>);

beforeEach(async () => {
  await i18n.changeLanguage("en");
  useAcademyCapabilities.mockReturnValue({ capabilities: {} });
  academyOwnerApi.mockResolvedValue(dashboard);
  fetchELearningSettings.mockResolvedValue({ settings });
  fetchPlans.mockResolvedValue({ plans: [{ id: "p", name: "EduHope English Conversation Course", status: "active", billing_type: "one_time", amount: "30.00", currency: "USD" }] });
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

it("shows charts with numbers and the settings summary for opt-in academies", async () => {
  view({ studentDashboard: true });
  const charts = await screen.findByRole("region", { name: "Students and affiliates" });
  expect(within(charts).getByText("12")).toBeTruthy();
  expect(screen.getByRole("region", { name: "Tuition Support" })).toBeTruthy();
  const summary = (await screen.findByText("Course price")).closest("dl");
  for (const text of ["EduHope English Conversation Course: $30.00", "$10.00", "$50.00", "4", "Palestinian Bank Transfer · PayPal", "paluniv.edu.ps — PAU Student", "English and Arabic (Arabic right to left)"]) expect(within(summary).getByText(text)).toBeTruthy();
  expect(within(summary).getAllByRole("link", { name: "Edit" }).length).toBe(6);
});

it("leaves other academies' overview unchanged", async () => {
  view({});
  await screen.findByText("Create course");
  expect(screen.queryByText("At a glance")).toBeNull();
  expect(screen.queryByText("Course price")).toBeNull();
  expect(fetchELearningSettings).not.toHaveBeenCalled();
});

import { MemoryRouter } from "react-router-dom";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import AcademyDataBlock, { AcademyCompositionContext } from "./AcademyDataBlock";
import { ACADEMY_COMPONENT_TYPES } from "../core/PageBuilder.academyProfile";
import "../../../i18n";
afterEach(cleanup);
function renderBlock(type, data, academy = {}, editing = false) {
  const collection = vi.fn((heading, courses) => <section><h2>{heading}</h2>{courses.map(course => <p key={course.id}>{course.name}</p>)}</section>);
  const plans = vi.fn(items => <div>{items.map(plan => <p key={plan.id}>{plan.name} {plan.amount}</p>)}</div>);
  render(<MemoryRouter><AcademyCompositionContext.Provider value={{ data, renderCollection: collection, renderPlans: plans }}><AcademyDataBlock element={{ type, academy }} editing={editing} /></AcademyCompositionContext.Provider></MemoryRouter>);
  return { collection, plans };
}
it("excludes forms, bookings, embeds and auth from the Academy authoring profile", () => {
  for (const type of ["formBlock", "reservationBlock", "reservationRequest", "embed", "loginBlock", "registrationBlock"]) expect(ACADEMY_COMPONENT_TYPES.has(type)).toBe(false);
  for (const type of ["heading", "text", "image", "button", "academyFeaturedCourses", "academyCourseCollection", "academyPlans", "academyContinueLearning"]) expect(ACADEMY_COMPONENT_TYPES.has(type)).toBe(true);
});
it("never renders guest Continue Learning data even when supplied", () => {
  const { collection } = renderBlock("academyContinueLearning", { authenticated: false, continue_courses: [{ id: "private", name: "Private Course" }] });
  expect(collection).not.toHaveBeenCalled(); expect(screen.queryByText("Private Course")).toBeNull();
});

it.each([
  ["academyFeaturedCourses", /No featured courses/],
  ["academyCourseCollection", /No published catalog courses/],
  ["academyPlans", /No public plans/],
  ["academyInstructors", /No public instructors/],
  ["academyContinueLearning", /Personalized for each signed-in learner/],
])("keeps empty %s visible and configurable in the editor", (type, message) => {
  renderBlock(type, { authenticated: false, courses: [], plans: [], instructors: [], continue_courses: [] }, { heading: "My component" }, true);
  expect(screen.getByRole("heading", { name: "My component" })).toBeTruthy();
  expect(screen.getByText(message)).toBeTruthy();
});

it("does not leak editor setup states onto published pages", () => {
  renderBlock("academyPlans", { plans: [] }, { heading: "Pricing" });
  expect(screen.queryByText(/No public plans/)).toBeNull();
  expect(screen.queryByRole("heading", { name: "Pricing" })).toBeNull();
});
it("uses authorized aggregate resume data for authenticated learners", () => {
  renderBlock("academyContinueLearning", { authenticated: true, continue_courses: [{ id: "c", name: "Resume me" }] }, { heading: "Continue", maxItems: 1 });
  expect(screen.getByText("Resume me")).toBeTruthy();
});
it("filters courses by selected IDs without copying record data", () => {
  const { collection } = renderBlock("academyFeaturedCourses", { courses: [{ id: "a", name: "First", featured: true }, { id: "b", name: "Second", featured: false }] }, { courseIds: ["b"], maxItems: 1 });
  expect(collection.mock.calls[0][1]).toEqual([{ id: "b", name: "Second", featured: false }]);
});
it("uses authoritative prices for selected active plans", () => {
  renderBlock("academyPlans", { plans: [{ id: "a", name: "Plan", amount: 49 }, { id: "b", name: "Other", amount: 100 }] }, { heading: "Pricing", planIds: ["a"] });
  expect(screen.getByText("Plan 49")).toBeTruthy(); expect(screen.queryByText("Other 100")).toBeNull();
});

it("renders selected existing instructors and only projected public course context", () => {
  renderBlock("academyInstructors", { site: { subdomain: "testing" }, instructors: [{ id: "i", name: "Actual instructor", description: "Existing profile", course_ids: ["public", "private"] }, { id: "other", name: "Other", course_ids: [] }], courses: [{ id: "public", name: "Public course" }] }, { heading: "Meet instructors", instructorIds: ["i"] });
  expect(screen.getByRole("heading", { name: "Actual instructor" })).toBeTruthy();
  expect(screen.getByRole("link", { name: "Public course" }).getAttribute("href")).toBe("/academy/testing/courses/public");
  expect(screen.queryByText("Other")).toBeNull(); expect(screen.queryByText("private")).toBeNull();
});

it("hides the public contact form when Website access is unavailable", () => {
  renderBlock("academyContact", { site: { subdomain: "academy" }, contact_enabled: false });
  expect(screen.queryByRole("button")).toBeNull();
});
it("renders the published academy contact form when Website access is enabled", () => {
  renderBlock("academyContact", { site: { subdomain: "academy" }, contact_enabled: true });
  expect(screen.getByRole("button", { name: /Send/ })).toBeTruthy();
});
it("preserves the guest affiliate destination through Academy login without pointing to support", () => {
 renderBlock('academyProgrammeInfo',{authenticated:false,site:{subdomain:'testing'},programme_info:{affiliate_terms:'Academy terms'}});
 const link=screen.getByRole('link',{name:'Become an affiliate'});
 expect(new URL(link.href).searchParams.get('returnTo')).toBe('/my-learning/affiliate');
});

it('shows configured Support actions and preserves the specialized return flow',()=>{
 renderBlock('academyProgrammeInfo',{authenticated:false,site:{subdomain:'testing'},programme_info:{support_programme_name:'Learning Assistance',tuition_terms:'Terms'}});
 const link=screen.getByRole('link',{name:'Learning Assistance'});expect(new URL(link.href).searchParams.get('returnTo')).toBe('/my-learning/programmes?kind=tuition');
});
it('lets guests read public opportunity detail before the contextual Forms login',()=>{
 renderBlock('academyExchangeOpportunities',{authenticated:false,site:{subdomain:'testing'},exchange_opportunities:[{id:'own',title:'Exchange',short_description:'Summary',description:'Full public detail',requirements:'Active learner',capacity:2}]});
 expect(screen.getByText('Full public detail').closest('details')).toBeTruthy();
 expect(new URL(screen.getByRole('link',{name:'Apply'}).href).searchParams.get('returnTo')).toBe('/my-learning/exchange/own');
});

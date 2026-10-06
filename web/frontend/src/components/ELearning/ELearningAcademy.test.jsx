import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "../../i18n";
import ELearningAcademy, { AcademyBuilderPreviewProvider } from "./ELearningAcademy";
import { useContext } from "react";
import { AcademyCompositionContext } from "../PageBuilder/blocks/AcademyDataBlock";
import { fetchAcademy, registerAcademy } from "../../services/elearningAcademy";
import * as commerce from "../../services/elearningCommerce";
vi.mock("../../services/elearningAcademy", async (original) => ({ ...(await original()), fetchAcademy: vi.fn(), registerAcademy: vi.fn() }));
vi.mock("../../services/elearningCommerce", () => ({ enrollCatalogCourse: vi.fn(), fetchMyPlans: vi.fn(), createCheckout: vi.fn(), localPaymentEvent: vi.fn() }));
const plan = { id:"plan", name:"Lifetime Access", amount:49, currency:"USD", billing_type:"one_time", access_scope:"all_courses", description:"Real plan" };
const course = { id:"free", name:"English Basics", description:"Speak with confidence", access_type:"free", cta:{action:"enroll_free"}, featured:true, outline:[{name:"First level",lesson_count:2}], instructors:[{name:"Teacher"}], plans:[], progress:null, credential:null };
const data = {site:{subdomain:"tenant",brand:"Academy",theme:{},course_label:"Course",section_label:"Level",lesson_label:"Topic",instructor_label:"Coach",academy_hero_title:"Learn With Confidence",academy_benefits:"Real learning"},authenticated:false,courses:[course],plans:[]};
data.landing = { theme: {}, defaultPageId: "home", pages: [{ id: "home", slug: "/", isDefault: true, sections: [{ id: "hero", rows: [{ id: "r", columns: [{ id: "c", elements: [{ id: "title", type: "heading", content: "Learn With Confidence", styles: {}, textBlockFormats: [{ type: "h1" }] }, { id: "continue", type: "academyContinueLearning", academy: { heading: "Continue Learning" } }, { id: "featured", type: "academyFeaturedCourses", academy: { heading: "Featured Courses" } }, { id: "all", type: "academyCourseCollection", academy: { heading: "Explore Courses" } }] }] }] }] }] };
function mount(path="/academy/tenant") { return render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/academy/:subdomain/*" element={<ELearningAcademy />} /><Route path="/my-learning/*" element={<h1>Learning runtime</h1>} /></Routes></MemoryRouter>); }
beforeEach(async()=>{ await i18n.changeLanguage("en");fetchAcademy.mockResolvedValue(structuredClone(data)); });
afterEach(()=>{cleanup();vi.clearAllMocks();});
it("renders Builder hero and actual featured courses while hiding empty/account sections",async()=>{
 mount();expect(await screen.findByText("Learn With Confidence")).toBeTruthy();expect(screen.getAllByText("English Basics").length).toBe(2);
 expect(screen.queryByRole("heading",{name:"Continue Learning"})).toBeNull();expect(screen.queryByText("Choose Your Access")).toBeNull();expect(screen.queryByRole("link",{name:"My Certificates"})).toBeNull();
 await waitFor(() => expect(document.querySelector('link[rel="canonical"]')?.href).toContain('/academy/tenant'));
});
it("uses centralized learner state, stored resume target and certificate state",async()=>{
 fetchAcademy.mockResolvedValue({...data,authenticated:true,continue_courses:[{...course,cta:{action:"continue"},progress:{progress_percent:50,completion:{completed:false}},resume:"/my-learning/courses/free/lessons/second"}],courses:[{...course,cta:{action:"continue"},progress:{progress_percent:50,completion:{completed:false}},resume:"/my-learning/courses/free/lessons/second"}]});mount();
 expect(await screen.findByRole("heading",{name:"Continue Learning"})).toBeTruthy();expect(screen.getAllByRole("link",{name:"Continue Learning"})[0].getAttribute("href")).toBe('/my-learning/courses/free/lessons/second');
 expect(screen.getByRole("link",{name:"My Certificates"})).toBeTruthy();
});
it("guest enrollment routes through tenant sign in and returns to course details",async()=>{
 mount('/academy/tenant/courses/free');fireEvent.click(await screen.findByRole('button',{name:'Enroll Free'}));expect(await screen.findByRole('heading',{name:'Sign in'})).toBeTruthy();expect(commerce.enrollCatalogCourse).not.toHaveBeenCalled();
});
it("enrollment uses existing commerce API then opens the learning runtime",async()=>{
 fetchAcademy.mockResolvedValue({...data,authenticated:true});commerce.enrollCatalogCourse.mockResolvedValue({});mount('/academy/tenant/courses/free');fireEvent.click(await screen.findByRole('button',{name:'Enroll Free'}));expect(await screen.findByRole('heading',{name:'Learning runtime'})).toBeTruthy();expect(commerce.enrollCatalogCourse).toHaveBeenCalledWith('free');
});
it("shows real plan prices and keeps unconfigured live payments disabled",async()=>{
 fetchAcademy.mockResolvedValue({...data,authenticated:true,plans:[plan]});commerce.fetchMyPlans.mockResolvedValue({local_adapter:false});mount('/academy/tenant/plans');fireEvent.click(await screen.findByRole('button',{name:'Buy'}));await screen.findByRole('alert');expect(commerce.createCheckout).not.toHaveBeenCalled();expect(screen.getByText(/49.00 USD/)).toBeTruthy();
});
it("catalog searches existing metadata and renders Arabic RTL",async()=>{
 await i18n.changeLanguage('ar');mount('/academy/tenant/courses');const search=await screen.findByRole('searchbox');expect(document.querySelector('.academy').dir).toBe('rtl');fireEvent.change(search,{target:{value:'missing'}});expect(screen.queryByText('English Basics')).toBeNull();fireEvent.change(search,{target:{value:'Teacher'}});expect(screen.getByText('English Basics')).toBeTruthy();fireEvent.click(screen.getByRole('button',{name:'القائمة'}));await waitFor(()=>expect(document.querySelector('.academy-header nav').className).toBe('is-open'));
});

it("renders published Builder pages without overriding the system catalog", async () => {
 const landing = structuredClone(data.landing);
 landing.pages.push({ id: "about", name: "About", slug: "/about", sections: structuredClone(landing.pages[0].sections) });
 landing.pages[1].sections[0].rows[0].columns[0].elements = [{ id: "about-title", type: "heading", content: "About our Academy", styles: {} }];
 fetchAcademy.mockResolvedValue({ ...data, landing }); mount("/academy/tenant/about");
 expect(await screen.findByRole("heading", { name: "About our Academy" })).toBeTruthy();
 expect(screen.queryByText("Learn With Confidence")).toBeNull();
});
it("does not substitute the home page for an unknown public page", async () => {
 mount("/academy/tenant/unknown"); expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Page not found");
 expect(screen.queryByText("Learn With Confidence")).toBeNull();
});

it('clears prior tenant data while another Academy loads', async () => {
 function Probe() { const runtime = useContext(AcademyCompositionContext); return <p>{runtime?.data?.site?.brand || 'Loading current Academy'}</p>; }
 fetchAcademy.mockResolvedValueOnce({ ...data, site: { ...data.site, brand: 'Owner Alpha' } }).mockReturnValueOnce(new Promise(() => {}));
 const view = render(<AcademyBuilderPreviewProvider identifier="alpha"><Probe /></AcademyBuilderPreviewProvider>);
 expect(await screen.findByText('Owner Alpha')).toBeTruthy();
 view.rerender(<AcademyBuilderPreviewProvider identifier="beta"><Probe /></AcademyBuilderPreviewProvider>);
 expect(screen.queryByText('Owner Alpha')).toBeNull();
 expect(screen.getByText('Loading current Academy')).toBeTruthy();
});


it('allows direct domain signup without an invitation and shows verification next', async () => {
 fetchAcademy.mockResolvedValue({ ...data, site: { ...data.site, academy_registration: 'email_domain' } });
 registerAcademy.mockResolvedValue({ requires_email_verification: true });
 mount('/academy/tenant/login?register=1');
 await screen.findByRole('heading', { name: 'Create Account' });
 fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Jack' } });
 fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'jack@university.edu' } });
 fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Safe-password-123' } });
 fireEvent.click(screen.getByRole('button', { name: 'Create Account' }));
 await waitFor(() => expect(registerAcademy).toHaveBeenCalledWith('tenant', expect.objectContaining({ email: 'jack@university.edu', full_name: 'Jack' })));
 expect(await screen.findByRole('status')).toBeTruthy();
});

it('explains a rejected signup domain using the server policy', async () => {
 fetchAcademy.mockResolvedValue({ ...data, site: { ...data.site, academy_registration: 'email_domain' } });
 registerAcademy.mockRejectedValue({ code: 'academy_email_domain_not_allowed' });
 mount('/academy/tenant/login?register=1');
 await screen.findByRole('heading', { name: 'Create Account' });
 fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Jack' } });
 fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'jack@gmail.com' } });
 fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Safe-password-123' } });
 fireEvent.click(screen.getByRole('button', { name: 'Create Account' }));
 expect((await screen.findByRole('alert')).textContent).toBe('Use an email address from a domain allowed by this Academy.');
});
it("hides development seed text in the Builder preview course cards", async () => {
  fetchAcademy.mockResolvedValue({ ...structuredClone(data), courses: [{ ...course, description: "[Development seed: madar-elearning-demo-v1] Speak with confidence" }] });
  render(<MemoryRouter><AcademyBuilderPreviewProvider identifier="tenant"><Probe /></AcademyBuilderPreviewProvider></MemoryRouter>);
  function Probe() {
    const runtime = useContext(AcademyCompositionContext);
    return runtime?.data ? runtime.renderCollection("Featured Courses", runtime.data.courses) : null;
  }
  expect(await screen.findByText("Speak with confidence")).toBeTruthy();
  expect(screen.queryByText(/Development seed/)).toBeNull();
});

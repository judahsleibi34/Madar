import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter,Routes,Route } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "../../i18n";
import LearningFormRenderer from "./LearningFormRenderer";
import AcademyFormBlock from "../PageBuilder/blocks/AcademyFormBlock";
import AcademyDataInspector from "../PageBuilder/blocks/AcademyDataInspector";
import { fetchELearningSettings } from "../../services/elearningSettings";
import LearningFormEditor from "./LearningFormEditor";
import LearningFormResponseDetail from "./LearningFormResponseDetail";
import LearningFormsPage from "./LearningFormsPage";
import LearningFormResponses from "./LearningFormResponses";
import LearningFormsNavigation from "./LearningFormsNavigation";
import { learningFormsApi } from "./learningFormsApi";
import { apiFetch } from "../../utils/apiClient";
import { visibleLearningFields } from "../PageBuilder/runtime/formVisibility";
vi.mock("../../services/elearningSettings", () => ({fetchELearningSettings:vi.fn()}));
vi.mock("./learningFormsApi", () => ({learningFormsApi:vi.fn()}));
vi.mock("../../utils/apiClient", () => ({apiFetch:vi.fn(),getApiUrl:path => path}));
beforeEach(async () => {await i18n.changeLanguage("en");learningFormsApi.mockReset();apiFetch.mockReset();});
afterEach(cleanup);
const schema = {title:"Scholarship feedback",access:"public",pageMode:"single",sections:[{id:"p",title:"Questions",fields:[{id:"student",type:"radio",label:"Student?",options:["Yes","No"],required:true},{id:"university",type:"shortText",label:"University",required:true}]}],logicRules:[{sourceFieldId:"student",targetFieldId:"university",operator:"equals",action:"show",value:"Yes"}]};
const mount = element => render(<MemoryRouter>{element}</MemoryRouter>);
it("shows guests every question of a sign-in form and sends them to Academy login to apply", async () => {
 apiFetch.mockResolvedValue({ok:true,status:200,json:async()=>({id:"own",version:1,requires_sign_in:true,schema:{...schema,access:"authenticated"}})});
 render(<MemoryRouter initialEntries={["/academy/tenant/exchange"]}><AcademyFormBlock formId="own" identifier="tenant" /></MemoryRouter>);
 expect(await screen.findByText("Student? *")).toBeTruthy();
 expect(screen.getByLabelText("Yes")).toBeTruthy();
 expect(screen.queryByRole("button",{name:"Submit"})).toBeNull();
 const apply = screen.getByRole("link",{name:"Log in to apply"});
 expect(new URL(apply.href).searchParams.get("returnTo")).toBe("/academy/tenant/exchange");
 expect(document.querySelector("fieldset").disabled).toBe(true);
});
it("shows ineligible learners the form with an accurate reason and English base text", async () => {
 const description = {description:"Your information is private.",localized:{description:{ar:"معلوماتك خاصة."}}};
 apiFetch.mockResolvedValue({ok:true,status:200,json:async()=>({id:"own",version:1,requires_sign_in:false,locked_reason:"eligibility",schema:{...schema,...description,access:"authenticated"}})});
 render(<MemoryRouter initialEntries={["/academy/tenant/exchange"]}><AcademyFormBlock formId="own" identifier="tenant" /></MemoryRouter>);
 expect(await screen.findByText("Your information is private.")).toBeTruthy();
 expect(screen.queryByText("معلوماتك خاصة.")).toBeNull();
 expect(screen.getByText(/open to active learners only/)).toBeTruthy();
 expect(screen.getByRole("link",{name:"Explore courses"}).getAttribute("href")).toBe("/academy/tenant/courses");
 expect(screen.queryByRole("button",{name:"Submit"})).toBeNull();
 expect(screen.queryByText("Tuition Support locked")).toBeNull();
});
it("recovers a signed-in form through Academy login while preserving its contextual page", async () => {
 apiFetch.mockResolvedValue({ok:false,status:401});
 render(<MemoryRouter initialEntries={["/academy/tenant/survey?campaign=learning"]}><AcademyFormBlock formId="own" identifier="tenant" /></MemoryRouter>);
 const login = await screen.findByRole("link",{name:"Log in"});
 const url = new URL(login.href);
 expect(url.pathname).toBe("/academy/tenant/login");
 expect(url.searchParams.get("returnTo")).toBe("/academy/tenant/survey?campaign=learning");
});
it("conditionally renders fields and omits hidden answers from independent submission", async () => {
  apiFetch.mockResolvedValue({ok:true});mount(<LearningFormRenderer form={{id:"form",version:2,schema}} identifier="academy" />);
  expect(screen.queryByLabelText(/University/)).toBeNull();fireEvent.click(screen.getByLabelText("Yes"));fireEvent.change(screen.getByLabelText(/University/),{target:{value:"Hidden later"}});fireEvent.click(screen.getByLabelText("No"));fireEvent.click(screen.getByRole("button",{name:"Submit"}));
  await waitFor(() => expect(apiFetch).toHaveBeenCalled());const [path,options] = apiFetch.mock.calls[0];expect(path).toBe("/public/academies/academy/forms/form/responses");expect(JSON.parse(options.body.get("payload"))).toMatchObject({version:2,answers:{student:"No"}});
});
it("requires visible fields and keeps preview inert", () => {
  mount(<LearningFormRenderer form={{id:"form",version:1,schema}} preview />);fireEvent.click(screen.getByLabelText("Yes"));expect(screen.getByLabelText(/University/)).toBeTruthy();expect(screen.getByRole("button",{name:"Submit"}).disabled).toBe(true);expect(apiFetch).not.toHaveBeenCalled();
});
it.each([[false,[]],[true,[{id:"f",name:"Feedback",status:"active"}]],[true,[{id:"f",name:"Historical survey",status:"archived"}]]])("forms navigation honors usage visibility without listing individual forms %s", (visible,items) => {
 mount(<LearningFormsNavigation forms={{visible,items}} />);if (!visible) expect(screen.queryByText("Forms")).toBeNull();else {expect(screen.queryByText(items[0].name,{exact:false})).toBeNull();expect(screen.getByRole("link",{name:"Form submissions"})).toBeTruthy();}
});
it("inactive form with historical responses remains navigable", () => {
 mount(<LearningFormsNavigation forms={{visible:true,items:[{id:"old",name:"Old form",status:"inactive",responses:1}]}} />);expect(screen.queryByRole("link",{name:"Old form"})).toBeNull();expect(screen.getByRole("link",{name:"Form submissions"}).getAttribute("href")).toBe("/e-learning/forms/responses");
});
it("does not let a hidden source influence a later condition", () => {
 const s={...schema,sections:[{...schema.sections[0],fields:[...schema.sections[0].fields,{id:"year",type:"shortText",label:"Year"}]}],logicRules:[...schema.logicRules,{sourceFieldId:"university",targetFieldId:"year",action:"show",value:"Hidden"}]};expect(visibleLearningFields(s,{student:"No",university:"Hidden"}).map(f => f.id)).toEqual(["student"]);
});
it("owner editor creates an independent inactive definition with pure field IDs", async () => {
 learningFormsApi.mockImplementation(async (path,options) => options ? {...options.body,id:"f",version:1} : {items:[]});mount(<LearningFormEditor />);fireEvent.change(screen.getByLabelText("Form name"),{target:{value:"Feedback"}});fireEvent.change(screen.getByLabelText("Form title"),{target:{value:"Feedback"}});fireEvent.click(screen.getByRole("button",{name:"Save form"}));await waitFor(() => expect(learningFormsApi).toHaveBeenCalledWith("",expect.objectContaining({method:"POST",body:expect.objectContaining({name:"Feedback",status:"inactive",schema:expect.objectContaining({sections:expect.any(Array)})})})));
});
it("historical responses use their version title and field labels", async () => {
 learningFormsApi.mockImplementation(async path => path === "" ? {items:[{id:"f",name:"Current name"}]} : path === "/responses/r" ? {id:"r",version:1,submitted_at:"2026-10-11",answers:{student:"No"},owner_notes:"",files:[],definition:{schema}} : {items:[{id:"r",form_id:"f",version:1,submitted_at:"2026-10-11"}],has_more:false});render(<MemoryRouter initialEntries={["/e-learning/forms/responses/r"]}><Routes><Route path="/e-learning/forms/responses/:responseId" element={<LearningFormResponseDetail/>}/></Routes></MemoryRouter>);expect(await screen.findByText("Scholarship feedback")).toBeTruthy();expect(screen.getByText(/Version 1/)).toBeTruthy();expect(screen.getByText("Student?")).toBeTruthy();expect(screen.getByText("No")).toBeTruthy();
});

it("Academy Builder selects a learning form ID without copying its definition", async () => {
 fetchELearningSettings.mockResolvedValue({academy_management:{subdomain:"academy"}});learningFormsApi.mockResolvedValue({items:[{id:"own",name:"Feedback",status:"active",schema},{id:"archived",name:"Old survey",status:"archived"}]});const change=vi.fn();mount(<AcademyDataInspector element={{type:"academyForm",academy:{}}} onChange={change} />);await screen.findByRole("option",{name:"Feedback"});expect(screen.queryByRole("option",{name:"Old survey"})).toBeNull();fireEvent.change(screen.getByRole("combobox"),{target:{value:"own"}});expect(change).toHaveBeenCalledWith({academy:{formId:"own"}});
});
it("Academy Builder previews its independent definition with no public submission", async () => {
 learningFormsApi.mockResolvedValue({id:"own",version:1,schema});mount(<AcademyFormBlock formId="own" identifier="academy" editing />);expect((await screen.findByRole("button",{name:"Submit"})).disabled).toBe(true);expect(learningFormsApi).toHaveBeenCalledWith("/own");expect(apiFetch).not.toHaveBeenCalled();
});
it("published Academy Form renders through the bound learning endpoint", async () => {
 apiFetch.mockResolvedValue({ok:true,json:async () => ({id:"own",version:1,schema})});mount(<AcademyFormBlock formId="own" identifier="academy" editing={false} />);await screen.findByLabelText("Yes");expect(apiFetch).toHaveBeenCalledWith("/public/academies/academy/forms/own",expect.objectContaining({cache:"no-store"}));expect(learningFormsApi).not.toHaveBeenCalled();
});

it("manage forms has a create route and no embedded editor", async()=>{learningFormsApi.mockResolvedValue({items:[]});mount(<LearningFormsPage/>);expect(await screen.findByText("No forms yet")).toBeTruthy();expect(screen.getAllByRole("link",{name:"Create form"})[0].getAttribute("href")).toBe("/e-learning/forms/new");expect(screen.queryByLabelText("Form name")).toBeNull();});
it("submissions table links to review while displaying the structured answers", async()=>{learningFormsApi.mockImplementation(async path => path === "/responses/r" ? {definition:{name:"Feedback",schema}} : {items:[{id:"r",form_id:"f",version:1,answers:{student:"Yes"},submitted_at:"2026-10-11"}]});mount(<LearningFormResponses/>);expect((await screen.findByRole("link",{name:"Open"})).getAttribute("href")).toBe("/e-learning/forms/responses/r");expect(screen.getByRole("columnheader",{name:"Student?"})).toBeTruthy();expect(screen.getByRole("cell",{name:"Yes"})).toBeTruthy();});
it("Builder zero-form state offers the safe create/return route", async()=>{fetchELearningSettings.mockResolvedValue({academy_management:{subdomain:"academy"}});learningFormsApi.mockResolvedValue({items:[]});mount(<AcademyDataInspector element={{type:"academyForm"}} onChange={vi.fn()}/>);expect(await screen.findByText("No forms yet")).toBeTruthy();expect(screen.getByRole("link",{name:"Create form"}).getAttribute("href")).toContain("/e-learning/forms/new?returnTo=");});
it("keeps sidebar destinations fixed even with many forms",()=>{mount(<LearningFormsNavigation discover forms={{visible:false,items:Array.from({length:20},(_,i)=>({id:String(i),name:`Form ${i}`}))}}/>);expect(screen.getAllByRole("link").filter(link=>link.getAttribute("href").includes("form_id="))).toHaveLength(0);expect(screen.getAllByRole("link")).toHaveLength(2);expect(screen.queryByRole("link",{name:"View all forms"})).toBeNull();});

it('does not turn a failed edit lookup into creation of a new form',async()=>{learningFormsApi.mockRejectedValue(new Error('offline'));render(<MemoryRouter initialEntries={['/e-learning/forms/existing/edit']}><Routes><Route path='/e-learning/forms/:id/edit' element={<LearningFormEditor/>}/></Routes></MemoryRouter>);await screen.findByRole('alert');expect(screen.queryByRole('button',{name:'Save form'})).toBeNull();expect(screen.queryByLabelText('Form name')).toBeNull();});

it('shows Arabic field validation without exposing English renderer messages',async()=>{await i18n.changeLanguage('ar');mount(<LearningFormRenderer form={{id:'form',version:1,schema}}/>);fireEvent.click(screen.getByRole('button',{name:i18n.t('elearning.forms.submit',{ns:'dashboard'})}));expect(screen.getByRole('alert').textContent).toContain('تحقق من إجابة');expect(apiFetch).not.toHaveBeenCalled();});

it('recovers an expired submission session without losing answers or changing the retry key',async()=>{
 apiFetch.mockResolvedValueOnce({ok:true,json:async()=>({id:'own',version:1,schema})}).mockResolvedValueOnce({ok:false,status:401}).mockResolvedValueOnce({ok:true});
 render(<MemoryRouter initialEntries={['/academy/tenant/survey?campaign=learning#form']}><AcademyFormBlock formId="own" identifier="tenant" /></MemoryRouter>);
 fireEvent.click(await screen.findByLabelText('No'));fireEvent.click(screen.getByRole('button',{name:'Submit'}));
 const link=await screen.findByRole('link',{name:'Log in'});expect(new URL(link.href).searchParams.get('returnTo')).toBe('/academy/tenant/survey?campaign=learning#form');
 expect(screen.getByLabelText('No').checked).toBe(true);
 const first=JSON.parse(apiFetch.mock.calls[1][1].body.get('payload'));
 fireEvent.click(screen.getByRole('button',{name:'Submit'}));await screen.findByText('Your response was received.');
 const second=JSON.parse(apiFetch.mock.calls[2][1].body.get('payload'));expect(second).toEqual(first);
});

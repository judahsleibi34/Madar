import { cleanup, fireEvent, render, screen, within, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import i18n from "../../i18n";
import ELearningRelationshipsPage from "./ELearningRelationshipsPage";
import ELearningLearnersPage from "./ELearningLearnersPage";
import * as api from "../../services/elearningRelationships";
import { fetchCourseEnrollments, changeEnrollmentStatus } from "../../services/elearningParticipation";
vi.mock("../../services/elearningRelationships",()=>({fetchRelationships:vi.fn(),changeRelationship:vi.fn(),fetchRelationshipCandidates:vi.fn()}));
vi.mock("../../services/elearningParticipation",()=>({fetchCourseEnrollments:vi.fn(),changeEnrollmentStatus:vi.fn()}));
vi.mock("../../hooks/useELearningTerminology",()=>({useELearningTerminology:()=>({labels:{group:"Cohort",course:"Program",instructor:"Trainer",lesson:"Topic",section:"Level",plural:{group:"Cohorts",course:"Programs",instructor:"Trainers",lesson:"Topics",section:"Levels"}}})}));
const data={entity:{id:"g",name:"English Cohort",status:"active"},members:[{id:4,name:"Ahmed",email:"a@example.com",membership_status:"active"}],member_count:1,courses:[{id:"c",name:"English",learner_count:1,average_progress:50,completed_count:0}],groups:[],instructors:[]};
function page(tab="members",kind="group"){return render(<MemoryRouter initialEntries={[`/groups/g/${tab}`]}><Routes><Route path="/groups/:itemId/:tab" element={<ELearningRelationshipsPage kind={kind}/>} /></Routes></MemoryRouter>);}
beforeEach(async()=>{await i18n.changeLanguage("en");api.fetchRelationships.mockResolvedValue(data);api.changeRelationship.mockResolvedValue(data);api.fetchRelationshipCandidates.mockResolvedValue({items:[{id:4,name:"Ahmed"},{id:5,name:"Sarah"}],has_more:false});});afterEach(()=>{cleanup();vi.resetAllMocks();});
it("shows existing members, uses saved labels and bulk adds existing users",async()=>{
 page();await screen.findByText("Ahmed");fireEvent.click(screen.getByRole("button",{name:"Add Members to Cohort"}));const dialog=within(screen.getByRole("dialog"));await dialog.findByText("Sarah");expect(dialog.getAllByRole("checkbox")[0].disabled).toBe(true);fireEvent.click(dialog.getAllByRole("checkbox")[1]);fireEvent.click(dialog.getByRole("button",{name:"Save"}));await waitFor(()=>expect(api.changeRelationship).toHaveBeenCalledWith("group","g",{action:"add_members",user_ids:[5]}));
});
it("confirms removing only a group member source and preserves cancellation",async()=>{
 page();fireEvent.click(await screen.findByRole("button",{name:"Remove Member"}));expect(screen.getByRole("dialog").textContent).toContain("Other Manual, Free, or Group grants will remain");expect(api.changeRelationship).not.toHaveBeenCalled();fireEvent.click(within(screen.getByRole("dialog")).getByRole("button",{name:"Cancel"}));fireEvent.click(screen.getByRole("button",{name:"Remove Member"}));fireEvent.click(within(screen.getByRole("dialog")).getByRole("button",{name:"Confirm Removal"}));await waitFor(()=>expect(api.changeRelationship).toHaveBeenCalledWith("group","g",{action:"remove_member",target_id:undefined,user_ids:[4],confirmed:true}));
});
it("shows group course progress and confirms assignment removal",async()=>{
 page("courses");await screen.findByText("English");expect(screen.getByText(/50% average/)).toBeTruthy();fireEvent.click(screen.getByRole("button",{name:"Remove Program"}));fireEvent.click(within(screen.getByRole("dialog")).getByRole("button",{name:"Confirm Removal"}));await waitFor(()=>expect(api.changeRelationship).toHaveBeenCalledWith("group","g",{action:"remove_course",target_id:"c",user_ids:undefined,confirmed:true}));
});
it("assigns instructors with a separate command and supports RTL",async()=>{
 await i18n.changeLanguage("ar");const {container}=page("instructors");api.fetchRelationshipCandidates.mockResolvedValue({items:[{id:"i",name:"Sarah"}],has_more:false});fireEvent.click(await screen.findByRole("button",{name:"تعيين Trainer"}));const dialog=within(screen.getByRole("dialog"));await dialog.findByText("Sarah");fireEvent.click(dialog.getByRole("checkbox"));fireEvent.click(dialog.getByRole("button",{name:"حفظ"}));await waitFor(()=>expect(api.changeRelationship).toHaveBeenCalledWith("group","g",{action:"assign_instructor",target_id:"i"}));expect(container.querySelector("main").getAttribute("dir")).toBe("rtl");
});
it("course learners show additive sources and revoke only Manual",async()=>{
 fetchCourseEnrollments.mockResolvedValue({enrollments:[{id:"e",name:"Ahmed",email:"a@example.com",enrollment_status:"active",learner_status:"active",effective_access:true,access_sources:[{type:"manual"},{type:"group",group_id:"g",group_name:"English Cohort"}],sections:[],progress_percent:50,completed_lessons:1,total_lessons:2,progress_status:"active"}],learner_count:1});
 render(<MemoryRouter><ELearningLearnersPage course={{id:"c",status:"published"}} /></MemoryRouter>);await screen.findByText("Manual + Group");expect(screen.getByText("1 / 2 Topics completed")).toBeTruthy();const actions=screen.getByLabelText("Actions for Ahmed").closest("details");actions.open=true;fireEvent.click(within(actions).getByRole("button",{name:"Remove Manual Access"}));fireEvent.click(within(screen.getByRole("dialog")).getByRole("button",{name:"Remove Manual Access"}));await waitFor(()=>expect(api.changeRelationship).toHaveBeenCalledWith("course","c",{action:"revoke_manual",target_id:"e",confirmed:true}));expect(changeEnrollmentStatus).not.toHaveBeenCalled();expect(screen.queryByRole("button",{name:"Cancel Enrollment"})).toBeNull();
});

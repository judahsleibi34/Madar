import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import i18n from "../../i18n";
import { AcademyLearningPerformance, AcademyFinanceSummary, AcademyRecentActivity } from "./AcademyOverviewSections";
beforeEach(async()=>{await i18n.changeLanguage("en");});
afterEach(cleanup);
const mount=node=>render(<MemoryRouter>{node}</MemoryRouter>);
it("shows no assessment data rather than a misleading zero percent pass rate",()=>{
 mount(<AcademyLearningPerformance progress={{completed_courses:5,attempts:0,average_score:0,pass_rate:0}} />);
 expect(screen.getByText("Completed enrollments")).toBeTruthy();
 expect(screen.getByText("5")).toBeTruthy();
 expect(screen.queryByText("0%")).toBeNull();
 expect(screen.getAllByText("No submitted assessments yet")).toHaveLength(2);
 expect(screen.getByRole("link",{name:"View learner reports"}).getAttribute("href")).toBe("/e-learning/reports");
});
it("preserves actual zero percent results when submitted attempts exist",()=>{
 mount(<AcademyLearningPerformance progress={{attempts:3,average_score:25,pass_rate:0}} />);
 expect(screen.getByText("0%")).toBeTruthy();expect(screen.getByText("25%")).toBeTruthy();
 expect(screen.queryByText("No submitted assessments yet")).toBeNull();
});
it("keeps each currency and reservation separate in academy finance totals",()=>{
 mount(<AcademyFinanceSummary data={{wallets:[{currency:"USD",available:"10",pending:"5"},{currency:"EUR",available:"20",pending:"0"}]}} capabilities={{}} />);
 const table=screen.getByRole("table",{name:"Learner reward balances"});
 const usd=within(table).getByRole("rowheader",{name:"USD"}).closest("tr");
 expect(within(usd).getByText("$10.00")).toBeTruthy();expect(within(usd).getByText("$5.00")).toBeTruthy();
 expect(screen.getByRole("rowheader",{name:"EUR"})).toBeTruthy();expect(screen.queryByRole("link")).toBeNull();
});
it("does not invent financial sections or activity detail missing from the API",()=>{
 const view=mount(<><AcademyFinanceSummary data={{}} /><AcademyRecentActivity events={[{event_type:"learning_topic_completed",created_at:"2026-10-12T10:00:00Z"}]} canReport={false} /></>);
 expect(screen.queryByText("Programme finances")).toBeNull();
 expect(screen.getByRole("table",{name:"Recent academy learning events"})).toBeTruthy();
 expect(screen.getByRole("cell",{name:"Learning material completed"})).toBeTruthy();
 expect(view.container.querySelector('time')?.getAttribute('dateTime')).toBe("2026-10-12T10:00:00Z");
 expect(screen.queryByRole("link")).toBeNull();
});

// Development-only gallery (localhost:5173/__eh-components/student): every
// EduHope student dashboard screen with sample data, for visual checks in English
// and Arabic. Never bundled in production (see appMain.jsx).
import { useTranslation } from "react-i18next";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { LearningExperienceContext } from "../components/ELearning/LearningExperienceContext";
import { StudentDataContext } from "../components/ELearning/student/StudentDataContext";
import StudentOverview from "../components/ELearning/student/StudentOverview";
import StudentCourse from "../components/ELearning/student/StudentCourse";
import StudentExams from "../components/ELearning/student/StudentExams";
import StudentReferral from "../components/ELearning/student/StudentReferral";
import StudentApplications from "../components/ELearning/student/StudentApplications";
import { StudentWallet, StudentWithdraw } from "../components/ELearning/student/StudentWallet";
import AffiliateArea from "../components/ELearning/student/AffiliateArea";
import "../styles/admin/dashboard/elearning-player.css";

const THEME = { "--theme-primary": "#002A60", "--theme-accent": "#088848", "--theme-surface": "#FFFFFF", "--theme-background": "#F6F7F4", "--theme-border": "#D9E3DF", "--theme-text": "#002A60", "--theme-text-soft": "#43576B" };
const TITLES = ["Getting Started", "Everyday Life", "Social Conversations", "Practical Situations", "Expressing Opinions", "Work and Study", "Professional Communication", "Advanced Conversations", "Fluency and Confidence", "Mastery"];
const sections = TITLES.map((title, index) => ({
  id: `s${index + 1}`, name: `Level ${index + 1} — ${title}`, progress_percent: index === 0 ? 100 : index === 1 ? 40 : 0,
  lessons: Array.from({ length: index === 0 ? 8 : 9 }, (_, n) => ({ id: `l${index}-${n}`, name: `Topic ${n + 1}`, completed: index === 0 || (index === 1 && n < 4), locked: index > 2 || (index === 1 && n > 4) })),
}));
const course = { course: { id: "c", name: "EduHope English Conversation Course" }, sections, continue_lesson_id: "l1-4",
  assessments: [{ placement_id: "e1", section_id: "s1", title: "A1 Final Exam", passed: true, best_score: 86, attempts: 1, locked: false }, { placement_id: "e2", section_id: "s2", title: "A2 Final Exam", locked: true, attempts: 0 }] };
const enrolled = { course: course.course, progress: { progress_percent: 13, completed_lessons: 12, total_lessons: 89 } };
const academy = { subdomain: "aooloo", brand: "EduHope", institution: { member: true, label: "PAU Student", name: "Palestine Ahliya University" } };
const history = [
  { id: "r1", amount: "10", currency: "USD", status: "earned", created_at: "2026-09-01", earned_at: "2026-09-05" },
  { id: "r2", amount: "10", currency: "USD", status: "earned", created_at: "2026-09-10", earned_at: "2026-09-14" },
  { id: "r3", amount: "10", currency: "USD", status: "reversed", created_at: "2026-09-12", reversed_at: "2026-09-16" },
  { id: "r4", amount: "10", currency: "USD", status: "pending", created_at: "2026-10-01" },
];
const referrals = { available: true, enabled: true, code: "EH7Q2K", reward_amount: "10", currency: "USD", history, balances: [], referred_count: 4, earned_count: 2 };
const programmes = (available, extra = {}) => ({
  capabilities: { affiliate: true, tuition: true, exchange: true, withdrawal: true, wallet: true },
  settings: { affiliates_enabled: true, tuition_support_enabled: true, exchange_programme_enabled: true, withdrawals_enabled: true, minimum_withdrawal_amount: "50", withdrawal_methods: ["Palestinian Bank Transfer", "PayPal"] },
  wallet: { currency: "USD", available, pending: "0", total_earned: "20", total_withdrawn: "0", debt: "0", verified_sales: 2, threshold: 4, remaining_sales: 2, tuition_eligible: false },
  applications: [{ id: "x1", kind: "exchange", status: "under_review", created_at: "2026-09-20" }], withdrawals: [], ...extra,
});
const base = { learning: { academy, courses: [enrolled] }, enrolled, course, referrals, programmes: programmes("20"),
  credentials: [{ id: "cr1", status: "active", final_score: 86, snapshot: { cefr_level: "A1" } }] };
const SCREENS = [
  ["overview", "EH / Student Overview (PAU)", "/my-learning/dashboard", <StudentOverview />, base],
  ["course", "EH / My Course", "/my-learning/course", <StudentCourse />, base],
  ["level", "EH / Level detail", "/my-learning/course/levels/s2", <StudentCourse />, base],
  ["exams", "EH / Exams & Certificates", "/my-learning/exams", <StudentExams />, base],
  ["referral", "EH / My Referral — purchased", "/my-learning/referral", <StudentReferral />, base],
  ["invite", "EH / My Referral — not purchased", "/my-learning/referral", <StudentReferral />, { ...base, learning: { academy, courses: [] }, enrolled: null, referrals: { ...referrals, code: null } }],
  ["wallet", "EH / Wallet", "/my-learning/wallet", <StudentWallet />, base],
  ["withdraw-low", "EH / Withdraw — below minimum", "/my-learning/withdraw", <StudentWithdraw />, base],
  ["withdraw-ok", "EH / Withdraw — eligible", "/my-learning/withdraw", <StudentWithdraw />, { ...base, programmes: programmes("60", { withdrawals: [{ id: "4f1c9a2e-0000", amount: "50", currency: "USD", status: "processing", created_at: "2026-10-02" }] }) }],
  ["applications", "EH / Applications", "/my-learning/applications", <StudentApplications />, base],
  ["applications-eligible", "EH / Applications — eligible", "/my-learning/applications", <StudentApplications />, { ...base, programmes: programmes("20", { wallet: { ...programmes("20").wallet, verified_sales: 4, remaining_sales: 0, tuition_eligible: true } }) }],
];
const affiliate = status => ({ ...base, learning: { academy, courses: [] }, enrolled: null, course: null, programmes: programmes("60", { applications: [{ id: "af", kind: "affiliate", status, created_at: "2026-08-01" }] }) });
SCREENS.push(
  ["affiliate", "EH / Affiliate Dashboard", "/my-learning/affiliate", <AffiliateArea />, affiliate("approved")],
  ["affiliate-link", "EH / Affiliate — Referral Link", "/my-learning/affiliate/link", <AffiliateArea />, affiliate("approved")],
  ["affiliate-sales", "EH / Affiliate — Sales", "/my-learning/affiliate/sales", <AffiliateArea />, affiliate("approved")],
  ["affiliate-review", "EH / Affiliate — Under Review", "/my-learning/affiliate", <AffiliateArea />, affiliate("under_review")],
  ["affiliate-suspended", "EH / Affiliate — Suspended", "/my-learning/affiliate", <AffiliateArea />, affiliate("suspended")],
);

export default function StudentGallery() {
  const { i18n } = useTranslation("dashboard");
  return <LearningExperienceContext.Provider value={{ lessonComponents: true, studentDashboard: true }}>
    <main className="elearning-player" dir={i18n.dir()} lang={i18n.language} style={{ ...THEME, background: "var(--theme-background)", color: "var(--theme-text)", minHeight: "100vh", padding: "24px 16px", fontFamily: "Inter, system-ui, sans-serif" }}>
      <header style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center", justifyContent: "space-between", maxWidth: 1120, margin: "0 auto 24px" }}>
        <h1 style={{ margin: 0, fontSize: 24 }}>EH student dashboard gallery</h1>
        <button type="button" onClick={() => i18n.changeLanguage(i18n.language.startsWith("ar") ? "en" : "ar")} style={{ minHeight: 44, padding: "0 16px" }}>English | العربية</button>
      </header>
      <div style={{ display: "grid", gap: 40, maxWidth: 1120, margin: "0 auto" }}>
        {SCREENS.map(([id, title, path, element, data]) => <section key={id} id={id} data-gallery-section style={{ display: "grid", gap: 14, paddingTop: 16, borderTop: "3px dashed var(--theme-border)" }}>
          <h2 style={{ margin: 0, fontSize: 14, color: "var(--theme-text-soft)" }}>{title}</h2>
          <StudentDataContext.Provider value={data}><MemoryRouter initialEntries={[path]}><Routes><Route path="/my-learning/course/levels/:sectionId" element={element} /><Route path="/my-learning/affiliate/*" element={element} /><Route path="*" element={element} /></Routes></MemoryRouter></StudentDataContext.Provider>
        </section>)}
      </div>
    </main>
  </LearningExperienceContext.Provider>;
}

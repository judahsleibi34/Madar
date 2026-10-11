import LoadingBar from "../common/LoadingBar";
import { useTranslation } from "react-i18next";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import ELearningTerminologyProvider from "./ELearningTerminologyProvider";
import AcademyLandingPageEntry from "./AcademyLandingPageEntry";
import AcademyManagementHub from "./AcademyManagementHub";
import AcademyOwnerOverview from "./AcademyOwnerOverview";
import AcademyExchangeOpportunities from "./AcademyExchangeOpportunities";
import { lazy, Suspense } from "react";
const AssessmentReviews = lazy(() => import("./AssessmentReviews"));
const LearningFormsPage = lazy(() => import("./LearningFormsPage"));
const LearningFormEditor = lazy(() => import("./LearningFormEditor"));
const LearningFormResponseDetail = lazy(() => import("./LearningFormResponseDetail"));
const AcademyProgrammeOwner = lazy(() => import("./AcademyProgrammeOwner"));
const LearningFormResponses = lazy(() => import("./LearningFormResponses"));
import AcademyContactInbox from "./AcademyContactInbox";
import useAcademyCapabilities from "../../hooks/useAcademyCapabilities";
import AcademyStudentsPage from "./AcademyStudentsPage";
import AcademyFinancePage from "./AcademyFinancePage";
import AcademyReportsPage from "./AcademyReportsPage";
import AcademyProgrammesPage from "./AcademyProgrammesPage";
import AcademyThemePage from "./AcademyThemePage";
import ELearningSettingsPage from "../DashboardBuilder/ELearningSettingsPage";
import ELearningCoursesPage from "./ELearningCoursesPage";
import ELearningCoursePage from "./ELearningCoursePage";
import ELearningDirectoryPage from "./ELearningDirectoryPage";
import ELearningRelationshipsPage from "./ELearningRelationshipsPage";
import ELearningLessonPage from "./ELearningLessonPage";
import ELearningPlansPage from "./ELearningPlansPage";
import "../../styles/admin/dashboard/elearning-management.css";
import "../../styles/admin/dashboard/elearning-owner.css";

function ProgrammeRoute({user}) { const { kind,applicationId } = useParams(); return ["affiliate","tuition","exchange"].includes(kind)?<CapabilityRoute user={user} capability={kind}><AcademyProgrammesPage key={`${kind}:${applicationId}`} admin initialKind={kind} responseId={applicationId}/></CapabilityRoute>:<Navigate to="/e-learning/dashboard" replace/>; }

function FormEditorRoute() { const { id } = useParams(); return <LearningFormEditor key={id} />; }
function FormResponseRoute() { const { responseId } = useParams(); return <LearningFormResponseDetail key={responseId} />; }
function OpportunityEditorRoute() { const { id } = useParams(); return <AcademyExchangeOpportunities editing key={id} />; }
function ContactDetailRoute() { const { contactId } = useParams(); return <AcademyContactInbox detail key={contactId} />; }
function WithdrawalDetailRoute() { const { applicationId } = useParams(); return <AcademyProgrammeOwner kind="withdrawal" key={applicationId} />; }

function AffiliateMemberRoute(){const {userId}=useParams();return <AcademyProgrammeOwner memberId={userId}/>;}

function FinanceRoute({user}) { const { kind } = useParams(); return ["referrals","rewards","transactions"].includes(kind)?<CapabilityRoute user={user} capability={kind}><AcademyFinancePage key={kind} kind={kind}/></CapabilityRoute>:<Navigate to="/e-learning/dashboard" replace/>; }

function CourseRoute() {
  const { courseId } = useParams();
  return <ELearningCoursePage key={courseId} />;
}

function LessonRoute() {
  const { courseId, lessonId } = useParams();
  return <ELearningLessonPage key={`${courseId}:${lessonId}`} />;
}

function CapabilityRoute({ user, capability, children }) {
  const access = useAcademyCapabilities(user);
  const { t } = useTranslation("dashboard");
  if(access===undefined)return <LoadingBar mode="inline" label={t("elearning.loading")}/>;
  return access?.can_manage && access.capabilities[capability] ? children : <p role="status">{t("elearning.owner.access_unavailable")}</p>;
}

export default function ELearningWorkspace({ user }) {
  const { t } = useTranslation("dashboard");
  const formsElement = node => <CapabilityRoute user={user} capability="forms"><Suspense fallback={<p role="status">{t("elearning.forms.loading")}</p>}>{node}</Suspense></CapabilityRoute>;
  const ownerElement = (capability,node) => <CapabilityRoute user={user} capability={capability}><Suspense fallback={<p role="status">{t("elearning.loading")}</p>}>{node}</Suspense></CapabilityRoute>;
  return <div className="elearning-owner"><ELearningTerminologyProvider key={`${user?.tenant_id}:${user?.id}`}>
    <Routes>
      <Route path="forms/new" element={formsElement(<LearningFormEditor key="new" />)} />
      <Route path="forms/:id/edit" element={formsElement(<FormEditorRoute />)} />
      <Route path="forms/responses/:responseId" element={formsElement(<FormResponseRoute />)} />
      <Route path="forms" element={<CapabilityRoute user={user} capability="forms"><Suspense fallback={<p role="status">{t("elearning.forms.loading")}</p>}><LearningFormsPage /></Suspense></CapabilityRoute>} />
      <Route path="assessment-reviews" element={<Suspense fallback={<p role="status">{t("elearning.assessment.loading")}</p>}><AssessmentReviews /></Suspense>} />
      <Route path="forms/responses" element={<CapabilityRoute user={user} capability="forms"><Suspense fallback={<p role="status">{t("elearning.forms.loading")}</p>}><LearningFormResponses user={user} /></Suspense></CapabilityRoute>} />
      <Route path="dashboard" element={<AcademyOwnerOverview user={user} />} />
      <Route path="exchange-opportunities/new" element={ownerElement("exchange",<AcademyExchangeOpportunities editing key="new" />)} />
      <Route path="exchange-opportunities/:id/edit" element={ownerElement("exchange",<OpportunityEditorRoute />)} />
      <Route path="affiliates" element={ownerElement("affiliate",<AcademyProgrammeOwner directory />)} />
      <Route path="affiliates/members/:userId" element={ownerElement("affiliate",<AffiliateMemberRoute />)} />
      <Route path="finance/withdrawals" element={ownerElement("withdrawal",<AcademyProgrammeOwner kind="withdrawal" />)} />
      <Route path="finance/withdrawals/:applicationId" element={ownerElement("withdrawal",<WithdrawalDetailRoute />)} />
      <Route path="programmes/withdrawal" element={<Navigate to="/e-learning/finance/withdrawals" replace />} />
      <Route path="programmes/:kind/:applicationId" element={<ProgrammeRoute user={user} />} />
      <Route path="exchange-opportunities" element={<CapabilityRoute user={user} capability="exchange"><AcademyExchangeOpportunities /></CapabilityRoute>} />
      <Route path="contacts/:contactId" element={<CapabilityRoute user={user} capability="contact"><ContactDetailRoute /></CapabilityRoute>}/>
      <Route path="contacts" element={<CapabilityRoute user={user} capability="contact"><AcademyContactInbox /></CapabilityRoute>} />
      <Route path="students" element={<AcademyStudentsPage />} />
      <Route path="finance/:kind" element={<FinanceRoute user={user} />} />
      <Route path="programmes/:kind" element={<ProgrammeRoute user={user} />} />
      <Route path="reports" element={ownerElement("reports",<AcademyReportsPage />)} />
      <Route path="programmes" element={<Navigate to="/e-learning/programmes/affiliate" replace />} />
      <Route index element={<Navigate to="courses" replace />} />
      <Route path="courses" element={<ELearningCoursesPage />} />
      <Route path="courses/:courseId" element={<CourseRoute />} />
      <Route path="courses/:courseId/:tab" element={<CourseRoute />} />
      <Route path="courses/:courseId/lessons/:lessonId" element={<LessonRoute />} />
      <Route path="groups/:itemId/:tab?" element={<ELearningRelationshipsPage kind="group" />} />
      <Route path="instructors/:itemId/:tab?" element={<ELearningRelationshipsPage kind="instructor" />} />
      <Route path="groups" element={<ELearningDirectoryPage key="groups" kind="groups" />} />
      <Route path="instructors" element={<ELearningDirectoryPage key="instructors" kind="instructors" />} />
      <Route path="settings" element={<ELearningSettingsPage user={user} />} />
      <Route path="theme" element={<AcademyThemePage user={user} />} />
      <Route path="landing-page" element={<AcademyLandingPageEntry key={`${user?.tenant_id}:${user?.id}`} />} />
      <Route path="academy-access" element={<AcademyManagementHub user={user} />} />
      <Route path="settings/academy" element={<Navigate to="/e-learning/academy-access" replace />} />
      <Route path="plans" element={<ELearningPlansPage />} />
      <Route path="settings/plans" element={<Navigate to="/e-learning/plans" replace />} />
      <Route path="*" element={<Navigate to="/e-learning/courses" replace />} />
    </Routes>
  </ELearningTerminologyProvider></div>;
}

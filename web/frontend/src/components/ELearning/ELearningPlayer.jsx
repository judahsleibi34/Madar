import LearningErrorNotice from "./LearningErrorNotice";
import { learningDescription } from "../../utils/elearningPresentation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, Route, Routes, useLocation, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Lock, BookOpen } from "lucide-react";
import { ELearningTerminologyContext } from "../../context/ELearningTerminologyContext";
import { getELearningTerminology } from "../../config/elearningTerminology";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import { fetchLearningAccountContext, fetchMyLearning, fetchLearningCourse, fetchLearningLesson, completeLearningLesson } from "../../services/elearningPlayer";
import { LearningExperienceContext, useLearningExperience } from "./LearningExperienceContext";
import LessonStepTracker from "./content/LessonStepTracker";
import ExamCard from "./content/ExamCard";
import { assembleLessonSteps, stepAnchor } from "../../utils/lessonSteps";
import { CircleDot, Circle } from "lucide-react";
import { getApiUrl } from "../../utils/apiClient";
import ELearningSkeleton from "./ELearningSkeleton";
import ContentBlockRenderer from "./content/ContentBlockRenderer";
import ELearningCatalog, { MyLearningPlans } from "./ELearningCatalog";
import "../../styles/admin/dashboard/elearning-content.css";
import "../../styles/admin/dashboard/elearning-player.css";

import useLearningDrawer from "../../hooks/useLearningDrawer";
import ChangePasswordPage from "../DashboardBuilder/ChangePasswordPage";
import ELearningLearnerShell from "./ELearningLearnerShell";
import AcademyProgrammesPage from "./AcademyProgrammesPage";
import NotificationsPage from "../DashboardBuilder/NotificationsPage";
import LearningFormApplicantResponses from "./LearningFormApplicantResponses";
import LearningFormApplicantResponse from "./LearningFormApplicantResponse";
import LearnerAccount from "./LearnerAccount";
import AssessmentReviews from "./AssessmentReviews";
import LearnerDashboard from "./LearnerDashboard";
import LearnerExchange from "./LearnerExchange";
import AffiliateDashboard from "./AffiliateDashboard";

import { MyCertificates, CredentialView } from "./ELearningCertificates";
import StudentOverview from "./student/StudentOverview";
import StudentCourse from "./student/StudentCourse";
import StudentExams from "./student/StudentExams";
import StudentReferral from "./student/StudentReferral";
import StudentApplications from "./student/StudentApplications";
import { StudentWallet, StudentWithdraw } from "./student/StudentWallet";

const coursePath = (id) => `/my-learning/courses/${id}`;
const assessmentPath = (course, placement) => `${coursePath(course)}/assessments/${placement}`;
const lessonPath = (course, lesson) => `${coursePath(course)}/lessons/${lesson}`;

function useLearningRequest(load, dependencies) {
  const [state, setState] = useState({ loading: true });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    load().then((data) => { if (active) setState({ data }); }).catch((error) => { if (active) setState({ error }); });
    return () => { active = false; };
    // The callers pass route/request keys; load is intentionally local to each render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...dependencies, attempt]);
  return { ...state, setState, retry: () => { setState({ loading: true }); setAttempt((value) => value + 1); } };
}

function ErrorState({ error, retry }) {
  const { t } = useTranslation("dashboard");
  const key = error?.detail?.code || error?.code;
  return <LearningErrorNotice className="ecommerce-list-card ecommerce-empty-state" as="div"><p>{t(key === "elearning_lesson_locked" ? "elearning.player.lockedHelp" : error?.status === 404 ? "elearning.player.unavailable" : "elearning.player.loadError")}</p><button className="ecommerce-secondary-button" onClick={retry}>{t("elearning.retry")}</button><Link to="/my-learning">{t("elearning.player.myLearning")}</Link></LearningErrorNotice>;
}

function Progress({ value }) {
  const { t } = useTranslation("dashboard");
  const { labels } = useELearningTerminology();
  return <div className="elearning-player-progress"><div><strong>{value.progress_percent}%</strong><span>{t("elearning.player.count", { completed: value.completed_lessons, total: value.total_lessons, lessons: labels.plural.lesson })}</span></div><progress max="100" value={value.progress_percent} aria-label={t("elearning.player.progress")} /></div>;
}

function Continue({ data, currentAssessment }) {
  const { t } = useTranslation("dashboard");
  return data.continue_lesson_id ? <Link className="ecommerce-primary-button" to={lessonPath(data.course.id, data.continue_lesson_id)}>{t("elearning.player.continue")}</Link> : data.continue_assessment_id && data.continue_assessment_id !== currentAssessment ? <Link className="ecommerce-primary-button" to={assessmentPath(data.course.id, data.continue_assessment_id)}>{t("elearning.player.continue")}</Link> : data.progress.progress_status === "completed" ? <span className="elearning-course-status is-published"><CheckCircle2 size={16} />{t("elearning.player.completed")}</span> : <p>{t("elearning.player.noLessons")}</p>;
}

export default function ELearningPlayer() {
  const { t, i18n } = useTranslation("dashboard");
  const location = useLocation();
  const accountRoute = /^\/my-learning\/(affiliate(?:\/|$)|exchange(?:\/|$)|referrals$|rewards$|wallet$|withdrawals$|programmes$)/.test(location.pathname);
  const state = useLearningRequest(() => accountRoute ? fetchLearningAccountContext() : fetchMyLearning(), [accountRoute]);
  if (state.loading) return <ELearningSkeleton label={t("elearning.player.loading")} direction={i18n.dir()} lang={i18n.language} />;
  if (state.error) return <main className="ecommerce-page elearning-management" dir={i18n.dir()}><ErrorState {...state} /></main>;
  const terminology = { labels: getELearningTerminology(state.data.settings), loading: false, error: null };
  // EduHope student dashboard (opt-in per academy: academyExperience.studentDashboard).
  const student = state.data.academy?.experience?.studentDashboard === true;
  return <ELearningTerminologyContext.Provider value={terminology}><LearningExperienceContext.Provider value={state.data.academy?.experience || {}}><ELearningLearnerShell site={state.data.academy}><main className="ecommerce-page elearning-management elearning-player" dir={i18n.dir()} lang={i18n.language}>
    <Routes><Route path="form-responses" element={<LearningFormApplicantResponses />} /><Route path="form-responses/:responseId" element={<LearningFormApplicantResponse />} /><Route path="assessment-reviews" element={<AssessmentReviews />} /><Route path="assessment-reviews/:attemptId" element={<AssessmentReviews />} /><Route path="exchange" element={<LearnerExchange />} /><Route path="exchange/:opportunityId" element={<LearnerExchange detail />} /><Route path="affiliate" element={<AffiliateDashboard site={state.data.academy} />} /><Route path="affiliate/application" element={<AcademyProgrammesPage key="affiliate-application" affiliateOnly />} /><Route path="programmes" element={<AcademyProgrammesPage key="programmes" />} /><Route path="notifications" element={<NotificationsPage />} /><Route index element={student ? <StudentOverview /> : <MyLearning />} /><Route path="dashboard" element={student ? <StudentOverview /> : <LearnerDashboard />} />{student && <><Route path="course" element={<StudentCourse />} /><Route path="course/levels/:sectionId" element={<StudentCourse />} /><Route path="exams" element={<StudentExams />} /><Route path="referral" element={<StudentReferral />} /><Route path="withdraw" element={<StudentWithdraw />} /><Route path="applications" element={<StudentApplications />} /></>}<Route path="referrals" element={<LearnerAccount key="referrals" view="referrals" site={state.data.academy} />} /><Route path="rewards" element={<LearnerAccount key="rewards" view="rewards" site={state.data.academy} />} /><Route path="wallet" element={student ? <StudentWallet /> : <LearnerAccount key="wallet" view="wallet" site={state.data.academy} />} /><Route path="withdrawals" element={<AcademyProgrammesPage key="withdrawals" initialKind="withdrawal" />} /><Route path="account" element={<LearnerAccount key="profile" />} /><Route path="account/password" element={<ChangePasswordPage lang={i18n.language.startsWith("ar") ? "ar" : "en"} backPath="/my-learning/account" backLabel={t("elearning.learner.account")} />} /><Route path="certificates" element={<MyCertificates />} /><Route path="certificates/:credentialId" element={<CredentialView />} /><Route path="catalog" element={<ELearningCatalog />} /><Route path="plans" element={<MyLearningPlans />} /><Route path="courses/:courseId" element={<CourseEntry />} /><Route path="courses/:courseId/lessons/:lessonId" element={<CourseEntry />} /><Route path="courses/:courseId/assessments/:placementId" element={<CourseEntry />} /><Route path="*" element={<ErrorState error={{ status: 404 }} retry={state.retry} />} /></Routes>
  </main></ELearningLearnerShell></LearningExperienceContext.Provider></ELearningTerminologyContext.Provider>;
}

function MyLearning() {
  const { t, i18n } = useTranslation("dashboard");
  const { labels } = useELearningTerminology();
  const fresh = useLearningRequest(() => fetchMyLearning(), []);
  const [extra, setExtra] = useState([]);
  const [hasMore, setMore] = useState(null);
  const courses = [...(fresh.data?.courses || []), ...extra];
  const more = hasMore ?? fresh.data?.has_more;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  async function loadMore() {
    setBusy(true); setError(null);
    try { const data = await fetchMyLearning(courses.length); setExtra((previous) => [...previous, ...data.courses]); setMore(data.has_more); }
    catch (failure) { setError(failure); } finally { setBusy(false); }
  }
  if (fresh.loading) return <ELearningSkeleton label={t("elearning.player.loading")} direction={i18n.dir()} lang={i18n.language} />;
  if (fresh.error) return <ErrorState {...fresh} />;
  return <><header className="ecommerce-page-header app-page-intro"><div><h1>{t("elearning.player.myLearning")}</h1><p>{t("elearning.player.intro")}</p></div></header>
    {!courses.length && <div className="ecommerce-list-card ecommerce-empty-state"><BookOpen size={36} /><h2>{t("elearning.player.empty")}</h2><p>{t("elearning.player.emptyHelp")}</p></div>}
    <div className="elearning-course-grid">{courses.map((data) => <article className="ecommerce-list-card elearning-course-card" key={data.course.id}>
      <div className="elearning-course-cover">{data.course.cover_url ? <img src={data.course.cover_url.startsWith("/uploads/") ? getApiUrl(data.course.cover_url) : data.course.cover_url} alt="" /> : <BookOpen size={32} aria-hidden="true" />}</div>
      <h2><Link to={coursePath(data.course.id)}>{data.course.name}</Link></h2><Progress value={data.progress} />{data.progress.completion && <p role="status">{t(`elearning.placements.${data.progress.completion.completed ? "completed" : "incomplete"}`, { label: labels.course })}{data.progress.completion.completed_at && ` · ${new Date(data.progress.completion.completed_at).toLocaleString()}`}</p>}<footer className="elearning-course-actions"><Continue data={data} /><Link className="ecommerce-secondary-button" to={coursePath(data.course.id)}>{t("elearning.player.openCourse")}</Link></footer>
    </article>)}</div>{error && <ErrorState error={error} retry={loadMore} />}{more && <button className="ecommerce-secondary-button" disabled={busy} onClick={loadMore}>{t("elearning.player.more")}</button>}
  </>;
}

function CourseEntry() {
  const { courseId, lessonId, placementId } = useParams();
  return <CoursePlayer key={`${courseId}:${lessonId || placementId || "outline"}`} courseId={courseId} lessonId={lessonId} placementId={placementId} />;
}

function CoursePlayer({ courseId, lessonId, placementId }) {
  const { t, i18n } = useTranslation("dashboard");
  const { labels } = useELearningTerminology();
  const state = useLearningRequest(() => lessonId ? fetchLearningLesson(courseId, lessonId) : fetchLearningCourse(courseId), [courseId, lessonId, placementId]);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [outlineOpen, setOutlineOpen] = useState(false);
  const enhanced = useLearningExperience().lessonComponents === true;
  const outlineRef = useRef(null);
  const closeOutline = useCallback(() => setOutlineOpen(false), []);
  useLearningDrawer(outlineOpen, outlineRef, closeOutline);
  if (state.loading) return <ELearningSkeleton variant={lessonId ? "lesson" : "course"} label={t("elearning.player.loading")} direction={i18n.dir()} lang={i18n.language} />;
  if (state.error) return <ErrorState {...state} />;
  const data = state.data;
  const selectedAssessment = [...(data.assessments || []), ...data.sections.flatMap(section => section.assessments || [])].find(assessment => assessment.placement_id === placementId);
  if (placementId && !selectedAssessment) return <ErrorState error={{ status: 404 }} retry={state.retry} />;
  const lessons = data.sections.flatMap((section) => section.lessons);
  const index = lessons.findIndex((lesson) => lesson.id === lessonId);
  const previous = lessons[index - 1], next = lessons[index + 1];
  async function complete() {
    setBusy(true); setSaveError(null);
    try { state.setState({ data: await completeLearningLesson(courseId, lessonId) }); }
    catch (error) { setSaveError(error); } finally { setBusy(false); }
  }
  return <><nav className="elearning-content-breadcrumb" aria-label={t("elearning.content.breadcrumb")}><Link to="/my-learning">{t("elearning.player.myLearning")}</Link><span aria-hidden="true">/</span><Link to={coursePath(courseId)}>{data.course.name}</Link>{data.lesson && <><span aria-hidden="true">/</span><span>{data.lesson.section_name}</span></>}</nav>
    <header className="ecommerce-page-header app-page-intro"><div><h1>{selectedAssessment?.title || data.lesson?.name || data.course.name}</h1><p>{lessonId ? data.course.name : learningDescription(data.course.description)}</p></div></header><Progress value={data.progress} />{data.progress.completion && <p role="status">{t(`elearning.placements.${data.progress.completion.completed ? "completed" : "incomplete"}`, { label: labels.course })}{data.progress.completion.completed_at && ` · ${new Date(data.progress.completion.completed_at).toLocaleString()}`}</p>}
    {data.credential && <Link className="ecommerce-primary-button" to={`/my-learning/certificates/${data.credential.id}`}>{t("elearning.certificates.viewCertificate")}</Link>}
    <button className="elearning-outline-toggle ecommerce-secondary-button" aria-expanded={outlineOpen} aria-controls="course-learning-outline" onClick={() => setOutlineOpen(!outlineOpen)}>{t("elearning.player.outline")}</button>
    {outlineOpen && <button className="elearning-outline-backdrop" aria-label={t("elearning.learner.closeMenu")} onClick={closeOutline} />}
    {!lessonId && !placementId && <section className="ecommerce-list-card elearning-course-resume" aria-label={t("elearning.player.openCourse")}><div><h2>{t("elearning.player.continue")}</h2><p>{t("elearning.player.overviewHelp")}</p></div><Continue data={data} /></section>}
    <div className={`elearning-player-layout${lessonId || placementId ? " has-lesson" : ""}`}>
      <aside ref={outlineRef} tabIndex={-1} role={outlineOpen ? "dialog" : undefined} aria-modal={outlineOpen || undefined} id="course-learning-outline" className={`ecommerce-list-card elearning-player-outline${outlineOpen ? " is-open" : ""}`} aria-label={t("elearning.player.outline")}><button className="elearning-outline-close ecommerce-secondary-button" onClick={closeOutline}>{t("elearning.learner.closeMenu")}</button><h2>{t("elearning.player.outline")}</h2>{lessons.some(lesson => lesson.locked) && <p className="elearning-outline-help">{t("elearning.player.lockedHelp")}</p>}
        {data.sections.map((section) => <section key={section.id}><h3>{section.name} <small>{section.progress_percent}%</small></h3><span className="elearning-player-label">{labels.section}</span><ol>{section.lessons.map((lesson) => <li key={lesson.id} className={`${lesson.id === lessonId ? "is-current" : ""}${lesson.locked ? " is-locked" : ""}`}>{enhanced ? <TopicStatus lesson={lesson} current={lesson.id === (lessonId || data.continue_lesson_id)} /> : lesson.completed ? <CheckCircle2 size={17} aria-label={t("elearning.player.completed")} /> : lesson.locked ? <Lock size={17} aria-label={t("elearning.player.locked")} /> : <span aria-hidden="true">○</span>}{lesson.locked ? <span>{lesson.name}{!enhanced && <small className="elearning-lesson-state">{t("elearning.player.locked")}</small>}</span> : <Link aria-current={lesson.id === lessonId ? "page" : undefined} to={lessonPath(courseId, lesson.id)}>{lesson.name}</Link>}</li>)}</ol>{section.completion && <small>{t(`elearning.placements.${section.completion.completed ? "sectionComplete" : "sectionIncomplete"}`, { label: labels.section })}</small>}<AssessmentOutline assessments={section.assessments || []} courseId={courseId} placementId={placementId} /></section>)}<AssessmentOutline assessments={data.assessments || []} courseId={courseId} placementId={placementId} />
      </aside>
      {selectedAssessment && <article className="elearning-player-reading">{selectedAssessment.locked ? <p role="status">{t("elearning.placements.lockedHelp")}</p> : <ContentBlockRenderer key={placementId} block={{ id: placementId, type: "assessment", assessment: selectedAssessment }} context="learner" courseId={courseId} onAssessmentChange={async () => state.setState({ data: await fetchLearningCourse(courseId) })} />}<footer className="elearning-assessment-actions"><Link className="ecommerce-secondary-button" to={coursePath(courseId)}>{t("elearning.placements.backCourse", { label: labels.course })}</Link>{selectedAssessment.passed && (data.continue_lesson_id || (data.continue_assessment_id && data.continue_assessment_id !== placementId)) && <Continue data={data} currentAssessment={placementId} />}</footer></article>}
      {data.lesson && <article className="elearning-player-reading" aria-label={t("elearning.content.context", { label: labels.lesson })}>
        {enhanced && data.blocks.length > 0 ? <TopicLesson data={data} courseId={courseId} lessonId={lessonId} onAssessmentChange={async () => state.setState({ data: await fetchLearningLesson(courseId, lessonId) })} />
        : <div className="elearning-player-blocks">{data.blocks.map((block) => <ContentBlockRenderer key={block.id} block={block} context="learner" courseId={courseId} lessonId={lessonId} onAssessmentChange={async () => state.setState({ data: await fetchLearningLesson(courseId, lessonId) })} />)}{!data.blocks.length && <p>{t("elearning.player.emptyLesson")}</p>}</div>}
        {saveError && <ErrorState error={saveError} retry={complete} />}
        {!data.lesson.completed && data.assessment_requirements?.some(requirement => !requirement.passed) && <p role="status">{t("elearning.assessment.completionBlocked", { lesson: labels.lesson })}</p>}
        <footer className="ecommerce-list-card elearning-player-lesson-actions"><div className="elearning-content-toolbar">{previous && !previous.locked && <Link className="ecommerce-secondary-button" to={lessonPath(courseId, previous.id)}>{t("elearning.player.previous", { label: labels.lesson })}</Link>}{next && (next.locked ? <span className="elearning-course-status">{t("elearning.player.nextLocked", { label: labels.lesson })}</span> : <Link className={data.lesson.completed ? "ecommerce-primary-button" : "ecommerce-secondary-button"} to={lessonPath(courseId, next.id)}>{t("elearning.player.next", { label: labels.lesson })}</Link>)}</div>
          {data.lesson.completed ? <span role="status" className="elearning-course-status is-published"><CheckCircle2 size={17} />{t("elearning.player.completed")}</span> : <button className="ecommerce-primary-button" disabled={busy || data.assessment_requirements?.some(requirement => !requirement.passed)} onClick={complete}>{t("elearning.player.markComplete")}</button>}
        </footer>
      </article>}
    </div>
  </>;
}

// EH / Topic Row status: icon + text, never colour alone.
function TopicStatus({ lesson, current }) {
  const { t } = useTranslation("dashboard");
  const status = lesson.completed ? "completed" : lesson.locked ? "locked" : current ? "current" : "available";
  const Icon = { completed: CheckCircle2, locked: Lock, current: CircleDot, available: Circle }[status];
  return <span className={`topic-row-status is-${status}`}><Icon size={16} aria-hidden="true" />{t(`elearning.topicStatus.${status}`)}</span>;
}

// EH / Topic Lesson: the lesson's blocks grouped into the book's topic steps.
function TopicLesson({ data, courseId, lessonId, onAssessmentChange }) {
  const { t } = useTranslation("dashboard");
  const steps = assembleLessonSteps(data.blocks);
  const passed = new Map((data.assessment_requirements || []).map(item => [item.id, item.passed]));
  const passedSteps = steps.filter(({ blocks }) => {
    const required = blocks.filter(block => block.type === "assessment" && passed.has(block.assessment?.id));
    return required.length > 0 && required.every(block => passed.get(block.assessment.id));
  }).map(({ step }) => step);
  return <div className="topic-lesson">
    <LessonStepTracker steps={steps} passedSteps={passedSteps} />
    {steps.map(({ step, blocks }, index) => <section key={step} id={stepAnchor(step)} data-step={step} className="topic-lesson-step" aria-labelledby={`${stepAnchor(step)}-title`}>
      <h2 id={`${stepAnchor(step)}-title`}><span aria-hidden="true">{index + 1}</span>{t(`elearning.lessonSteps.${step}`)}</h2>
      <div className="elearning-player-blocks">{blocks.map(block => <ContentBlockRenderer key={block.id} block={block} context="learner" courseId={courseId} lessonId={lessonId} onAssessmentChange={onAssessmentChange} />)}</div>
    </section>)}
  </div>;
}

function AssessmentOutline({ assessments, courseId, placementId }) {
  const { t } = useTranslation("dashboard");
  const enhanced = useLearningExperience().lessonComponents === true;
  if (enhanced) return assessments.length > 0 && <div className="exam-card-list">{assessments.map(value => <ExamCard key={value.placement_id} exam={value} current={value.placement_id === placementId} href={assessmentPath(courseId, value.placement_id)} />)}</div>;
  return assessments.length > 0 && <ul className="elearning-assessment-outline">{assessments.map(value => <li key={value.placement_id} className={value.placement_id === placementId ? "is-current" : undefined}>{value.locked ? <Lock size={16} /> : value.passed ? <CheckCircle2 size={16} /> : <span aria-hidden="true">○</span>}{value.locked ? <span>{value.title} — {t("elearning.player.locked")}</span> : <Link aria-current={value.placement_id === placementId ? "page" : undefined} to={assessmentPath(courseId, value.placement_id)}>{value.title}</Link>}<small>{t(`elearning.placements.${value.required_for_completion ? "required" : "optional"}`)} · {value.passed ? `${t("elearning.assessment.passed")} — ${value.best_score}%` : value.attempts ? `${t("elearning.assessment.notPassed")} — ${value.best_score}%` : t("elearning.placements.notAttempted")}</small></li>)}</ul>;
}

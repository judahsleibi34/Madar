import { learningDescription } from "../../utils/elearningPresentation";
import ELearningSkeleton from "./ELearningSkeleton";
import { useCallback, useEffect, useState } from "react";
import { Link, NavLink, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft, BookOpen, Image } from "lucide-react";
import { DASHBOARD_ROUTES } from "../../config/routes";
import { fetchCourse } from "../../services/elearningCourses";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import ELearningCourseForm from "./ELearningCourseForm";
import { resolveMediaUrl } from "../../utils/media";
import ELearningStructurePage from "./ELearningStructurePage";
import ELearningLearnersPage from "./ELearningLearnersPage";
import ELearningRelationshipsPage from "./ELearningRelationshipsPage";
import ELearningProgressPage from "./ELearningProgressPage";

import ELearningAssessmentsPage from "./ELearningAssessmentsPage";

import CourseCertificates from "./ELearningCertificates";

const tabs = ["overview", "structure", "learners", "groups", "instructors", "assessments", "certificate", "progress", "settings"];
export default function ELearningCoursePage() {
  const { courseId, tab = "overview" } = useParams();
  const { t, i18n } = useTranslation("dashboard");
  const { labels, loading: labelsLoading, error: labelsError } = useELearningTerminology();
  const [course, setCourse] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [saved, setSaved] = useState(false);
  const [reload, setReload] = useState(0);
  const updateStructureCounts = useCallback((structure) => setCourse((current) => current ? { ...current, section_count: structure.section_count, lesson_count: structure.lesson_count } : current), []);
  useEffect(() => {
    let cancelled = false;
    fetchCourse(courseId).then((data) => { if (!cancelled) setCourse(data.course); })
      .catch((failure) => { if (!cancelled) setError(failure.status === 404 ? "courses.notFound" : failure.status === 403 ? "forbidden" : failure.status === 503 ? "courses.unavailable" : "courses.loadError"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [courseId, reload]);
  const validTab = tabs.includes(tab);
  if (loading || labelsLoading) return <ELearningSkeleton variant="course" tab={tab} label={t("elearning.courses.loading")} lang={i18n.language} direction={i18n.dir()} />;
  return <main className="ecommerce-page elearning-management" dir={i18n.dir()}>
    <header className="ecommerce-page-header app-page-intro"><div><h1>{t("elearning.navigation.courses")}</h1><p>{course?.name || t("elearning.courses.subtitle")}</p></div></header>
    <Link className="ecommerce-secondary-button elearning-back-link" to={DASHBOARD_ROUTES.elearningCourses}><ArrowLeft size={16} aria-hidden="true" />{t("elearning.courses.back")}</Link>
    {error && <p role="alert" className="elearning-feedback is-error">{t(`elearning.${error}`)} <button className="ecommerce-secondary-button" onClick={() => { setError(""); setLoading(true); setReload((value) => value + 1); }}>{t("elearning.retry")}</button></p>}
    {!loading && course && !error && <>
      <nav className="elearning-course-tabs" aria-label={t("elearning.courses.tabsLabel")}>{tabs.map((value) => <NavLink key={value} className={({ isActive }) => isActive ? "ecommerce-secondary-button active" : "ecommerce-secondary-button"} to={`${DASHBOARD_ROUTES.elearningCourses}/${course.id}${value === "overview" ? "" : `/${value}`}`} end>{t(`elearning.courses.tabs.${value}`)}</NavLink>)}</nav>
      {saved && <p role="status" className="elearning-feedback">{t("elearning.courses.saved", { label: labels.course })}</p>}
      {!validTab ? <p role="alert">{t("elearning.courses.notFound")}</p> : tab === "overview" ? <section className="ecommerce-list-card elearning-course-overview">
        <header><h2>{course.name}</h2><button className="ecommerce-primary-button" disabled={labelsError?.status === 403} onClick={() => setEditing(true)}>{t("elearning.courses.edit", { label: labels.course })}</button></header>
        <div className="elearning-course-cover elearning-overview-cover">{course.cover_asset ? <img src={resolveMediaUrl(course.cover_asset)} alt={t("elearning.courses.coverAlt", { name: course.name })} /> : <Image size={36} aria-hidden="true" />}</div>
        <p>{learningDescription(course.description) || t("elearning.courses.noDescription")}</p>
        <dl className="elearning-course-counts"><div><dt>{t("elearning.courses.status")}</dt><dd>{t(`elearning.courses.statuses.${course.status}`)}</dd></div><div><dt>{t("elearning.courses.access")}</dt><dd>{t(`elearning.courses.accessTypes.${course.access_type}`)}</dd></div><div><dt>{labels.plural.section}</dt><dd>{course.section_count}</dd></div><div><dt>{labels.plural.lesson}</dt><dd>{course.lesson_count}</dd></div><div><dt>{t("elearning.courses.learners")}</dt><dd>{course.learner_count}</dd></div></dl>
        <Link to={`${DASHBOARD_ROUTES.elearningCourses}/${course.id}/instructors`}>{t("elearning.assignments.assignedLabels", { labels: labels.plural.instructor })}</Link>
      </section> : tab === "structure" ? <ELearningStructurePage course={course} onUpdated={updateStructureCounts} /> : ["groups", "instructors"].includes(tab) ? <ELearningRelationshipsPage kind="course" course={course} selectedTab={tab} /> : tab === "assessments" ? <ELearningAssessmentsPage course={course} /> : tab === "certificate" ? <CourseCertificates course={course} /> : tab === "progress" ? <ELearningProgressPage key={course.id} course={course} /> : tab === "learners" ? <ELearningLearnersPage key={course.id} course={course} /> : <section className="ecommerce-list-card ecommerce-empty-state">
        <BookOpen size={36} aria-hidden="true" /><h2>{t(`elearning.courses.shell.${tab}Title`)}</h2><p>{t(`elearning.courses.shell.${tab}Help`, { section: labels.plural.section, lesson: labels.plural.lesson })}</p>
        {tab === "settings" && <button className="ecommerce-primary-button" disabled={labelsError?.status === 403} onClick={() => setEditing(true)}>{t("elearning.courses.edit", { label: labels.course })}</button>}
      </section>}
      {editing && <ELearningCourseForm course={course} onClose={() => setEditing(false)} onSaved={(updated) => { setCourse(updated); setEditing(false); setSaved(true); }} />}
    </>}
  </main>;
}

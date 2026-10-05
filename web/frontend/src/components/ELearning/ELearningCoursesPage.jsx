import { learningDescription } from "../../utils/elearningPresentation";
import ELearningSkeleton from "./ELearningSkeleton";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { BookOpen, Plus, Pencil, Copy, Archive, Settings2, Trash2 } from "lucide-react";
import { DASHBOARD_ROUTES } from "../../config/routes";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import { fetchCourses, duplicateCourse, archiveCourse, deleteCourse } from "../../services/elearningCourses";
import { resolveMediaUrl } from "../../utils/media";
import ELearningCourseForm from "./ELearningCourseForm";
import ELearningDialog from "./ELearningDialog";

export default function ELearningCoursesPage() {
  const { t, i18n } = useTranslation("dashboard");
  const { labels, loading: labelsLoading, error: labelsError, retry } = useELearningTerminology();
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [available, setAvailable] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [form, setForm] = useState(null);
  const [archiving, setArchiving] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [confirmationName, setConfirmationName] = useState("");
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let cancelled = false;
    fetchCourses().then((data) => { if (!cancelled) { setCourses(data.courses); setAvailable(data.available); setHasMore(data.has_more); } })
      .catch((failure) => { if (!cancelled) setError(failure.status === 403 ? "forbidden" : "courses.loadError"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [reload]);
  const loadMore = async () => {
    setBusy(true); setError("");
    try { const data = await fetchCourses(courses.length); setCourses((current) => [...current, ...data.courses.filter((row) => !current.some((existing) => existing.id === row.id))]); setHasMore(data.has_more); }
    catch { setError("courses.loadError"); } finally { setBusy(false); }
  };
  const apply = (course) => setCourses((current) => current.some((row) => row.id === course.id) ? current.map((row) => row.id === course.id ? course : row) : [course, ...current]);
  const action = async (kind, course) => {
    setBusy(true); setError(""); setFeedback("");
    try {
      const data = await (kind === "delete" ? deleteCourse(course, confirmationName) : kind === "archive" ? archiveCourse(course) : duplicateCourse(course));
      if (kind === "delete") setCourses((current) => current.filter((item) => item.id !== course.id)); else apply(data.course);
      setArchiving(null); setDeleting(null); setFeedback(`courses.${kind === "delete" ? "deleted" : kind === "archive" ? "archived" : "duplicated"}`);
    } catch (failure) { setError((failure.data?.detail?.code || failure.code) === "elearning_course_delete_protected" ? "courses.deleteProtected" : failure.status === 409 ? "courses.conflict" : failure.status === 403 ? "forbidden" : "courses.actionError"); }
    finally { setBusy(false); }
  };
  const disabled = loading || labelsLoading || busy || !available || error === "forbidden" || labelsError?.status === 403;
  const date = (value) => value ? new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium" }).format(new Date(value)) : "—";
  if (loading || labelsLoading) return <ELearningSkeleton variant="courses" label={t("elearning.courses.loading")} lang={i18n.language} direction={i18n.dir()} />;
  return <main className="ecommerce-page elearning-management elearning-courses-page" dir={i18n.dir()}>
    <header className="ecommerce-page-header app-page-intro"><div><h1>{t("elearning.navigation.courses")}</h1><p>{t("elearning.courses.subtitle")}</p></div></header>
    <div className="elearning-course-toolbar"><button className="ecommerce-primary-button" disabled={disabled} onClick={() => { setForm({}); setFeedback(""); }}><Plus size={18} aria-hidden="true" />{t("elearning.courses.create", { label: labels.course })}</button></div>
    {error && !archiving && !deleting && <div role="alert" className="elearning-feedback is-error">{t(`elearning.${error}`)} <button className="ecommerce-secondary-button" onClick={() => { setError(""); setLoading(true); setReload((value) => value + 1); }}>{t("elearning.retry")}</button></div>}
    {feedback && <p role="status" className="elearning-feedback">{t(`elearning.${feedback}`, { label: labels.course })}</p>}
    {labelsError && <div role={labelsError.status === 403 ? "alert" : "status"} className="elearning-feedback">{t(labelsError.status === 403 ? "elearning.forbidden" : "elearning.courses.labelsUnavailable")} <button className="ecommerce-secondary-button" onClick={retry}>{t("elearning.retry")}</button></div>}
    {!available ? <p className="elearning-feedback" role="status">{t("elearning.courses.upgradeRequired")}</p> : !courses.length && !error ? <section className="ecommerce-list-card ecommerce-empty-state"><BookOpen size={36} aria-hidden="true" /><h2>{t("elearning.courses.empty")}</h2><p>{t("elearning.courses.emptyHelp", { label: labels.course })}</p></section> : <div className="elearning-course-grid">
      {courses.map((course) => <article className="ecommerce-list-card elearning-course-card" key={course.id}>
        <div className="elearning-course-body">
          <header className="elearning-course-card-heading"><div className="elearning-course-thumbnail">{course.cover_asset ? <img src={resolveMediaUrl(course.cover_asset)} alt={t("elearning.courses.coverAlt", { name: course.name })} /> : <BookOpen size={24} aria-hidden="true" />}</div><div className="elearning-course-heading-copy"><h2><Link to={`${DASHBOARD_ROUTES.elearningCourses}/${course.id}`}>{course.name}</Link></h2><div className="elearning-course-badges"><span className={`elearning-course-status is-${course.status}`}>{t(`elearning.courses.statuses.${course.status}`)}</span><span className="elearning-access-badge">{t(`elearning.courses.accessTypes.${course.access_type}`)}</span></div></div></header>
          <p className="elearning-course-description">{learningDescription(course.description) || t("elearning.courses.noDescription")}</p>
          <dl className="elearning-course-counts"><div><dt>{labels.plural.section}</dt><dd>{course.section_count}</dd></div><div><dt>{labels.plural.lesson}</dt><dd>{course.lesson_count}</dd></div><div><dt>{t("elearning.courses.learners")}</dt><dd>{course.learner_count}</dd></div></dl>
          <div className="elearning-course-completion"><span>{t("elearning.participation.average")}</span><strong>{course.average_progress ?? 0}%</strong><progress max="100" value={course.average_progress ?? 0} aria-label={t("elearning.participation.progressFor", { name: course.name })} /></div>
          <footer className="elearning-course-actions"><Link className="ecommerce-secondary-button" to={`${DASHBOARD_ROUTES.elearningCourses}/${course.id}`}><Settings2 size={15} aria-hidden="true" />{t("elearning.courses.manage")}</Link><div className="elearning-course-icon-actions"><button className="ecommerce-icon-button" aria-label={t("elearning.courses.editAction")} title={t("elearning.courses.editAction")} disabled={disabled} onClick={() => setForm({ course })}><Pencil size={16} aria-hidden="true" /></button><button className="ecommerce-icon-button" aria-label={t("elearning.courses.duplicate")} title={t("elearning.courses.duplicate")} disabled={disabled} onClick={() => action("duplicate", course)}><Copy size={16} aria-hidden="true" /></button>{course.status !== "archived" && <button className="ecommerce-icon-button" aria-label={t("elearning.courses.archive")} title={t("elearning.courses.archive")} disabled={disabled} onClick={() => { setError(""); setArchiving(course); }}><Archive size={16} aria-hidden="true" /></button>}<button className="ecommerce-icon-button elearning-course-delete" aria-label={t("elearning.structure.delete")} title={t(course.deletion_available ? "elearning.structure.delete" : "elearning.courses.deleteUnavailable")} disabled={disabled || !course.deletion_available} onClick={() => { setError(""); setConfirmationName(""); setDeleting(course); }}><Trash2 size={16} aria-hidden="true" /></button></div></footer>
          <p className="elearning-course-date">{t("elearning.courses.updated")} {date(course.updated_at)}</p>
        </div>
      </article>)}
    </div>}
    {hasMore && <button className="ecommerce-secondary-button" disabled={busy} onClick={loadMore}>{t("elearning.courses.loadMore")}</button>}
    {form && <ELearningCourseForm course={form.course} onClose={() => setForm(null)} onSaved={(course) => { apply(course); setForm(null); setFeedback("courses.saved"); }} />}
    {deleting && <ELearningDialog title={t("elearning.courses.deleteTitle", { label: labels.course })} closeLabel={t("elearning.courses.close")} busy={busy} onClose={() => setDeleting(null)}><form onSubmit={(event) => { event.preventDefault(); if (!busy && confirmationName === deleting.name) action("delete", deleting); }}>{error && <p role="alert" className="elearning-feedback is-error">{t(`elearning.${error}`)}</p>}<p>{t("elearning.courses.deleteHelp", { name: deleting.name, sections: labels.plural.section, lessons: labels.plural.lesson })}</p><fieldset className="elearning-course-form" disabled={busy}><label>{t("elearning.courses.confirmName", { name: deleting.name })}<input autoFocus required maxLength={120} autoComplete="off" value={confirmationName} onChange={(event) => setConfirmationName(event.target.value)} /></label></fieldset><footer><button type="button" className="ecommerce-secondary-button" disabled={busy} onClick={() => setDeleting(null)}>{t("elearning.courses.cancel")}</button><button type="submit" className="ecommerce-primary-button" disabled={busy || confirmationName !== deleting.name}>{t("elearning.structure.delete")}</button></footer></form></ELearningDialog>}
    {archiving && <ELearningDialog title={t("elearning.courses.archiveTitle", { label: labels.course })} closeLabel={t("elearning.courses.close")} busy={busy} onClose={() => setArchiving(null)}>{error && <p role="alert" className="elearning-feedback is-error">{t(`elearning.${error}`)}</p>}<p>{t("elearning.courses.archiveHelp", { name: archiving.name })}</p><footer><button className="ecommerce-secondary-button" disabled={busy} onClick={() => setArchiving(null)}>{t("elearning.courses.cancel")}</button><button className="ecommerce-primary-button" disabled={busy} onClick={() => action("archive", archiving)}>{t("elearning.courses.archive")}</button></footer></ELearningDialog>}
  </main>;
}

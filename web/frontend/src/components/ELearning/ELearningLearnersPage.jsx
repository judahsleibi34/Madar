import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { changeRelationship } from "../../services/elearningRelationships";
import { Plus, Search } from "lucide-react";
import { fetchCourseEnrollments, changeEnrollmentStatus } from "../../services/elearningParticipation";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import { ProgressBar, ProgressStatus, LearnerProgressDialog } from "./ELearningProgressDetail";
import { ELearningProgressSkeleton } from "./ELearningSkeleton";
import ELearningDialog from "./ELearningDialog";
import Actions from "./ELearningActions";
import ELearningEnrollUsersDialog from "./ELearningEnrollUsersDialog";

export default function ELearningLearnersPage({ course }) {
  const { t, i18n } = useTranslation("dashboard");
  const { labels } = useELearningTerminology();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [progress, setProgress] = useState("");
  const [group, setGroup] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [enrolling, setEnrolling] = useState(false);
  const [confirmation, setConfirmation] = useState(null);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  useEffect(() => {
    let cancelled = false;
    fetchCourseEnrollments(course.id).then((result) => { if (!cancelled) setData(result); })
      .catch((failure) => { if (!cancelled) setError(failure.status === 403 ? "elearning.forbidden" : failure.status === 404 ? "elearning.courses.notFound" : failure.status === 503 ? "elearning.enrollments.unavailable" : "elearning.participation.loadError"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [course.id, reload]);
  const refresh = () => { setError(""); setLoading(true); setSelectedId(null); setConfirmation(null); setReload((value) => value + 1); };
  const act = async (learner, action) => {
    setBusy(true); setError(""); setFeedback("");
    try { if (action.startsWith("revoke_")) await changeRelationship("course", course.id, { action, target_id: learner.id, confirmed: true }); else await changeEnrollmentStatus(course.id, learner, action); setFeedback("elearning.enrollments.updated"); refresh(); }
    catch (failure) { setError(failure.status === 409 ? "elearning.enrollments.conflict" : failure.status === 403 ? "elearning.forbidden" : "elearning.enrollments.actionError"); }
    finally { setBusy(false); }
  };
  const learners = data?.enrollments || [];
  const normalizedQuery = query.trim().toLocaleLowerCase(i18n.language);
  const groups = [...new Map(learners.flatMap((learner) => learner.access_sources ? learner.access_sources.filter((source) => source.group_id).map((source) => [source.group_id, source.group_name]) : learner.group_id ? [[learner.group_id, learner.group_name]] : [])).entries()];
  const filtered = learners.filter((learner) => (!status || learner.enrollment_status === status) && (!progress || learner.progress_status === progress) && (!group || (learner.access_sources?.some((source) => source.group_id === group) || learner.group_id === group)) && `${learner.name} ${learner.email}`.toLocaleLowerCase(i18n.language).includes(normalizedQuery));
  const selected = learners.find((learner) => learner.id === selectedId);
  const neutral = t("elearning.enrollments.notConnected");
  const access = (learner) => learner.access_sources ? ["manual", "free", "group", "purchase"].filter((type) => learner.access_sources.some((source) => source.type === type)).map((type) => t(`elearning.assignments.sources.${type}`)).join(" + ") || t("elearning.assignments.noAccess") : ["manual", "free"].includes(learner.access_source) ? t(`elearning.participation.access_${learner.access_source}`) : neutral;
  const enrollmentStatus = (learner) => t(`elearning.enrollments.statuses.${learner.enrollment_status}`);
  const date = (value) => value && !Number.isNaN(new Date(value).getTime()) ? new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium" }).format(new Date(value)) : t("elearning.progress.unavailableActivity");
  const currentSection = (learner) => learner.progress_status === "completed" ? t("elearning.participation.completed") : learner.sections.find((section) => section.status === "published" && section.total_lessons > section.completed_lessons)?.name || t("elearning.progress.noApplicableLessons", { labels: labels.plural.lesson });
  if (loading) return <ELearningProgressSkeleton count={4} label={t("elearning.participation.loading")} />;
  return <section className="elearning-progress-page elearning-learners-page" aria-labelledby="elearning-learners-title">
    <header className="elearning-structure-header"><div><h2 id="elearning-learners-title">{t("elearning.courses.tabs.learners")}</h2><p>{t("elearning.enrollments.help")}</p></div><button className="ecommerce-primary-button" disabled={busy || !!error || course.status !== "published"} onClick={() => { setEnrolling(true); setFeedback(""); }}><Plus size={18} aria-hidden="true" />{t("elearning.enrollments.enroll")}</button></header>
    {course.status !== "published" && <p className="elearning-feedback">{t("elearning.enrollments.publishRequired")}</p>}
    {error && !confirmation && <p role="alert" className="elearning-feedback is-error">{t(error)} <button className="ecommerce-secondary-button" disabled={busy} onClick={refresh}>{t("elearning.retry")}</button></p>}
    {feedback && <p role="status" className="elearning-feedback">{t(feedback)}</p>}
    {data && (!error || confirmation) && <>
      <dl className="elearning-progress-overview">{[["total", data.learner_count], ["active", data.enrollment_active_count], ["completed", data.completed_count], ["not_started", data.not_started_count]].map(([key, value]) => <div className="ecommerce-list-card" key={key}><dt>{t(`elearning.enrollments.overview.${key}`)}</dt><dd>{value}</dd></div>)}</dl>
      <div className="elearning-progress-tools"><label className="ecommerce-search"><Search size={18} aria-hidden="true" /><input type="search" aria-label={t("elearning.progress.search")} placeholder={t("elearning.progress.search")} value={query} onChange={(event) => setQuery(event.target.value)} /></label><label className="elearning-progress-filter">{t("elearning.enrollments.enrollmentStatus")}<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">{t("elearning.progress.allStatuses")}</option>{["active", "suspended", "archived"].map((value) => <option key={value} value={value}>{t(`elearning.enrollments.statuses.${value}`)}</option>)}</select></label><label className="elearning-progress-filter">{t("elearning.progress.statusFilter")}<select value={progress} onChange={(event) => setProgress(event.target.value)}><option value="">{t("elearning.progress.allStatuses")}</option>{["not_started", "active", "completed"].map((value) => <option key={value} value={value}>{t(`elearning.participation.${value}`)}</option>)}</select></label><label className="elearning-progress-filter">{labels.group}<select value={group} disabled={!groups.length} onChange={(event) => setGroup(event.target.value)}><option value="">{groups.length ? t("elearning.enrollments.allGroups") : neutral}</option>{groups.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label></div>
      <p role="status" className="elearning-course-description">{t("elearning.progress.results", { count: filtered.length, total: learners.length })}</p>
      {!filtered.length ? <div className="ecommerce-list-card ecommerce-empty-state"><h3>{t(learners.length ? "elearning.progress.noMatches" : "elearning.participation.empty")}</h3>{learners.length > 0 && <button className="ecommerce-secondary-button" onClick={() => { setQuery(""); setStatus(""); setProgress(""); setGroup(""); }}>{t("elearning.progress.clearFilters")}</button>}</div> : <div className="ecommerce-list-card elearning-progress-table-wrap" role="region" aria-label={t("elearning.enrollments.table")} tabIndex={0}><table className="elearning-progress-table"><caption>{t("elearning.enrollments.table")}</caption><thead><tr>{[t("elearning.progress.learner"), t("elearning.enrollments.email"), t("elearning.enrollments.enrollmentStatus"), t("elearning.progress.completion"), t("elearning.enrollments.enrollmentDate"), t("elearning.enrollments.accessSource"), t("elearning.enrollments.payment"), labels.group, t("elearning.progress.actions")].map((heading) => <th scope="col" key={heading}>{heading}</th>)}</tr></thead><tbody>{filtered.map((learner) => <tr key={learner.id}><th scope="row"><button className="elearning-learner-name" onClick={() => setSelectedId(learner.id)}>{learner.name}</button></th><td>{learner.email}</td><td><span className={`elearning-course-status ${learner.enrollment_status === "active" ? "is-published" : ""}`}>{enrollmentStatus(learner)}</span>{learner.effective_access === false && <small>{t("elearning.assignments.noAccess")}</small>}</td><td><ProgressBar learner={learner} t={t} /><small>{t("elearning.participation.completion", { completed: learner.completed_lessons, total: learner.total_lessons, labels: labels.plural.lesson })}</small><ProgressStatus learner={learner} t={t} /></td><td>{date(learner.enrolled_at)}</td><td>{access(learner)}</td><td>{learner.payment_status || neutral}</td><td>{learner.access_sources?.filter((source) => source.group_id).map((source) => source.group_name).join(", ") || learner.group_name || neutral}</td><td><div className="elearning-enrollment-actions"><button className="ecommerce-secondary-button" disabled={busy} aria-label={t("elearning.progress.viewFor", { name: learner.name })} onClick={() => setSelectedId(learner.id)}>{t("elearning.progress.view")}</button><Actions label={t("elearning.structure.actions", { name: learner.name })} disabled={busy}>{learner.enrollment_status === "active" ? <button className="ecommerce-secondary-button" disabled={busy} onClick={() => { setError(""); setConfirmation({ learner, action: "suspend" }); }}>{t("elearning.enrollments.suspend")}</button> : <button className="ecommerce-secondary-button" disabled={busy || course.status !== "published" || learner.learner_status !== "active"} onClick={() => act(learner, "reactivate")}>{t("elearning.enrollments.reactivate")}</button>}{learner.access_sources ? ["manual", "free"].filter((type) => learner.access_sources.some((source) => source.type === type)).map((type) => <button key={type} disabled={busy} onClick={() => { setError(""); setConfirmation({ learner, action: `revoke_${type}` }); }}>{t(`elearning.assignments.revoke_${type}`)}</button>) : learner.enrollment_status !== "archived" && <button className="ecommerce-secondary-button" disabled={busy} onClick={() => { setError(""); setConfirmation({ learner, action: "cancel" }); }}>{t("elearning.enrollments.cancel")}</button>}</Actions></div></td></tr>)}</tbody></table></div>}
    </>}
    {selected && !error && <LearnerProgressDialog learner={selected} course={course} onClose={() => setSelectedId(null)}><dl className="elearning-learner-information">{[[t("elearning.enrollments.email"), selected.email], [t("elearning.enrollments.enrollmentStatus"), enrollmentStatus(selected)], [t("elearning.enrollments.enrollmentDate"), date(selected.enrolled_at)], [t("elearning.progress.currentSection", { label: labels.section }), currentSection(selected)], [t("elearning.enrollments.accessSource"), access(selected)], [t("elearning.enrollments.payment"), selected.payment_status || neutral], [labels.group, selected.access_sources?.filter((source) => source.group_id).map((source) => source.group_name).join(", ") || selected.group_name || neutral]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></LearnerProgressDialog>}
    {enrolling && <ELearningEnrollUsersDialog course={course} onClose={() => setEnrolling(false)} onSaved={() => { setEnrolling(false); setFeedback("elearning.enrollments.enrolled"); refresh(); }} />}
    {confirmation && <ELearningDialog title={t(confirmation.action.startsWith("revoke_") ? `elearning.assignments.${confirmation.action}` : `elearning.enrollments.${confirmation.action}`)} closeLabel={t("elearning.courses.close")} busy={busy} onClose={() => { setConfirmation(null); setError(""); }}>{error && <p role="alert" className="elearning-feedback is-error">{t(error)}</p>}<p className="elearning-enrollment-confirm">{t(confirmation.action.startsWith("revoke_") ? "elearning.assignments.confirmHelp" : `elearning.enrollments.${confirmation.action}Help`, { name: confirmation.learner.name })}</p><footer><button className="ecommerce-secondary-button" disabled={busy} onClick={() => { setConfirmation(null); setError(""); }}>{t("elearning.courses.cancel")}</button><button className="ecommerce-primary-button" disabled={busy} onClick={() => act(confirmation.learner, confirmation.action)}>{t(confirmation.action.startsWith("revoke_") ? `elearning.assignments.${confirmation.action}` : `elearning.enrollments.${confirmation.action}`)}</button></footer></ELearningDialog>}
  </section>;
}

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Search } from "lucide-react";
import { fetchCourseProgress } from "../../services/elearningParticipation";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import { ProgressBar, ProgressStatus, LearnerProgressDialog } from "./ELearningProgressDetail";
import { ELearningProgressSkeleton } from "./ELearningSkeleton";

export default function ELearningProgressPage({ course }) {
  const { t, i18n } = useTranslation("dashboard");
  const { labels } = useELearningTerminology();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  useEffect(() => {
    let cancelled = false;
    fetchCourseProgress(course.id).then((result) => { if (!cancelled) setData(result); })
      .catch((failure) => { if (!cancelled) setError(failure.status === 403 ? "elearning.forbidden" : failure.status === 404 ? "elearning.courses.notFound" : failure.status === 503 ? "elearning.participation.unavailable" : "elearning.participation.loadError"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [course.id, reload]);
  const retry = () => { setData(null); setError(""); setLoading(true); setSelectedId(null); setReload((value) => value + 1); };
  const enrollments = data?.enrollments || [];
  const normalizedQuery = query.trim().toLocaleLowerCase(i18n.language);
  const filtered = enrollments.filter((learner) => (!status || learner.progress_status === status) && `${learner.name} ${learner.email}`.toLocaleLowerCase(i18n.language).includes(normalizedQuery));
  // The report contains only applicable lessons; do not infer visited content.
  const sectionsFor = (learner) => learner.sections.filter((section) => section.status === "published");
  const currentSection = (learner) => learner.progress_status === "completed" ? t("elearning.participation.completed") : sectionsFor(learner).find((section) => section.total_lessons > section.completed_lessons)?.name || t("elearning.progress.noApplicableLessons", { labels: labels.plural.lesson });
  const selected = enrollments.find((learner) => learner.id === selectedId);
  const activity = (value) => {
    const date = value ? new Date(value) : null;
    return date && !Number.isNaN(date.getTime()) ? new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium", timeStyle: "short" }).format(date) : t("elearning.progress.unavailableActivity");
  };
  if (loading) return <ELearningProgressSkeleton label={t("elearning.participation.loading")} />;
  return <section className="elearning-progress-page" aria-labelledby="elearning-progress-title">
    <header><h2 id="elearning-progress-title">{t("elearning.courses.tabs.progress")}</h2><p>{t("elearning.progress.calculationHelp", { lessons: labels.plural.lesson, sections: labels.plural.section })}</p></header>
    {error && <p role="alert" className="elearning-feedback is-error">{t(error)} <button className="ecommerce-secondary-button" onClick={retry}>{t("elearning.retry")}</button></p>}
    {data && !error && <>
      <dl className="elearning-progress-overview">{[["enrolled", data.learner_count], ["average", `${data.average_progress}%`], ["completed", data.completed_count], ["active", data.active_count], ["not_started", data.not_started_count]].map(([key, value]) => <div className="ecommerce-list-card" key={key}><dt>{t(key === "enrolled" ? "elearning.progress.enrolled" : `elearning.participation.${key}`)}</dt><dd>{value}</dd></div>)}</dl>
      {enrollments.length === 0 ? <div className="ecommerce-list-card ecommerce-empty-state"><h3>{t("elearning.participation.empty")}</h3><p>{t("elearning.participation.emptyHelp")}</p></div> : <>
        <div className="elearning-progress-tools"><label className="ecommerce-search"><Search size={18} aria-hidden="true" /><input type="search" aria-label={t("elearning.progress.search")} placeholder={t("elearning.progress.search")} value={query} onChange={(event) => setQuery(event.target.value)} /></label><label className="elearning-progress-filter">{t("elearning.progress.statusFilter")}<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">{t("elearning.progress.allStatuses")}</option>{["not_started", "active", "completed"].map((value) => <option key={value} value={value}>{t(`elearning.participation.${value}`)}</option>)}</select></label></div>
        <p className="elearning-course-description" role="status">{t("elearning.progress.results", { count: filtered.length, total: enrollments.length })}</p>
        <p className="elearning-course-description">{t("elearning.progress.currentHelp", { label: labels.section, lessons: labels.plural.lesson })}</p>
        {filtered.length === 0 ? <div className="ecommerce-list-card ecommerce-empty-state"><h3>{t("elearning.progress.noMatches")}</h3><button className="ecommerce-secondary-button" onClick={() => { setQuery(""); setStatus(""); }}>{t("elearning.progress.clearFilters")}</button></div> : <div className="ecommerce-list-card elearning-progress-table-wrap" role="region" aria-label={t("elearning.progress.table")} tabIndex={0}><table className="elearning-progress-table"><caption >{t("elearning.progress.table")}</caption><thead><tr>{[t("elearning.progress.learner"), t("elearning.progress.completion"), t("elearning.progress.currentSection", { label: labels.section }), t("elearning.progress.completedLessons", { labels: labels.plural.lesson }), t("elearning.courses.status"), t("elearning.progress.lastActivity"), t("elearning.progress.actions")].map((heading) => <th scope="col" key={heading}>{heading}</th>)}</tr></thead><tbody>{filtered.map((learner) => <tr key={learner.id}><th scope="row"><strong>{learner.name}</strong><small>{learner.email}</small></th><td><ProgressBar learner={learner} t={t} /></td><td>{currentSection(learner)}</td><td>{learner.completed_lessons} / {learner.total_lessons}</td><td><ProgressStatus learner={learner} t={t} /></td><td>{activity(learner.last_activity)}</td><td><button className="ecommerce-secondary-button" aria-label={t("elearning.progress.viewFor", { name: learner.name })} onClick={() => setSelectedId(learner.id)}>{t("elearning.progress.view")}</button></td></tr>)}</tbody></table></div>}
      </>}
    </>}
    {selected && !error && <LearnerProgressDialog learner={selected} course={course} onClose={() => setSelectedId(null)} />}
  </section>;
}

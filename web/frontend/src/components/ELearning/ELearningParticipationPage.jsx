import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { fetchCourseProgress } from "../../services/elearningParticipation";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import { ELearningStructureSkeleton } from "./ELearningSkeleton";

export default function ELearningParticipationPage({ courseId, tab }) {
  const { t } = useTranslation("dashboard");
  const { labels } = useELearningTerminology();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let cancelled = false;
    fetchCourseProgress(courseId).then((result) => { if (!cancelled) setData(result); })
      .catch((failure) => { if (!cancelled) setError(failure.status === 403 ? "elearning.forbidden" : failure.status === 503 ? "elearning.participation.unavailable" : "elearning.participation.loadError"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [courseId, reload]);
  if (loading) return <ELearningStructureSkeleton label={t("elearning.participation.loading")} />;
  return <section className="elearning-structure" aria-labelledby="elearning-participation-title">
    <header><h2 id="elearning-participation-title">{t(`elearning.courses.tabs.${tab}`)}</h2><p>{t("elearning.participation.help", { labels: labels.plural.lesson })}</p></header>
    {error && <p role="alert" className="elearning-feedback is-error">{t(error)} <button className="ecommerce-secondary-button" onClick={() => { setError(""); setLoading(true); setReload((value) => value + 1); }}>{t("elearning.retry")}</button></p>}
    {data && !error && <>
      <dl className="elearning-structure-summary"><div><dt>{t("elearning.courses.learners")}</dt><dd>{data.learner_count}</dd></div><div><dt>{t("elearning.participation.average")}</dt><dd>{data.average_progress}%</dd></div><div><dt>{t("elearning.participation.not_started")}</dt><dd>{data.not_started_count}</dd></div><div><dt>{t("elearning.participation.active")}</dt><dd>{data.active_count}</dd></div><div><dt>{t("elearning.participation.completed")}</dt><dd>{data.completed_count}</dd></div></dl>
      {data.enrollments.length === 0 && <div className="ecommerce-list-card ecommerce-empty-state"><h3>{t("elearning.participation.empty")}</h3><p>{t("elearning.participation.emptyHelp")}</p></div>}
      {data.enrollments.map((learner) => <article className="ecommerce-list-card elearning-section-card" key={learner.id}>
        <header><div><h3>{learner.name}</h3><p className="elearning-course-description">{learner.email}</p></div><span className="elearning-course-status">{t(`elearning.participation.${learner.progress_status}`)}</span></header>
        <div className="elearning-participation-progress"><span>{t("elearning.participation.completion", { completed: learner.completed_lessons, total: learner.total_lessons, labels: labels.plural.lesson })}</span><strong>{learner.progress_percent}%</strong><progress max="100" value={learner.progress_percent} aria-label={t("elearning.participation.progressFor", { name: learner.name })} /></div>
        <p>{t(`elearning.participation.access_${learner.access_source}`)}</p>
        {tab === "progress" && <details><summary>{t("elearning.participation.sectionProgress", { labels: labels.plural.section })}</summary><div className="elearning-participation-sections">{learner.sections.map((section) => <details key={section.id}><summary>{section.name} · {section.completed_lessons}/{section.total_lessons} · {section.progress_percent}%</summary><ul className="elearning-participation-lessons">{section.lessons.map((lesson) => <li key={lesson.id}><span>{lesson.name}</span><span>{t(lesson.completed ? "elearning.participation.completed" : "elearning.participation.not_started")}</span></li>)}</ul></details>)}</div></details>}
      </article>)}
    </>}
  </section>;
}

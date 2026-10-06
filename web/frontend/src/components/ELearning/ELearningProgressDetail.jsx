import { useTranslation } from "react-i18next";
import { CheckCircle2, Circle } from "lucide-react";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import ELearningDialog from "./ELearningDialog";

export function ProgressBar({ learner, t }) {
  return <div className="elearning-progress-value"><strong>{learner.progress_percent}%</strong><progress max="100" value={learner.progress_percent} aria-label={t("elearning.participation.progressFor", { name: learner.name })} /></div>;
}
export function ProgressStatus({ learner, t }) {
  return <span className={`elearning-course-status ${learner.progress_status === "completed" ? "is-published" : learner.progress_status === "active" ? "is-draft" : ""}`}>{t(`elearning.participation.${learner.progress_status}`)}</span>;
}

export function LearnerProgressDialog({ learner, course, onClose, children }) {
  const { t } = useTranslation("dashboard");
  const { labels } = useELearningTerminology();
  const sectionsFor = (record) => record.sections.filter((section) => section.status === "published");
  return <ELearningDialog title={t("elearning.progress.detailTitle", { name: learner.name })} closeLabel={t("elearning.courses.close")} onClose={onClose}>
      <div className="elearning-progress-detail"><p className="elearning-course-description">{course.name}</p><ProgressBar learner={learner} t={t} /><p>{t("elearning.participation.completion", { completed: learner.completed_lessons, total: learner.total_lessons, labels: labels.plural.lesson })}</p><ProgressStatus learner={learner} t={t} /><p>{t("elearning.progress.courseStatus")}: <span className={`elearning-course-status is-${course.status}`}>{t(`elearning.courses.statuses.${course.status}`)}</span></p>
        {children}
        {learner.completion && <p role="status">{t(`elearning.placements.${learner.completion.completed ? "completed" : "incomplete"}`, { label: labels.course })}{learner.completion.completed_at && ` · ${new Date(learner.completion.completed_at).toLocaleString()}`}</p>}
        {learner.assessment_results?.length > 0 && <section><h3>{t("elearning.content.types.assessment")}</h3>{learner.assessment_results.map(result => <div className="ecommerce-list-card" key={result.placement_id || result.assessment_id}><h4>{result.title}</h4>{result.placement_type && <small>{t("elearning.placements.heading", { label: labels[result.placement_type] })}</small>}<p>{t("elearning.assessment.attempts")}: {result.attempts} · {t("elearning.assessment.best")}: {result.best_score ?? "—"}% · {t(`elearning.assessment.${result.passed ? "passed" : "notPassed"}`)}</p><p>{t("elearning.assessment.lastAttempt")}: {result.last_attempt ? new Date(result.last_attempt).toLocaleString() : "—"}</p></div>)}</section>}
        <h3>{t("elearning.participation.sectionProgress", { labels: labels.plural.section })}</h3>
        {sectionsFor(learner).length === 0 && <p>{t("elearning.progress.noApplicableLessons", { labels: labels.plural.lesson })}</p>}
        {sectionsFor(learner).map((section) => <section className="ecommerce-list-card elearning-progress-section" key={section.id}><header><h4>{labels.section}: {section.name}</h4><strong>{section.progress_percent}%</strong></header><p className="elearning-course-description">{t("elearning.participation.completion", { completed: section.completed_lessons, total: section.total_lessons, labels: labels.plural.lesson })}</p>{section.lessons.length === 0 ? <p>{t("elearning.progress.noApplicableLessons", { labels: labels.plural.lesson })}</p> : <ul className="elearning-participation-lessons">{section.lessons.map((lesson) => <li key={lesson.id}>{lesson.completed ? <CheckCircle2 size={18} aria-hidden="true" /> : <Circle size={18} aria-hidden="true" />}<span>{labels.lesson}: {lesson.name}</span><span className="elearning-course-description">{t(lesson.completed ? "elearning.participation.completed" : "elearning.participation.not_started")}</span></li>)}</ul>}</section>)}
      </div><footer><button className="ecommerce-secondary-button" onClick={onClose}>{t("elearning.courses.close")}</button></footer>
  </ELearningDialog>;
}

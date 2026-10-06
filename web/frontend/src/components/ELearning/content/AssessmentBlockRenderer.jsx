import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { loadAssessment, learnerAssessment, startAssessment, submitAssessment } from "../../../services/elearningAssessments";
import ELearningSkeleton from "../ELearningSkeleton";
import AssessmentQuestions from "./AssessmentQuestions";
export default function AssessmentBlockRenderer({ block, context = "author", courseId, lessonId, onAssessmentChange }) {
  const { t } = useTranslation("dashboard");
  const [data, setData] = useState(null), [answers, setAnswers] = useState({}), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  useEffect(() => {
    if (context === "author") return;
    let active = true;
    (context === "preview" ? loadAssessment(courseId, lessonId, block.id, true) : learnerAssessment(courseId, lessonId, block.id)).then(value => { if (active) setData(value); }).catch(() => { if (active) setError(t("elearning.assessment.loadError")); });
    return () => { active = false; };
  }, [context, courseId, lessonId, block.id, reload, t]);
  async function run(submit = false) {
    setBusy(true); setError("");
    try {
      const value = submit ? await submitAssessment(courseId, lessonId, block.id, data.attempt.id, answers) : await startAssessment(courseId, lessonId, block.id);
      setData(value); setAnswers({});
      if (submit) await onAssessmentChange?.();
    } catch (failure) { setError(failure.detail?.message || t("elearning.assessment.saveError")); } finally { setBusy(false); }
  }
  const assessment = data?.assessment || block.assessment;
  if (context !== "author" && !data && !error) return <ELearningSkeleton variant="lesson" label={t("elearning.assessment.loading")} />;
  const attempt = data?.attempt;
  return <div className="assessment-runtime" aria-busy={busy}>
    <h3>{assessment?.title}</h3><p>{attempt?.instructions ?? assessment?.instructions}</p>
    <p>{t("elearning.assessment.questionCount", { count: assessment?.question_count || data?.questions?.length || 0 })} · {t("elearning.assessment.passing")}: {attempt?.passing_score ?? assessment?.passing_score}% · {t("elearning.assessment.maxAttempts")}: {assessment?.max_attempts ?? t("elearning.assessment.unlimited")}</p>
    {error && <p role="alert">{error} <button type="button" onClick={() => { setError(""); setReload(n => n + 1); }}>{t("elearning.retry")}</button></p>}
    {context === "preview" && data && <AssessmentQuestions questions={data.questions} answers={answers} onChange={(id, value) => setAnswers(previous => ({ ...previous, [id]: value }))} />}
    {context === "learner" && data && <>
      {attempt?.status === "submitted" && <div role="status"><strong>{t("elearning.assessment.score")}: {attempt.score_percentage}% — {t(`elearning.assessment.${attempt.passed ? "passed" : "notPassed"}`)}</strong><p>{t("elearning.assessment.attempt")} {attempt.attempt_number}{attempt.max_attempts ? ` / ${attempt.max_attempts}` : ""}</p></div>}
      {attempt?.status === "in_progress" ? <form onSubmit={event => { event.preventDefault(); run(true); }}><AssessmentQuestions questions={attempt.questions} answers={answers} onChange={(id, value) => setAnswers(previous => ({ ...previous, [id]: value }))} disabled={busy} /><button className="ecommerce-primary-button" disabled={busy || attempt.questions.some(q => !answers[q.id] || (["matching", "listen_match"].includes(q.type) && Object.values(answers[q.id].matches || {}).filter(Boolean).length !== q.config.prompts.length))}>{t("elearning.assessment.submit")}</button></form> : data.summary.remaining_attempts === 0 ? <p role="status">{t("elearning.assessment.limit")}</p> : <button className="ecommerce-primary-button" disabled={busy} onClick={() => run()}>{t(`elearning.assessment.${attempt ? "retry" : "start"}`)}</button>}
      <p>{t("elearning.assessment.attempts")}: {data.summary.attempts} {data.summary.remaining_attempts != null && `· ${t("elearning.assessment.remaining")}: ${data.summary.remaining_attempts}`}</p>
      <p>{t("elearning.assessment.best")}: {data.summary.best_score ?? "—"}{data.summary.best_score != null ? "%" : ""} {data.summary.passed && `· ${t("elearning.assessment.passed")}`}</p>
    </>}
  </div>;
}

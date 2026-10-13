import LearningErrorNotice from "../LearningErrorNotice";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { checkPracticeAnswer, loadAssessment, learnerAssessment, startAssessment, submitAssessment } from "../../../services/elearningAssessments";
import ListenMatchActivity, { ListenMatchResults } from "./ListenMatchActivity";
import { ChooseBestResponse, SpeakNow } from "./PracticeActivities";
import ExamRunner from "./ExamRunner";
import { useLearningExperience } from "../LearningExperienceContext";
import ELearningSkeleton from "../ELearningSkeleton";
import AssessmentQuestions from "./AssessmentQuestions";
export default function AssessmentBlockRenderer({ block, context = "author", courseId, lessonId, onAssessmentChange }) {
  const { t } = useTranslation("dashboard");
  const [data, setData] = useState(null), [answers, setAnswers] = useState({}), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [reload, setReload] = useState(0), [listenResult, setListenResult] = useState(null);
  const enhanced = useLearningExperience().lessonComponents === true;
  useEffect(() => {
    if (context === "author") return;
    let active = true;
    (context === "preview" ? loadAssessment(courseId, lessonId, block.id, true) : learnerAssessment(courseId, lessonId, block.id)).then(value => { if (active) setData(value); }).catch(() => { if (active) setError(t("elearning.assessment.loadError")); });
    return () => { active = false; };
  }, [context, courseId, lessonId, block.id, reload, t]);
  async function run(submit = false, submitted = answers) {
    setBusy(true); setError("");
    if (!submit) setListenResult(null);
    try {
      const value = submit ? await submitAssessment(courseId, lessonId, block.id, data.attempt.id, submitted) : await startAssessment(courseId, lessonId, block.id);
      setData(value); setAnswers({});
      if (submit) await onAssessmentChange?.();
    } catch { setError(t("elearning.assessment.saveError")); } finally { setBusy(false); }
  }
  const assessment = data?.assessment || block.assessment;
  if (context !== "author" && !data && !error) return <ELearningSkeleton variant="lesson" label={t("elearning.assessment.loading")} />;
  const attempt = data?.attempt;
  const practice = (attempt?.activity_mode ?? assessment?.activity_mode) === "practice";
  // Opt-in Listen & Match: practice activities made only of picture questions.
  const sequence = enhanced && context === "learner" && practice && attempt?.status === "in_progress" && attempt.questions?.length > 0;
  const allOf = type => sequence && attempt.questions.every(q => q.type === type);
  const listenMatch = allOf("picture_listen"), bestResponse = allOf("multiple_choice"), speakNow = allOf("speaking_practice");
  const check = (question, option) => checkPracticeAnswer(courseId, lessonId, block.id, attempt.id, question, option);
  const finish = result => { if (result.total) setListenResult(result); run(true, result.answers); };
  return <div className="assessment-runtime" aria-busy={busy}>
    <h3>{assessment?.title}</h3><p>{attempt?.instructions ?? assessment?.instructions}</p>
    <p>{t("elearning.assessment.questionCount", { count: assessment?.question_count || data?.questions?.length || 0 })} · {practice ? t("elearning.assessment.practice") : `${t("elearning.assessment.passing")}: ${attempt?.passing_score ?? assessment?.passing_score}%`} · {t("elearning.assessment.maxAttempts")}: {assessment?.max_attempts ?? t("elearning.assessment.unlimited")}</p>
    {error && <LearningErrorNotice as="p">{error} <button type="button" onClick={() => { setError(""); setReload(n => n + 1); }}>{t("elearning.retry")}</button></LearningErrorNotice>}
    {context === "preview" && data && <AssessmentQuestions questions={data.questions} answers={answers} onChange={(id, value) => setAnswers(previous => ({ ...previous, [id]: value }))} />}
    {context === "learner" && data && <>
      {attempt?.status === "pending_review" && <p role="status"><strong>{t("elearning.assessment.pendingReview")}</strong></p>}
      {attempt?.status === "submitted" && <div role="status"><strong>{practice ? t("elearning.assessment.practiceComplete") : `${t("elearning.assessment.score")}: ${attempt.score_percentage}% — ${t(`elearning.assessment.${attempt.passed ? "passed" : "notPassed"}`)}`}</strong><p>{t("elearning.assessment.attempt")} {attempt.attempt_number}{attempt.max_attempts ? ` / ${attempt.max_attempts}` : ""}</p></div>}
      {listenResult && attempt?.status === "submitted" && <ListenMatchResults correct={listenResult.correct} total={listenResult.total} />}
      {listenMatch ? <ListenMatchActivity questions={attempt.questions} disabled={busy} check={check} onFinish={finish} />
      : bestResponse ? <ChooseBestResponse title={assessment?.title} questions={attempt.questions} disabled={busy} check={check} onFinish={finish} />
      : speakNow ? <SpeakNow questions={attempt.questions} disabled={busy} onFinish={finish} />
      : enhanced && !practice && attempt?.status === "in_progress" ? <ExamRunner attempt={attempt} answers={answers} busy={busy} onChange={(id, value) => setAnswers(previous => ({ ...previous, [id]: value }))} onSubmit={() => run(true)} />
      : attempt?.status === "in_progress" ? <form onSubmit={event => { event.preventDefault(); run(true); }}><AssessmentQuestions recordings={attempt.recordings} attemptId={attempt.id} questions={attempt.questions} answers={answers} onChange={(id, value) => setAnswers(previous => ({ ...previous, [id]: value }))} disabled={busy} /><button className="ecommerce-primary-button" disabled={busy || attempt.questions.some(q => !answers[q.id] || (["matching", "listen_match"].includes(q.type) && Object.values(answers[q.id].matches || {}).filter(Boolean).length !== q.config.prompts.length))}>{t("elearning.assessment.submit")}</button></form> : attempt?.status === "pending_review" ? <button className="ecommerce-secondary-button" disabled={busy} onClick={() => setReload(n => n + 1)}>{t("elearning.retry")}</button> : data.summary.remaining_attempts === 0 ? <p role="status">{t("elearning.assessment.limit")}</p> : <button className="ecommerce-primary-button" disabled={busy} onClick={() => run()}>{t(`elearning.assessment.${attempt ? "retry" : "start"}`)}</button>}
      {attempt?.status === "submitted" && attempt.feedback?.length > 0 && <ul aria-label={t("elearning.assessment.answerFeedback")}>{attempt.feedback.map(value => <li key={value.question_id}><strong>{attempt.questions?.find(q => q.id === value.question_id)?.prompt}</strong><p>{value.correct != null ? t(`elearning.assessment.${value.correct ? "correct" : "tryAgain"}`) : value.points != null ? `${value.points} / ${value.maximum}` : t("elearning.assessment.practiceComplete")}</p>{value.feedback && <p>{value.feedback}</p>}</li>)}</ul>}
      <p>{t("elearning.assessment.attempts")}: {data.summary.attempts} {data.summary.remaining_attempts != null && `· ${t("elearning.assessment.remaining")}: ${data.summary.remaining_attempts}`}</p>
      {!practice && <p>{t("elearning.assessment.best")}: {data.summary.best_score ?? "—"}{data.summary.best_score != null ? "%" : ""} {data.summary.passed && `· ${t("elearning.assessment.passed")}`}</p>}
    </>}
  </div>;
}

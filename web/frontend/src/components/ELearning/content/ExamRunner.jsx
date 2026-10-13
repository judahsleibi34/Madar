import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowLeft, ArrowRight, CheckCircle2, Circle, Clock, ListChecks } from "lucide-react";
import AssessmentQuestions from "./AssessmentQuestions";
import { answered } from "../../../utils/examAnswers";
import "../../../styles/lesson-components.css";

const clock = seconds => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

/**
 * EH / Exam screen: one question per page, a question map, time spent (the book
 * sets no time limit), and a review step. Answers reach the server only on
 * submit; correctness is never shown before then.
 */
export default function ExamRunner({ attempt, answers, onChange, onSubmit, busy }) {
  const { t } = useTranslation("dashboard");
  const questions = attempt.questions, total = questions.length;
  const [index, setIndex] = useState(0), [reviewing, setReviewing] = useState(false);
  const started = Date.parse(attempt.started_at || "") || null;
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const elapsed = started ? Math.max(0, Math.floor((now - started) / 1000)) : null;
  const done = questions.filter(q => answered(q, answers[q.id])).length;
  const go = next => { setReviewing(false); setIndex(Math.min(total - 1, Math.max(0, next))); };
  return <section className="exam-runner" aria-label={t("elearning.exams.screen")}>
    <header className="exam-runner-header">
      <strong>{reviewing ? t("elearning.exams.review") : t("elearning.listenMatch.questionOf", { current: index + 1, total })}</strong>
      <span><ListChecks size={16} aria-hidden="true" />{t("elearning.exams.answeredCount", { done, total })}</span>
      {elapsed !== null && <span role="timer" aria-live="off"><Clock size={16} aria-hidden="true" />{t("elearning.exams.timeSpent")}: <span dir="ltr">{clock(elapsed)}</span></span>}
    </header>
    <nav className="exam-question-map" aria-label={t("elearning.exams.questionMap")}>
      {questions.map((q, i) => { const isDone = answered(q, answers[q.id]); return <button type="button" key={q.id} aria-current={!reviewing && i === index ? "step" : undefined} className={isDone ? "is-answered" : ""} onClick={() => go(i)}
        aria-label={`${t("elearning.assessment.question", { number: i + 1 })} · ${t(isDone ? "elearning.exams.answered" : "elearning.exams.unanswered")}`}>{i + 1}</button>; })}
    </nav>
    <form noValidate onSubmit={event => { event.preventDefault(); if (reviewing) onSubmit(); else setReviewing(true); }}>
      <AssessmentQuestions recordings={attempt.recordings} attemptId={attempt.id} questions={questions} answers={answers} onChange={onChange} disabled={busy} visibleIndex={reviewing ? -1 : index} />
      {reviewing && <div className="exam-review" role="status">
        <p>{t("elearning.exams.reviewHelp", { done, total })}</p>
        <ul>{questions.map((q, i) => { const isDone = answered(q, answers[q.id]); return <li key={q.id}><button type="button" onClick={() => go(i)}>{isDone ? <CheckCircle2 size={16} aria-hidden="true" /> : <Circle size={16} aria-hidden="true" />}{t("elearning.assessment.question", { number: i + 1 })} · {t(isDone ? "elearning.exams.answered" : "elearning.exams.unanswered")}</button></li>; })}</ul>
      </div>}
      <footer className="exam-runner-actions">
        <button type="button" className="ecommerce-secondary-button" disabled={busy || (!reviewing && index === 0)} onClick={() => go(reviewing ? total - 1 : index - 1)}><ArrowLeft size={16} aria-hidden="true" />{t("elearning.exams.previous")}</button>
        {!reviewing && index < total - 1 && <button type="button" className="ecommerce-secondary-button" onClick={() => go(index + 1)}>{t("elearning.exams.next")}<ArrowRight size={16} aria-hidden="true" /></button>}
        {!reviewing && index === total - 1 && <button type="submit" className="ecommerce-primary-button">{t("elearning.exams.reviewAnswers")}</button>}
        {reviewing && <button type="submit" className="ecommerce-primary-button" disabled={busy || done < total}>{t("elearning.assessment.submit")}</button>}
      </footer>
    </form>
  </section>;
}

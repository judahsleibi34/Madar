import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Lock, PlayCircle, RotateCcw, XCircle } from "lucide-react";
import { examState } from "../../../utils/examState";
import "../../../styles/lesson-components.css";


/** EH / Exam Card: Locked, Available, Passed (score), Not passed (score + Retake). */
export default function ExamCard({ exam, href, current = false }) {
  const { t } = useTranslation("dashboard");
  const state = examState(exam);
  const Icon = { locked: Lock, available: PlayCircle, passed: CheckCircle2, failed: XCircle }[state];
  const score = exam.best_score != null ? `${exam.best_score}%` : "";
  return <article className={`exam-card is-${state}${current ? " is-current" : ""}`}>
    <div className="exam-card-main">
      <h3>{state === "locked" || !href ? exam.title : <Link to={href} aria-current={current ? "page" : undefined}>{exam.title}</Link>}</h3>
      <span className="exam-card-status"><Icon size={18} aria-hidden="true" />{t(`elearning.exams.${state}`, { score })}</span>
      {state === "locked" && <p>{t("elearning.exams.lockedHelp")}</p>}
      {exam.passing_score != null && <p className="exam-card-pass">{t("elearning.exams.passMark", { score: exam.passing_score })}</p>}
    </div>
    {state === "available" && href && <Link className="ecommerce-primary-button" to={href}>{t("elearning.exams.start")}</Link>}
    {state === "failed" && href && <Link className="ecommerce-primary-button" to={href}><RotateCcw size={16} aria-hidden="true" />{t("elearning.exams.retake")}</Link>}
  </article>;
}

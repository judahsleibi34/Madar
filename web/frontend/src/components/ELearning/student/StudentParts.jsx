import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Circle, CircleDot, Clock, Lock, XCircle } from "lucide-react";
import "../../../styles/student-dashboard.css";

/** EH / Stat Card */
export function StatCard({ icon: Icon, label, value, detail, to, children }) {
  const body = <>
    <span className="stat-card-label">{Icon && <Icon size={18} aria-hidden="true" />}{label}</span>
    <strong className="stat-card-value">{value}</strong>
    {detail && <span className="stat-card-detail">{detail}</span>}
    {children}
  </>;
  return to ? <Link className="stat-card is-link" to={to}>{body}</Link> : <div className="stat-card">{body}</div>;
}

/** EH / Progress Bar: fills from the reading start, so right-to-left in Arabic. */
export function ProgressBar({ value, max = 100, label }) {
  const percent = max > 0 ? Math.max(0, Math.min(100, (Number(value) / max) * 100)) : 0;
  return <div className="eh-progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={max} aria-valuenow={Number(value) || 0}><span style={{ width: `${percent}%` }} /></div>;
}

const PILL = {
  completed: [CheckCircle2, "is-teal"], available: [Circle, "is-indigo"], inProgress: [CircleDot, "is-amber"], locked: [Lock, "is-gray"],
  pending: [Clock, "is-amber"], submitted: [Clock, "is-blue"], under_review: [Clock, "is-blue"], processing: [Clock, "is-blue"],
  approved: [CheckCircle2, "is-green"], paid: [CheckCircle2, "is-green"], earned: [CheckCircle2, "is-green"], eligible: [CheckCircle2, "is-green"],
  not_approved: [XCircle, "is-red"], rejected: [XCircle, "is-red"], reversed: [XCircle, "is-red"], suspended: [XCircle, "is-red"],
};

/** EH / Status Pill: every status is an icon + text. */
export function StatusPill({ status, children }) {
  const [Icon, tone] = PILL[status] || [Circle, "is-gray"];
  return <span className={`status-pill ${tone}`}><Icon size={15} aria-hidden="true" />{children}</span>;
}

/** EH / Level Card: Locked, Available, In Progress (with %), Completed. */
export function LevelCard({ level, to }) {
  const { t } = useTranslation("dashboard");
  const title = String(level.name || "").replace(/^Level\s+\d+\s*[—-]\s*/i, "");
  const topics = (level.lessons || []).length;
  const body = <>
    <header><span className="level-card-number">{t("elearning.student.levelNumber", { number: level.number })}</span>{level.cefr && <span className="cefr-badge" lang="en">{level.cefr}</span>}</header>
    <h3 lang="en" dir="auto">{title}</h3>
    <StatusPill status={level.state}>{level.state === "inProgress" ? t("elearning.student.levelInProgress", { percent: Math.round(Number(level.progress_percent) || 0) }) : t(`elearning.student.level_${level.state}`)}</StatusPill>
    <ProgressBar value={level.progress_percent || 0} label={t("elearning.student.levelProgress")} />
    <span className="level-card-topics">{t("elearning.student.topicCount", { count: topics })}</span>
  </>;
  return level.state === "locked" || !to ? <article className={`level-card is-${level.state}`}>{body}</article> : <Link className={`level-card is-${level.state}`} to={to}>{body}</Link>;
}

export function StudentPage({ title, intro, children }) {
  return <section className="student-page"><header className="student-page-header"><h1>{title}</h1>{intro && <p>{intro}</p>}</header>{children}</section>;
}

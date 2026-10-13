import { useTranslation } from "react-i18next";
import { CheckCircle2, Circle, CircleDot, Lock } from "lucide-react";

// Mirrors TopicStatus in ELearningPlayer for the gallery.
export default function TopicRowsSample() {
  const { t } = useTranslation("dashboard");
  const rows = [["Introducing Yourself", "completed", CheckCircle2], ["Greetings and Saying Goodbye", "current", CircleDot], ["Talking About Your Family", "available", Circle], ["Numbers, Phone Numbers and Email Addresses", "locked", Lock]];
  return <ol className="elearning-player-outline" style={{ display: "grid", gap: 10, padding: 16, background: "var(--theme-surface)", borderRadius: 16, listStyle: "none" }}>
    {rows.map(([name, status, Icon]) => <li key={name} style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}><span className={`topic-row-status is-${status}`}><Icon size={16} aria-hidden="true" />{t(`elearning.topicStatus.${status}`)}</span><span lang="en">{name}</span></li>)}
  </ol>;
}

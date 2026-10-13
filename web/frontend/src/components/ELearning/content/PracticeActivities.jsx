import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, Mic, MessagesSquare, X } from "lucide-react";
import SpeakingRecorder from "./SpeakingRecorder";
import "../../../styles/lesson-components.css";

/**
 * EH / Choose the Best Response: one situation at a time; each choice is checked
 * by the server for this practice attempt only. Score = right on the first try.
 */
export function ChooseBestResponse({ title, questions, check, onFinish, disabled = false }) {
  const { t } = useTranslation("dashboard");
  const [index, setIndex] = useState(0), [state, setState] = useState({}), [firstTry, setFirstTry] = useState({}), [answers, setAnswers] = useState({});
  const [busy, setBusy] = useState(false), [error, setError] = useState(false);
  const question = questions[index], current = state[question.id] || {}, total = questions.length;
  async function choose(option) {
    if (busy || disabled || current.correct) return;
    setBusy(true); setError(false);
    try {
      const { correct } = await check(question.id, option.id);
      setState(previous => ({ ...previous, [question.id]: { selected: option.id, correct } }));
      setFirstTry(previous => (question.id in previous ? previous : { ...previous, [question.id]: correct }));
      if (correct) setAnswers(previous => ({ ...previous, [question.id]: { option_id: option.id } }));
    } catch { setError(true); } finally { setBusy(false); }
  }
  function next() {
    if (index + 1 < total) { setIndex(index + 1); return; }
    onFinish({ answers, correct: Object.values(firstTry).filter(Boolean).length, total });
  }
  return <section className="practice-activity" aria-labelledby={`best-response-${question.id}`}>
    <header className="listen-match-header">
      <h4 id={`best-response-${question.id}`}><MessagesSquare size={20} aria-hidden="true" /> {title || t("elearning.practice.bestResponse")}</h4>
      <span className="listen-match-counter">{t("elearning.listenMatch.questionOf", { current: index + 1, total })}</span>
    </header>
    <p className="practice-situation" lang="en" dir="ltr">{question.prompt}</p>
    <div className="practice-options" role="group" aria-label={t("elearning.practice.responses")}>
      {question.config.options.map(option => {
        const chosen = current.selected === option.id, tone = chosen ? (current.correct ? "is-correct" : "is-incorrect") : "";
        return <button type="button" key={option.id} className={`practice-option ${tone}`} aria-pressed={chosen} disabled={disabled || busy || current.correct} onClick={() => choose(option)}>
          <span lang="en" dir="ltr">{option.label}</span>
          {chosen && (current.correct ? <Check size={20} aria-hidden="true" /> : <X size={20} aria-hidden="true" />)}
        </button>;
      })}
    </div>
    <div aria-live="polite" className="listen-match-feedback">
      {current.selected && <p className={current.correct ? "is-correct" : "is-incorrect"}>{current.correct ? <Check size={18} aria-hidden="true" /> : <X size={18} aria-hidden="true" />}{t(current.correct ? "elearning.listenMatch.correct" : "elearning.practice.incorrect")}</p>}
      {error && <p className="is-incorrect">{t("elearning.assessment.saveError")}</p>}
    </div>
    {current.correct && <button type="button" className="ecommerce-primary-button listen-match-continue" onClick={next}>{t("elearning.listenMatch.continue")}</button>}
  </section>;
}

/** EH / Speak Now: record, stop, listen back, then CONTINUE. Nothing is scored automatically. */
export function SpeakNow({ questions, onFinish, disabled = false }) {
  const { t } = useTranslation("dashboard");
  const [index, setIndex] = useState(0), [recorded, setRecorded] = useState({});
  const question = questions[index], total = questions.length;
  function next() {
    if (index + 1 < total) { setIndex(index + 1); return; }
    onFinish({ answers: Object.fromEntries(questions.map(item => [item.id, { finished: true }])) });
  }
  return <section className="practice-activity speak-now" aria-labelledby={`speak-now-${question.id}`}>
    <header className="listen-match-header">
      <h4 id={`speak-now-${question.id}`}><Mic size={20} aria-hidden="true" /> {t("elearning.practice.speakNow")}</h4>
      {total > 1 && <span className="listen-match-counter">{t("elearning.listenMatch.questionOf", { current: index + 1, total })}</span>}
    </header>
    <p className="practice-situation" lang="en" dir="ltr">{question.prompt}</p>
    <SpeakingRecorder key={question.id} maxDuration={question.config.max_duration_seconds} maxBytes={question.config.max_size_bytes} disabled={disabled}
      onChange={value => setRecorded(previous => ({ ...previous, [question.id]: value instanceof Blob }))} />
    <p className="practice-note">{t("elearning.practice.speakNote")}</p>
    <button type="button" className="ecommerce-primary-button listen-match-continue" disabled={disabled || !recorded[question.id]} onClick={next}>{t("elearning.listenMatch.continue")}</button>
  </section>;
}

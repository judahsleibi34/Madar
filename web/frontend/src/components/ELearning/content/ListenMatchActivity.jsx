import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, ImageOff, RotateCcw, Volume2, X } from "lucide-react";
import { getApiUrl } from "../../../utils/apiClient";
import "../../../styles/lesson-components.css";

const MANAGED_IMAGE = /^\/uploads\/tenant_[1-9][0-9]*\/builder_assets\/[a-f0-9]{32}\.(png|jpg|jpeg|webp)$/;
const MANAGED_AUDIO = /^\/uploads\/tenant_[1-9][0-9]*\/builder_assets\/[a-f0-9]{32}\.(mp3|wav)$/;

/**
 * EH / Listen & Match: LISTEN → hear → choose one of four photos (no text).
 * Each choice is checked by the server for this practice attempt only; the
 * score counts questions answered correctly on the first try.
 */
export default function ListenMatchActivity({ questions, check, onFinish, disabled = false }) {
  const { t } = useTranslation("dashboard");
  const audio = useRef(null);
  const [index, setIndex] = useState(0), [state, setState] = useState({}), [busy, setBusy] = useState(false), [error, setError] = useState(false);
  const [firstTry, setFirstTry] = useState({}), [answers, setAnswers] = useState({});
  const question = questions[index];
  const current = state[question.id] || {};
  const audioUrl = question.config?.media?.url;
  const total = questions.length;
  async function listen(again = false) {
    const element = audio.current; if (!element) return;
    if (again) element.currentTime = 0;
    try { await element.play(); } catch { /* The learner can press LISTEN again. */ }
  }
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
  return <section className="listen-match" aria-labelledby={`listen-match-${question.id}`}>
    <header className="listen-match-header">
      <h4 id={`listen-match-${question.id}`}>{t("elearning.listenMatch.title")}</h4>
      <span className="listen-match-counter">{t("elearning.listenMatch.questionOf", { current: index + 1, total })}</span>
    </header>
    <div className="lesson-audio-controls">
      {audioUrl && MANAGED_AUDIO.test(audioUrl) ? <>
        <audio ref={audio} src={getApiUrl(audioUrl)} preload="auto" />
        <button type="button" className="lesson-audio-listen" onClick={() => listen(false)}><Volume2 size={22} aria-hidden="true" />{t("elearning.content.listen")}</button>
        <button type="button" className="lesson-audio-again" onClick={() => listen(true)}><RotateCcw size={20} aria-hidden="true" />{t("elearning.content.playAgain")}</button>
      </> : <p className="listen-match-pending" role="status">{t("elearning.content.audioPending")}</p>}
    </div>
    <p className="listen-match-question">{t("elearning.listenMatch.whatDidYouHear")}</p>
    <div className="listen-match-grid" role="group" aria-label={t("elearning.listenMatch.pictures")}>
      {question.config.options.map((option, position) => {
        const chosen = current.selected === option.id;
        const tone = chosen ? (current.correct ? "is-correct" : "is-incorrect") : "";
        const image = option.media?.url && MANAGED_IMAGE.test(option.media.url) ? getApiUrl(option.media.url) : null;
        return <button type="button" key={option.id} className={`listen-match-option ${tone}`} disabled={disabled || busy || current.correct}
          aria-label={`${t("elearning.listenMatch.picture", { number: position + 1 })}${option.alt ? `: ${option.alt}` : ""}`} aria-pressed={chosen} onClick={() => choose(option)}>
          {image ? <img src={image} alt="" loading="lazy" /> : <span className="listen-match-photo-pending"><ImageOff size={28} aria-hidden="true" /></span>}
          {chosen && <span className="listen-match-mark" aria-hidden="true">{current.correct ? <Check size={22} /> : <X size={22} />}</span>}
        </button>;
      })}
    </div>
    <div aria-live="polite" className="listen-match-feedback">
      {current.selected && <p className={current.correct ? "is-correct" : "is-incorrect"}>{current.correct ? <Check size={18} aria-hidden="true" /> : <X size={18} aria-hidden="true" />}{t(current.correct ? "elearning.listenMatch.correct" : "elearning.listenMatch.incorrect")}</p>}
      {error && <p className="is-incorrect">{t("elearning.assessment.saveError")}</p>}
    </div>
    {current.correct && <button type="button" className="ecommerce-primary-button listen-match-continue" onClick={next}>{t("elearning.listenMatch.continue")}</button>}
  </section>;
}

export function ListenMatchResults({ correct, total, onRetry, retryDisabled }) {
  const { t } = useTranslation("dashboard");
  return <div className="listen-match-results" role="status">
    <strong>{t("elearning.listenMatch.score", { correct, total })}</strong>
    {onRetry && <button type="button" className="lesson-audio-again" onClick={onRetry} disabled={retryDisabled}><RotateCcw size={20} aria-hidden="true" />{t("elearning.listenMatch.retry")}</button>}
  </div>;
}

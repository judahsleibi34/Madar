import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Gauge, Headphones, Pause, RotateCcw, Volume2 } from "lucide-react";
import LearningErrorNotice from "../LearningErrorNotice";
import { parseDialogue } from "../../../utils/lessonDialogue";
import "../../../styles/lesson-components.css";

const SPEEDS = [0.75, 1];
const formatTime = seconds => {
  const value = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0;
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, "0")}`;
};

export function Transcript({ transcript, id, hidden }) {
  const dialogue = parseDialogue(transcript);
  return <div id={id} hidden={hidden} className="lesson-transcript" lang="en" dir="ltr">
    {dialogue ? dialogue.map((turn, index) => <p key={index} className={`lesson-transcript-turn is-${turn.side}`}><strong>{turn.speaker}</strong><span>{turn.text}</span></p>)
      : <p className="lesson-transcript-prose">{transcript}</p>}
  </div>;
}

/** EH / Audio Player: LISTEN, PLAY AGAIN, 0.75x / 1x, SHOW TRANSCRIPT. */
export default function LessonAudioPlayer({ src, title, transcript, caption, onError }) {
  const { t } = useTranslation("dashboard");
  const audio = useRef(null), transcriptId = useId();
  const [playing, setPlaying] = useState(false), [speed, setSpeed] = useState(1), [failed, setFailed] = useState(false);
  const [time, setTime] = useState({ current: 0, duration: 0 }), [transcriptVisible, setTranscriptVisible] = useState(false);
  useEffect(() => { if (audio.current) audio.current.playbackRate = speed; }, [speed]);
  if (!src) {
    return <div className="lesson-audio is-pending" role="status">
      <Headphones size={28} aria-hidden="true" />
      <div><strong>{title || t("elearning.content.audioPendingTitle")}</strong><p>{t("elearning.content.audioPending")}</p></div>
    </div>;
  }
  async function play(fromStart = false) {
    const element = audio.current; if (!element) return;
    if (!fromStart && playing) { element.pause(); return; }
    if (fromStart) element.currentTime = 0;
    element.playbackRate = speed;
    try { await element.play(); } catch { setPlaying(false); }
  }
  const progress = time.duration ? Math.min(100, (time.current / time.duration) * 100) : 0;
  return <div className="lesson-audio">
    <audio ref={audio} src={src} preload="metadata" aria-label={title}
      onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)}
      onLoadedMetadata={event => { setFailed(false); setTime({ current: 0, duration: event.currentTarget.duration }); }}
      onTimeUpdate={event => setTime({ current: event.currentTarget.currentTime, duration: event.currentTarget.duration })}
      onError={() => { setFailed(true); onError?.(); }} />
    {title && <strong className="lesson-audio-title">{title}</strong>}
    <div className="lesson-audio-controls">
      <button type="button" className="lesson-audio-listen" onClick={() => play(false)} disabled={failed} aria-pressed={playing}>
        {playing ? <Pause size={22} aria-hidden="true" /> : <Volume2 size={22} aria-hidden="true" />}{t(playing ? "elearning.content.pause" : "elearning.content.listen")}
      </button>
      <button type="button" className="lesson-audio-again" onClick={() => play(true)} disabled={failed}>
        <RotateCcw size={20} aria-hidden="true" />{t("elearning.content.playAgain")}
      </button>
      <span className="lesson-audio-speed" role="group" aria-label={t("elearning.content.speed")}>
        <Gauge size={18} aria-hidden="true" />
        {SPEEDS.map(value => <button type="button" key={value} aria-pressed={speed === value} onClick={() => setSpeed(value)}>{value}x</button>)}
      </span>
    </div>
    <div className="lesson-audio-progress" role="progressbar" aria-label={t("elearning.content.audioProgress")} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress)}>
      <span style={{ width: `${progress}%` }} />
    </div>
    <small className="lesson-audio-time" dir="ltr">{formatTime(time.current)} / {formatTime(time.duration)}</small>
    {failed && <LearningErrorNotice as="p">{t("elearning.content.mediaError")}</LearningErrorNotice>}
    {caption && <p className="lesson-audio-caption">{caption}</p>}
    {transcript && <>
      <button type="button" className="lesson-audio-transcript-toggle" aria-expanded={transcriptVisible} aria-controls={transcriptId} onClick={() => setTranscriptVisible(value => !value)}>
        {t(`elearning.content.${transcriptVisible ? "hideTranscript" : "showTranscript"}`)}
      </button>
      <Transcript transcript={transcript} id={transcriptId} hidden={!transcriptVisible} />
    </>}
  </div>;
}

import { useTranslation } from "react-i18next";
import MediaBlockRenderer from "./MediaBlockRenderer";
import SpeakingRecorder from "./SpeakingRecorder";
import { useRef, useState } from "react";
import { uploadAssessmentRecording } from "../../../services/elearningAssessments";
import { getApiUrl } from "../../../utils/apiClient";
export default function AssessmentQuestions({ questions, answers, onChange, disabled, attemptId, recordings = {} }) {
  const { t } = useTranslation("dashboard");
  const revisions = useRef({});
  const [savedRecordings,setSavedRecordings]=useState({});
  const [recorderKeys,setRecorderKeys]=useState({});
  const [recordingState, setRecordingState] = useState({});
  async function recording(question, value) {
    const revision = (revisions.current[question.id] || 0) + 1;
    revisions.current[question.id] = revision;
    onChange(question.id, undefined);
    if (question.type === "speaking_practice") {
      if (value?.finished === true) onChange(question.id, { finished: true });
      return;
    }
    setRecordingState(previous => ({...previous,[question.id]:(savedRecordings[question.id] || recordings[question.id]) ? "editing" : null}));
    if (!(value instanceof Blob) || !attemptId) return;
    setRecordingState(previous => ({ ...previous, [question.id]: "uploading" }));
    try {
      const result = await uploadAssessmentRecording(attemptId, question.id, value);
      if (revisions.current[question.id] !== revision) return;
      setSavedRecordings(previous => ({...previous,[question.id]:result.id}));
      onChange(question.id, { recording_id: result.id });
      setRecordingState(previous => ({ ...previous, [question.id]: "saved" }));
    } catch {
      if (revisions.current[question.id] === revision) setRecordingState(previous => ({ ...previous, [question.id]: "error" }));
    }
  }
  return questions.map((q, index) => <fieldset className="ecommerce-list-card assessment-question" key={q.id} disabled={disabled}>
    <legend>{t("elearning.assessment.question", { number: index + 1 })}: {q.prompt}</legend>
    {q.type !== "speaking_practice" && <small>{t("elearning.assessment.points")}: {q.points}</small>}
    {q.type === "written" && <label>{t("elearning.assessment.writtenAnswer")}<textarea required maxLength={q.config.max_characters} value={answers[q.id]?.text || ""} onChange={event => onChange(q.id, { text: event.target.value })} /></label>}
    {["speaking", "speaking_practice"].includes(q.type) && <div>
      {q.config.media && <MediaBlockRenderer kind="audio" block={{ title: q.prompt, media: q.config.media }} />}
      <SpeakingRecorder key={recorderKeys[q.id] || 0} maxDuration={q.config.max_duration_seconds} maxBytes={q.config.max_size_bytes} disabled={disabled || recordingState[q.id] === "uploading"} practice={q.type === "speaking_practice"} onChange={value => recording(q, value)} />
      {q.type === "speaking" && !answers[q.id]?.recording_id && (savedRecordings[q.id] || recordings[q.id]) && recordingState[q.id] !== "uploading" && <button type="button" disabled={disabled} onClick={() => {
        revisions.current[q.id]=(revisions.current[q.id] || 0)+1;
        onChange(q.id,{recording_id:savedRecordings[q.id] || recordings[q.id]});
        setRecorderKeys(previous => ({...previous,[q.id]:(previous[q.id] || 0)+1}));
        setRecordingState(previous => ({...previous,[q.id]:"restored"}));
      }}>{t("elearning.assessment.useSavedRecording")}</button>}
      {recordingState[q.id] === "restored" && answers[q.id]?.recording_id && <audio controls preload="none" src={getApiUrl(`/elearning/assessment-recordings/${answers[q.id].recording_id}`)} aria-label={q.prompt} />}
      {recordingState[q.id] && <p role={recordingState[q.id] === "error" ? "alert" : "status"}>{t(`elearning.assessment.recordingUpload.${recordingState[q.id]}`)}</p>}
    </div>}
    {q.type === "picture_listen" && <div>
      <MediaBlockRenderer kind="audio" block={{ title: q.prompt, media: q.config.media }} />
      <div className="assessment-picture-options">{q.config.options.map(option => <label key={option.id}>
        <input type="radio" aria-label={option.alt} required name={q.id} checked={answers[q.id]?.option_id === option.id} onChange={() => onChange(q.id, { option_id: option.id })} />
        {option.media?.url && /^\/uploads\/tenant_[1-9][0-9]*\/builder_assets\/[a-f0-9]{32}\.(png|jpg|jpeg|webp)$/.test(option.media.url) && <img loading="lazy" width="160" height="120" style={{ objectFit: "contain", maxWidth: "100%" }} src={getApiUrl(option.media.url)} alt={option.alt} />}
        <span>{option.alt}</span>
      </label>)}</div>
    </div>}
    {q.type === "multiple_choice" && q.config.options.map(option => <label key={option.id}><input type="radio" name={q.id} checked={answers[q.id]?.option_id === option.id} onChange={() => onChange(q.id, { option_id: option.id })} />{option.label}</label>)}
    {q.type === "true_false" && [true, false].map(value => <label key={String(value)}><input type="radio" name={q.id} checked={answers[q.id]?.value === value} onChange={() => onChange(q.id, { value })} />{t(`elearning.assessment.${value ? "true" : "false"}`)}</label>)}
    {["matching", "listen_match"].includes(q.type) && q.config.prompts.map((prompt, i) => <div className="assessment-pair" key={prompt.id}>
      {q.type === "listen_match" ? <MediaBlockRenderer kind="audio" block={{ title: `${t("elearning.content.types.audio")} ${i + 1}`, media: prompt.media }} /> : <p>{prompt.label}</p>}
      <label>{q.type === "listen_match" ? `${t("elearning.content.types.audio")} ${i + 1}` : prompt.label}<select required value={answers[q.id]?.matches?.[prompt.id] || ""} onChange={event => onChange(q.id, { matches: { ...answers[q.id]?.matches, [prompt.id]: event.target.value } })}><option value="">{t("elearning.assessment.select")}</option>{q.config.targets.map(target => <option key={target.id} value={target.id}>{target.label}</option>)}</select></label>
    </div>)}
  </fieldset>);
}

import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { recordingWav } from "./recordingWav";

export default function SpeakingRecorder({ maxDuration = 120, maxBytes = 10485760, disabled = false, onChange, practice = false }) {
  const { t } = useTranslation("dashboard");
  const [state, setState] = useState("idle"), [error, setError] = useState(""), [url, setUrl] = useState("");
  const resource = useRef({ epoch: 0 }), callback = useRef(onChange), alive = useRef(true);
  useEffect(() => { callback.current = onChange; }, [onChange]);
  const audioId = useId();
  useEffect(() => {
    alive.current = true;
    const resources = resource.current;
    return () => {
      alive.current = false; resources.epoch += 1;
      clearTimeout(resources.timer);
      if (resources.recorder?.state === "recording") resources.recorder.stop();
      resources.stream?.getTracks().forEach(track => track.stop());
      if (resources.url) URL.revokeObjectURL(resources.url);
    };
  }, []);
  function stop() {
    clearTimeout(resource.current.timer);
    if (resource.current.recorder?.state === "recording") resource.current.recorder.stop();
  }
  async function start() {
    const epoch = ++resource.current.epoch;
    setError(""); setState("requesting"); callback.current?.(null);
    if (resource.current.url) URL.revokeObjectURL(resource.current.url);
    setUrl("");
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError("unsupported"); setState("idle"); return;
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!alive.current || epoch !== resource.current.epoch) { stream.getTracks().forEach(track => track.stop()); return; }
      resource.current.stream = stream;
      const recorder = new MediaRecorder(stream), chunks = [];
      let bytes = 0, recordingFailed = false;
      resource.current.recorder = recorder;
      recorder.ondataavailable = event => {
        bytes += event.data.size;
        if (bytes > maxBytes) { setError("recordingLimit"); stop(); }
        else if (event.data.size) chunks.push(event.data);
      };
      recorder.onerror = () => {
        recordingFailed = true; setError("recordingError"); stop();
        if (recorder.state === "inactive") {stream.getTracks().forEach(track => track.stop()); setState("idle");}
      };
      stream.getTracks().forEach(track => { track.onended = () => { if (recorder.state === "recording") { recordingFailed = true; setError("recordingError"); stop(); } }; });
      recorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop()); clearTimeout(resource.current.timer);
        if (!alive.current || epoch !== resource.current.epoch) return;
        setState("processing");
        try {
          if (recordingFailed) throw new Error("recordingError");
          if (bytes > maxBytes) throw new Error("recordingLimit");
          const wav = await recordingWav(new Blob(chunks, { type: recorder.mimeType }), maxDuration, maxBytes);
          if (!alive.current || epoch !== resource.current.epoch) return;
          const preview = URL.createObjectURL(wav); resource.current.url = preview;
          setUrl(preview); setState("ready"); callback.current?.(wav);
        } catch (failure) { if (alive.current && epoch === resource.current.epoch) { setError(["recordingLimit", "unsupported"].includes(failure.message) ? failure.message : "recordingError"); setState("idle"); } }
      };
      recorder.start(500); setState("recording"); resource.current.timer = setTimeout(stop, maxDuration * 1000);
    } catch (failure) {
      stream?.getTracks().forEach(track => track.stop());
      if (alive.current && epoch === resource.current.epoch) { setState("idle"); setError(failure.name === "NotAllowedError" ? "microphoneDenied" : "recordingError"); }
    }
  }
  return <div className="speaking-recorder" aria-busy={["requesting", "processing"].includes(state)}>
    {error && <p role="alert">{t(`elearning.assessment.${error}`)}</p>}
    <p role="status">{t(`elearning.assessment.recorder.${state}`)}</p>
    {state === "recording" ? <button type="button" onClick={stop}>{t("elearning.assessment.stopRecording")}</button> : <button type="button" disabled={disabled || ["requesting", "processing"].includes(state)} onClick={start}>{t(`elearning.assessment.${url ? "recordAgain" : "startRecording"}`)}</button>}
    {url && <audio id={audioId} controls preload="metadata" src={url} aria-label={t("elearning.assessment.yourRecording")} />}
    {practice && <button type="button" disabled={disabled || state !== "ready"} onClick={() => { callback.current?.({ finished: true }); setState("finished"); }}>{t("elearning.assessment.finishPractice")}</button>}
  </div>;
}

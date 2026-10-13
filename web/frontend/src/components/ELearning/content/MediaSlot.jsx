import { useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, CheckCircle2, ImagePlus, Mic, RefreshCw, Trash2, UploadCloud } from "lucide-react";
import { getApiUrl } from "../../../utils/apiClient";
import LessonAudioPlayer from "./LessonAudioPlayer";
import { MEDIA_RULES, MIN_PHOTO, checkMediaFile } from "../../../utils/mediaRules";
import "../../../styles/lesson-components.css";

function photoSize(file) {
  return new Promise(resolve => {
    if (typeof URL.createObjectURL !== "function" || typeof Image === "undefined") { resolve(null); return; }
    const url = URL.createObjectURL(file), image = new Image();
    image.onload = () => { resolve({ width: image.naturalWidth, height: image.naturalHeight }); URL.revokeObjectURL(url); };
    image.onerror = () => { resolve(null); URL.revokeObjectURL(url); };
    image.src = url;
  });
}

/**
 * EH / Media Slot: one expected photo or recording, named as in the owner's
 * media list. Empty placeholder → upload with progress → preview with Replace
 * and Remove. Remove only detaches the file from this lesson.
 */
export default function MediaSlot({ kind, label, expectedName, value, upload, onChange, onBusy }) {
  const { t } = useTranslation("dashboard");
  const input = useRef(null), id = useId();
  const [progress, setProgress] = useState(null), [error, setError] = useState(""), [warning, setWarning] = useState("");
  const rule = MEDIA_RULES[kind];
  const url = value?.url;
  async function choose(event) {
    const file = event.target.files?.[0]; event.target.value = "";
    if (!file) return;
    const problem = checkMediaFile(kind, file);
    if (problem) { setError(problem); return; }
    setError(""); setWarning("");
    if (kind === "image") {
      const size = await photoSize(file);
      if (size && (size.width < MIN_PHOTO.width || size.height < MIN_PHOTO.height)) setWarning("small");
    }
    const source = /wav/.test(file.type) && file.type !== "audio/wav" ? new File([file], file.name, { type: "audio/wav" }) : file;
    setProgress(0); onBusy?.(true);
    try {
      const result = await upload(source, setProgress);
      const assetId = result.asset_id || result.asset?.id || result.id;
      if (!assetId) throw new Error("Missing media identity");
      onChange({ id: assetId, url: result.asset_url || result.asset?.url || result.url, filename: file.name });
    } catch { setError("upload"); }
    finally { setProgress(null); onBusy?.(false); }
  }
  const status = progress !== null ? "uploading" : url ? "uploaded" : "pending";
  return <div className={`media-slot is-${status}`} aria-busy={status === "uploading"}>
    <div className="media-slot-head">
      {kind === "audio" ? <Mic size={20} aria-hidden="true" /> : <ImagePlus size={20} aria-hidden="true" />}
      <div><strong>{label}</strong>{expectedName && <code dir="ltr">{expectedName}</code>}</div>
      <span className={`media-slot-status is-${status}`}>
        {status === "uploaded" ? <CheckCircle2 size={16} aria-hidden="true" /> : status === "uploading" ? <UploadCloud size={16} aria-hidden="true" /> : <AlertTriangle size={16} aria-hidden="true" />}
        {t(`elearning.mediaSlot.${status}`)}
      </span>
    </div>
    {status === "uploaded" && (kind === "image"
      ? <img className="media-slot-preview" src={getApiUrl(url)} alt="" />
      : <LessonAudioPlayer src={getApiUrl(url)} title={value.filename} />)}
    {status === "pending" && <p className="media-slot-placeholder">{t(`elearning.mediaSlot.${kind}Placeholder`)}</p>}
    {status === "uploading" && <div className="media-slot-progress" role="progressbar" aria-label={t("elearning.mediaSlot.uploading")} aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}><span style={{ width: `${progress}%` }} /><small>{progress}%</small></div>}
    {status === "uploaded" && value.filename && <small className="media-slot-file" dir="ltr">{value.filename}</small>}
    <div className="media-slot-actions">
      <input ref={input} id={id} type="file" hidden accept={rule.accept} onChange={choose} />
      <button type="button" className="ecommerce-secondary-button" disabled={status === "uploading"} onClick={() => input.current?.click()}>
        {url ? <RefreshCw size={16} aria-hidden="true" /> : <UploadCloud size={16} aria-hidden="true" />}{t(url ? "elearning.mediaSlot.replace" : "elearning.mediaSlot.upload")}
      </button>
      {url && <button type="button" className="ecommerce-secondary-button" disabled={status === "uploading"} onClick={() => onChange(null)}><Trash2 size={16} aria-hidden="true" />{t("elearning.mediaSlot.remove")}</button>}
    </div>
    <small className="media-slot-help">{t(`elearning.mediaSlot.${kind}Rules`)}</small>
    {error && <p className="media-slot-error" role="alert"><AlertTriangle size={16} aria-hidden="true" />{t(`elearning.mediaSlot.error_${error}`)}</p>}
    {warning && <p className="media-slot-warning" role="status"><AlertTriangle size={16} aria-hidden="true" />{t("elearning.mediaSlot.warning_small")}</p>}
  </div>;
}

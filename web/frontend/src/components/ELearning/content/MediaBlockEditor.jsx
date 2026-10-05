import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import LoadingBar from "../../common/LoadingBar";
import MediaBlockRenderer from "./MediaBlockRenderer";

export default function MediaBlockEditor({ type, value, onChange, upload, onBusy }) {
  const { t } = useTranslation("dashboard");
  const [error, setError] = useState("");
  const captionLabelId = useId();
  const [uploading, setUploading] = useState(false);
  const allowed = type === "audio" ? ["audio/mpeg", "audio/wav", "audio/x-wav"] : ["video/mp4", "video/webm"];
  const limit = (type === "audio" ? 50 : 250) * 1024 * 1024;
  async function choose(event) {
    const file = event.target.files?.[0]; event.target.value = "";
    if (!file) return;
    if (!allowed.includes(file.type) || file.size > limit || !file.size) { setError("invalidFile"); return; }
    setError(""); setUploading(true); onBusy(true);
    try {
      // Normalize common WAV alias; the backend still verifies actual file content.
      const source = file.type === "audio/x-wav" ? new File([file], file.name, { type: "audio/wav" }) : file;
      const result = await upload(source);
      if (!result.asset_id) throw new Error("Missing media identity");
      onChange({ ...value, media_id: result.asset_id, media: { id: result.asset_id, url: result.asset_url, filename: file.name } });
    } catch { setError("uploadError"); }
    finally { setUploading(false); onBusy(false); }
  }
  return <div className="elearning-media-editor">
    <label>{t("elearning.content.upload")}<input type="file" accept={type === "audio" ? ".mp3,.wav" : ".mp4,.webm"} disabled={uploading} onChange={choose} /></label>
    <small>{t(`elearning.content.${type}Help`)}</small>
    {uploading && <LoadingBar mode="inline" label={t("elearning.content.uploading")} />}
    {error && <p role="alert" className="elearning-feedback is-error">{t(`elearning.content.${error}`)}</p>}
    {value.media_id && <MediaBlockRenderer key={value.media_id} block={value} kind={type} />}
    <label><span id={captionLabelId}>{t("elearning.content.caption")}</span><textarea aria-labelledby={captionLabelId} rows={3} maxLength={4000} value={value.content.caption} onChange={(event) => onChange({ ...value, content: { ...value.content, caption: event.target.value } })} /></label>
  </div>;
}

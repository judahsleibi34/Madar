import { useState } from "react";
import { useTranslation } from "react-i18next";
import ELearningDialog from "../ELearningDialog";
import TextBlockEditor from "./TextBlockEditor";
import MediaBlockEditor from "./MediaBlockEditor";

const editors = { text: TextBlockEditor, audio: MediaBlockEditor, video: MediaBlockEditor };
export default function ContentBlockEditor({ block, type, busy, error, upload, onSave, onClose }) {
  const { t } = useTranslation("dashboard");
  const [value, setValue] = useState(() => block || { type, title: "", content: type === "text" ? { version: 1, body: "", formats: [], ranges: [] } : { version: 1, caption: "" } });
  const [uploading, setUploading] = useState(false);
  const disabled = busy || uploading;
  const Editor = editors[type];
  const valid = type === "text" ? value.content.body.trim().length > 0 : Boolean(value.media_id);
  function save(event) {
    event.preventDefault();
    if (disabled || !valid) return;
    onSave({ type, title: value.title, content: value.content, ...(type !== "text" ? { media_id: value.media_id } : {}) });
  }
  return <ELearningDialog title={t(block ? "elearning.content.editType" : "elearning.content.addType", { type: t(`elearning.content.types.${type}`) })} busy={disabled} onClose={onClose} closeLabel={t("elearning.courses.close")}>
    <form onSubmit={save}>
      {error && <p role="alert" className="elearning-feedback is-error">{t(`elearning.content.${error}`)}</p>}
      <fieldset className="elearning-course-form" disabled={disabled}>
        <label>{t("elearning.content.title")}<input maxLength={120} value={value.title} onChange={(event) => setValue({ ...value, title: event.target.value })} /></label>
        {type === "text" ? <Editor value={value.content} onChange={(content) => setValue({ ...value, content })} /> : <Editor type={type} value={value} onChange={setValue} upload={upload} onBusy={setUploading} />}
      </fieldset>
      <footer><button type="button" className="ecommerce-secondary-button" disabled={disabled} onClick={onClose}>{t("elearning.courses.cancel")}</button><button type="submit" className="ecommerce-primary-button" disabled={disabled || !valid}>{t(busy ? "elearning.content.saving" : "elearning.courses.save")}</button></footer>
    </form>
  </ELearningDialog>;
}

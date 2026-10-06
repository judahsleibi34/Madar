import ELearningDescriptionTextarea from "./ELearningDescriptionTextarea";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import ELearningDialog from "./ELearningDialog";

export default function ELearningStructureForm({ label, kind, item, position, busy, error, onClose, onSave }) {
  const { t } = useTranslation("dashboard");
  const descriptionLabelId = useId();
  const [form, setForm] = useState(() => ({ name: item?.name || "", description: item?.description || "", status: item?.status || "draft" }));
  const change = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  return <ELearningDialog title={t(item ? "elearning.courses.edit" : "elearning.courses.add", { label })} onClose={onClose} busy={busy} closeLabel={t("elearning.courses.close")}>
    <form onSubmit={(event) => { event.preventDefault(); if (!busy) onSave(form); }}>
      {error && <p role="alert" className="elearning-feedback is-error">{t(`elearning.${error}`)}</p>}
      <fieldset className="elearning-course-form" disabled={busy}>
        <label>{t("elearning.courses.name", { label })}<input autoFocus required maxLength={120} value={form.name} onChange={(event) => change("name", event.target.value)} /></label>
        <label><span id={descriptionLabelId}>{t(kind === "lesson" ? "elearning.structure.shortDescription" : "elearning.courses.description", { label })}</span><ELearningDescriptionTextarea label={t(kind === "lesson" ? "elearning.structure.shortDescription" : "elearning.courses.description", { label })} maxLength={4000} value={form.description} onChange={(event) => change("description", event.target.value)} /></label>
        <label>{t("elearning.courses.status")}<select value={form.status} onChange={(event) => change("status", event.target.value)}>{["draft", "published", ...(item ? ["archived"] : [])].map((status) => <option key={status} value={status}>{t(`elearning.courses.statuses.${status}`)}</option>)}</select></label>
        <label>{t("elearning.structure.position")}<input type="number" min="1" readOnly value={position} aria-describedby="elearning-position-help" /></label>
        <p id="elearning-position-help" className="elearning-course-description">{t("elearning.structure.positionHelp")}</p>
      </fieldset>
      <footer><button type="button" className="ecommerce-secondary-button" disabled={busy} onClick={onClose}>{t("elearning.courses.cancel")}</button><button type="submit" className="ecommerce-primary-button" disabled={busy}>{t(busy ? "elearning.saving" : "elearning.courses.save")}</button></footer>
    </form>
  </ELearningDialog>;
}

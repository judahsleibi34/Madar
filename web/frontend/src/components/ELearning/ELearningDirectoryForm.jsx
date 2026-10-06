import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import { createDirectoryItem, updateDirectoryItem } from "../../services/elearningDirectory";
import ELearningDescriptionTextarea from "./ELearningDescriptionTextarea";
import ELearningDialog from "./ELearningDialog";
import EcommerceToast from "../DashboardBuilder/EcommerceToast";

export default function ELearningDirectoryForm({ kind, item, onClose, onSaved }) {
  const { t, i18n } = useTranslation("dashboard");
  const { labels } = useELearningTerminology();
  const instructor = kind === "instructors";
  const label = labels[instructor ? "instructor" : "group"];
  const [form, setForm] = useState(() => ({ name: item?.name || "", description: item?.description || "", status: item?.status || "active", ...(instructor ? { email: item?.email || "" } : {}) }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const update = (key, value) => { setForm((current) => ({ ...current, [key]: value })); setError(""); };
  const submit = async (event) => {
    event.preventDefault(); if (saving) return;
    const invalid = event.currentTarget.querySelector("input:invalid, textarea:invalid, select:invalid");
    if (!form.name.trim() || invalid) {
      setError(!form.name.trim() ? "directory.nameRequired" : invalid?.type === "email" ? "directory.invalidEmail" : "directory.validationError");
      (!form.name.trim() ? event.currentTarget.querySelector("input") : invalid)?.focus();
      return;
    }
    setSaving(true); setError("");
    try {
      const result = item ? await updateDirectoryItem(kind, item.id, { ...form, expected_revision: item.revision }) : await createDirectoryItem(kind, form);
      onSaved(result.item);
    } catch (failure) {
      setError(failure.code === "elearning_group_name_exists" ? "directory.duplicateName" : failure.status === 409 ? "directory.conflict" : failure.status === 403 ? "forbidden" : [400, 422].includes(failure.status) ? "directory.validationError" : "directory.saveError");
    } finally { setSaving(false); }
  };
  return <ELearningDialog title={t(item ? "elearning.courses.edit" : instructor ? "elearning.courses.add" : "elearning.courses.create", { label })} onClose={onClose} busy={saving} closeLabel={t("elearning.courses.close")}>
    {/* Keep errors inside the native dialog's top layer so they stay visible. */}
    <EcommerceToast type="error" title={error ? t("elearning.directory.validationTitle") : ""} message={error ? t(`elearning.${error}`, { label }) : ""} dir={i18n.dir()} onDismiss={() => setError("")} />
    <form onSubmit={submit} noValidate>
      <fieldset disabled={saving} className="elearning-course-form">
        <label>{t("elearning.courses.name", { label })}<input autoFocus required maxLength={120} value={form.name} onChange={(event) => update("name", event.target.value)} /></label>
        {instructor && <div className="elearning-directory-email-field"><label>{t("elearning.directory.email")}<input type="email" maxLength={254} aria-describedby="elearning-instructor-email-help" value={form.email} onChange={(event) => update("email", event.target.value)} /></label><small id="elearning-instructor-email-help">{t("elearning.directory.emailHelp")}</small></div>}
        <label>{t(instructor ? "elearning.directory.biography" : "elearning.courses.description", { label })}<ELearningDescriptionTextarea maxLength={4000} value={form.description} onChange={(event) => update("description", event.target.value)}
          label={t(instructor ? "elearning.directory.biography" : "elearning.courses.description", { label })}
          placeholder={t("elearning.directory.descriptionPlaceholder", { label })} /></label>
        <label>{t("elearning.courses.status")}<select aria-label={t("elearning.courses.status")} value={form.status} onChange={(event) => update("status", event.target.value)}>{["active", "archived"].map((status) => <option key={status} value={status}>{t(`elearning.directory.statuses.${status}`)}</option>)}</select></label>
      </fieldset>
      <footer><button type="button" className="ecommerce-secondary-button" disabled={saving} onClick={onClose}>{t("elearning.courses.cancel")}</button><button type="submit" className="ecommerce-primary-button" disabled={saving}>{t(saving ? "elearning.courses.saving" : "elearning.courses.save")}</button></footer>
    </form>
  </ELearningDialog>;
}

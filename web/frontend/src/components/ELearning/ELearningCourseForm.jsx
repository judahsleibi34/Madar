import ELearningDescriptionTextarea from "./ELearningDescriptionTextarea";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Upload, Image } from "lucide-react";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import { createCourse, updateCourse, uploadCourseCover } from "../../services/elearningCourses";
import { resolveMediaUrl } from "../../utils/media";
import ELearningDialog from "./ELearningDialog";

export default function ELearningCourseForm({ course, onClose, onSaved }) {
  const { t } = useTranslation("dashboard");
  const { labels } = useELearningTerminology();
  const [form, setForm] = useState(() => ({ name: course?.name || "", description: course?.description || "", cover_asset: course?.cover_asset || "", status: course?.status || "draft", access_type: course?.access_type || "private", ...(course && typeof course.catalog_visible === "boolean" ? { catalog_visible: course.catalog_visible } : {}) }));
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const update = (key, value) => { setForm((current) => ({ ...current, [key]: value })); setError(""); };
  const busy = saving || uploading;
  const upload = async (event) => {
    const file = event.target.files?.[0]; event.target.value = "";
    if (!file) return;
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type) || !file.size || file.size > 5 * 1024 * 1024) { setError("imageUploadInvalid"); return; }
    setUploading(true); setError("");
    try { const result = await uploadCourseCover(file); update("cover_asset", result.asset_url); }
    catch { setError("imageUploadError"); } finally { setUploading(false); }
  };
  const submit = async (event) => {
    event.preventDefault(); if (busy) return;
    setSaving(true); setError("");
    try {
      const result = course ? await updateCourse(course.id, { ...form, expected_revision: course.revision }) : await createCourse(form);
      onSaved(result.course);
    } catch (failure) {
      setError(failure.status === 409 ? "courses.conflict" : failure.status === 403 ? "forbidden" : [400, 422].includes(failure.status) ? "courses.validationError" : "courses.saveError");
    } finally { setSaving(false); }
  };
  return <ELearningDialog className="elearning-course-editor-dialog" title={t(course ? "elearning.courses.edit" : "elearning.courses.create", { label: labels.course })} onClose={onClose} busy={busy} closeLabel={t("elearning.courses.close")}>
    <form className="elearning-course-editor" onSubmit={submit}>
      <div className="elearning-course-editor-body">
      {error && <p className="elearning-feedback is-error" role="alert">{t(`elearning.${error}`)}</p>}
      <fieldset disabled={busy} className="elearning-course-form">
        <label className="elearning-course-name-field">{t("elearning.courses.name", { label: labels.course })}<input autoFocus required maxLength={120} value={form.name} onChange={(event) => update("name", event.target.value)} /></label>
        <label>{t("elearning.courses.description", { label: labels.course })}<ELearningDescriptionTextarea maxLength={4000} value={form.description} onChange={(event) => update("description", event.target.value)} label={t("elearning.courses.description", { label: labels.course })} /></label>
        <div className="elearning-cover-field">
          <span>{t("elearning.courses.cover")}</span>
          {form.cover_asset ? <img src={resolveMediaUrl(form.cover_asset)} alt={t("elearning.courses.coverPreview")} /> : <div className="elearning-cover-placeholder"><Image size={28} aria-hidden="true" /></div>}
          <div className="elearning-cover-actions"><label className="ecommerce-secondary-button elearning-cover-upload"><Upload size={16} aria-hidden="true" />{t("elearning.uploadImage")}<input type="file" accept="image/png,image/jpeg,image/webp" aria-label={t("elearning.uploadImage")} onChange={upload} /></label>
          {form.cover_asset && <button className="ecommerce-secondary-button" type="button" onClick={() => update("cover_asset", "")}>{t("elearning.courses.removeCover")}</button>}</div>
          <small>{t("elearning.courses.coverHelp")}</small>
        </div>
        {uploading && <p role="status">{t("elearning.uploadingImage")}</p>}
        <div className="ecommerce-field-grid">
          <label>{t("elearning.courses.status")}<select value={form.status} onChange={(event) => update("status", event.target.value)}>{["draft", "published", ...(course?.status === "archived" ? ["archived"] : [])].map((value) => <option value={value} key={value}>{t(`elearning.courses.statuses.${value}`)}</option>)}</select></label>
          <label>{t("elearning.courses.access")}<select value={form.access_type} onChange={(event) => update("access_type", event.target.value)}>{["private", "free", "paid"].map((value) => <option value={value} key={value}>{t(`elearning.courses.accessTypes.${value}`)}</option>)}</select></label>
          {typeof form.catalog_visible === "boolean" && <label className="elearning-course-catalog-choice"><input type="checkbox" checked={form.catalog_visible} onChange={event => update("catalog_visible", event.target.checked)} />{t("elearning.commerce.catalogVisible")}</label>}
        </div>
      </fieldset>
      </div>
      <footer><button type="button" className="ecommerce-secondary-button" disabled={busy} onClick={onClose}>{t("elearning.courses.cancel")}</button><button className="ecommerce-primary-button" type="submit" disabled={busy}>{t(saving ? "elearning.saving" : "elearning.courses.save")}</button></footer>
    </form>
  </ELearningDialog>;
}

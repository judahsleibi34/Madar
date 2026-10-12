import "../../styles/learning-form-runtime.css";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { getRuntimeFieldError } from "../PageBuilder/runtime/formValidation";
import { visibleLearningFields } from "../PageBuilder/runtime/formVisibility";
import { getModernFieldPlaceholder } from "../PageBuilder/core/PageBuilder.fields";
import { getFormPageNavigationItems } from "../PageBuilder/runtime/formPageNavigation";
import { getLocalizedValue, getLocalizedOptions } from "../PageBuilder/core/PageBuilder.localization";
import { apiFetch, getApiUrl } from "../../utils/apiClient";
export default function LearningFormRenderer({ form, identifier, preview = false, submissionPath, loginPath }) {
  const {t,i18n} = useTranslation("dashboard"), copy = key => t(`elearning.forms.${key}`);
  const instanceId = useId();
  const language = i18n.language.startsWith("ar") ? "ar" : "en";
  const translated = (source, keys) => ({...source, ...Object.fromEntries(keys.map(key => [key, getLocalizedValue(source, key, language)]))});
  const schema = {...translated(form.schema, ["title", "description", "submitLabel", "successMessage"]),
    sections: form.schema.sections.map(section => ({...translated(section, ["title"]),
      fields: section.fields.map(field => translated(field, ["label", "helpText", "placeholder"]))}))};
  const [answers, setAnswers] = useState({}), [errors, setErrors] = useState({}), [page, setPage] = useState(0), [completed, setCompleted] = useState([]), [status, setStatus] = useState("");
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  const visible = visibleLearningFields(schema, answers), visibleIds = new Set(visible.map(field => field.id));
  const pages = schema.pageMode === "single" ? [{title:"", fields:schema.sections.flatMap(section => section.fields)}] : schema.sections;
  const current = pages[Math.min(page, pages.length - 1)];
  const change = (id, value) => { setAnswers(previous => ({...previous, [id]:value}));setErrors({});setRequestKey(crypto.randomUUID());setCompleted([]); };
  function validation(fields) { const result = {};for (const field of fields.filter(field => visibleIds.has(field.id))) { const value = answers[field.id] ?? field.defaultValue;const error = getRuntimeFieldError(field.type === "file" ? {...field,maxFileSizeMb:field.maxFileSizeMb || 5} : field, value);if (error) result[field.id] = t("elearning.forms.invalid_input",{field:field.label});const limits = field.validation || {};if (value != null && value !== "" && ((limits.minLength != null && String(value).length < limits.minLength) || (limits.maxLength != null && String(value).length > limits.maxLength) || (field.type === "number" && ((limits.min != null && Number(value) < limits.min) || (limits.max != null && Number(value) > limits.max))))) result[field.id] = copy("invalid"); }return result; }
  async function submit(event) {
    event.preventDefault();if (status === "sending") return;const invalid = validation(page < pages.length - 1 ? current.fields : visible);setErrors(invalid);if (Object.keys(invalid).length) return;
    if (page < pages.length - 1) {setCompleted([...completed, page]);setPage(page + 1);return;}
    if (preview) return;setStatus("sending");
    const values = {}, body = new FormData();
    for (const field of visible) {const value = answers[field.id] ?? field.defaultValue;if (value instanceof File) body.append(`file:${field.id}`, value);else if (value != null && value !== "") values[field.id] = value;}
    body.append("payload", JSON.stringify({version:form.version, idempotency_key:requestKey, answers:values}));
    try {const response = await apiFetch(getApiUrl(submissionPath || `/public/academies/${encodeURIComponent(identifier)}/forms/${form.id}/responses`), {method:"POST",body});if (response.status === 401 && loginPath) {setStatus("login");return;}if (!response.ok) {const data = await response.json();if (data.detail?.field_id) setErrors({[data.detail.field_id]:copy("invalid")});throw new Error();}setStatus("received");} catch {setStatus("error");}
  }
  if (status === "received") return <p role="status">{schema.successMessage || copy("received")}</p>;
  return <form dir={i18n.dir()} lang={i18n.language} className="learning-form-runtime" onSubmit={submit}><h2>{schema.title}</h2><p>{schema.description}</p>{preview && <p>{copy("preview")}: {t("elearning.ui.preview_help")}</p>}{pages.length > 1 && <nav aria-label={copy("pages")}>{getFormPageNavigationItems(pages.length, page, completed).map(item => <button type="button" key={item.index} disabled={item.isDisabled} onClick={() => setPage(item.index)}>{item.index + 1}</button>)}</nav>}<h3>{current.title}</h3>
    <fieldset disabled={status === "sending"}>{current.fields.filter(field => visibleIds.has(field.id)).map(field => { const value = answers[field.id] ?? field.defaultValue ?? "";const domId = `${instanceId}-${field.id}`;const props = {id:domId, dir:"auto", placeholder:getModernFieldPlaceholder(field), "aria-invalid":Boolean(errors[field.id]), "aria-describedby":`${domId}-help`, onChange:event => change(field.id, event.target.value)};return <div className="elearning-field" key={field.id}><label htmlFor={domId}>{field.label}{field.required && " *"}</label>{field.type === "paragraph" ? <textarea {...props} value={value} maxLength={field.validation?.maxLength ?? 12000} /> : field.type === "dropdown" ? <select {...props} value={value}><option value="">{copy("select")}</option>{field.options.map((option, index) => <option key={option} value={option}>{getLocalizedOptions(field, language)[index] || option}</option>)}</select> : ["radio", "checkboxes"].includes(field.type) ? <div role="group" aria-label={field.label}>{field.options.map((option, index) => <label key={option}><input type={field.type === "radio" ? "radio" : "checkbox"} name={domId} checked={field.type === "radio" ? value === option : Array.isArray(value) && value.includes(option)} onChange={event => change(field.id, field.type === "radio" ? option : event.target.checked ? [...(Array.isArray(value) ? value : []), option] : value.filter(item => item !== option))} />{getLocalizedOptions(field, language)[index] || option}</label>)}</div> : field.type === "file" ? <input {...props} type="file" accept="application/pdf,image/png,image/jpeg" onChange={event => change(field.id,event.target.files[0])} /> : <input {...props} type={({shortText:"text",phone:"tel",number:"number",email:"email",date:"date"})[field.type] || "text"} step={field.type === "number" ? "any" : undefined} value={value} />}
      <small id={`${domId}-help`}>{field.helpText}</small>{errors[field.id] && <p role="alert">{errors[field.id]}</p>}</div>;})}<button className="runtime-submit" disabled={preview && page === pages.length - 1} type="submit">{page < pages.length - 1 ? copy("next") : schema.submitLabel || copy("submit")}</button></fieldset>{status === "error" && <p role="alert">{copy("error")}</p>}{status === "login" && <p role="alert"><a href={loginPath}>{t("elearning.learner.logIn")}</a></p>}</form>;
}

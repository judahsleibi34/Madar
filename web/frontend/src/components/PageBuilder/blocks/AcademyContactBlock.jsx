import { useState } from "react";
import { useTranslation } from "react-i18next";
import { apiFetch, getApiUrl } from "../../../utils/apiClient";
export default function AcademyContactBlock({ site, editing, heading }) {
  const { t } = useTranslation("dashboard");const label = key => t(`elearning.owner.${key}`);
  const [status, setStatus] = useState("");
  async function submit(event) {
    event.preventDefault();if (editing) return;setStatus("sending");
    const form = event.currentTarget;
    try { const response = await apiFetch(getApiUrl(`/public/academies/${encodeURIComponent(site.subdomain)}/contact`), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(Object.fromEntries(new FormData(form))) });if (!response.ok) throw new Error();form.reset();setStatus("received"); } catch { setStatus("error"); }
  }
  return <section className="academy-section"><h2>{heading}</h2><form onSubmit={submit}><fieldset disabled={editing || status === "sending"}>{["name", "email", "subject", "message"].map(key => <label className="elearning-field" key={key}>{label(key)}{key === "message" ? <textarea name={key} required maxLength={8000} /> : <input name={key} required={key !== "subject"} type={key === "email" ? "email" : "text"} maxLength={key === "subject" ? 200 : key === "email" ? 254 : 120} />}</label>)}<button type="submit">{label("send")}</button></fieldset>{status && <p role={status === "error" ? "alert" : "status"}>{label(status)}</p>}</form></section>;
}

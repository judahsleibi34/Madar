import LearningErrorNotice from "./LearningErrorNotice";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { apiFetch, getApiUrl } from "../../utils/apiClient";
import { fetchStructure } from "../../services/elearningStructure";
export default function CEFRConfiguration({ course, templates }) {
  const { t } = useTranslation("dashboard");
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const path = getApiUrl(`/elearning/programmes/courses/${course.id}/cefr`);
  useEffect(() => {
    let active = true;
    Promise.all([fetchStructure(course.id), apiFetch(path).then(response => response.ok ? response.json() : null)])
      .then(([structure, config]) => { if (active && config) setData({ structure, config }); }).catch(() => {});
    return () => { active = false; };
  }, [course.id, path]);
  if (!data) return null;
  async function save(event) {
    event.preventDefault(); setBusy(true); setError(false); setSaved(false);
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const response = await apiFetch(path, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...values, enabled: values.enabled === "on" }) });
      if (!response.ok) throw new Error();
      const config = await apiFetch(path).then(response => response.json()); setData({ ...data, config }); setSaved(true);
    } catch { setError(true); } finally { setBusy(false); }
  }
  return <section className="ecommerce-list-card"><h3>{t("elearning.programmes.cefr")}</h3><p>{t("elearning.programmes.cefrHelp")}</p>
    {data.config.items.map(row => <p key={row.section_id}>{row.cefr_level} · {data.structure.sections.find(section => section.id === row.section_id)?.name} · {t(`elearning.certificates.${row.enabled ? "active" : "revoked"}`)}</p>)}
    <form onSubmit={save} className="settings-form-grid"><label>{t("elearning.programmes.level")}<select name="level">{["A1", "A2", "B1", "B2", "C1"].map(level => <option key={level}>{level}</option>)}</select></label>
      <label>{t("elearning.programmes.section")}<select name="section_id" required><option value="">—</option>{data.structure.sections.map(section => <option key={section.id} value={section.id}>{section.name}</option>)}</select></label>
      <label>{t("elearning.certificates.template")}<select name="template_id" required><option value="">—</option>{templates.filter(row => row.status === "active").map(row => <option key={row.id} value={row.id}>{row.design.name}</option>)}</select></label>
      <label><input name="enabled" type="checkbox" defaultChecked />{t("elearning.certificates.enabled")}</label><button className="ecommerce-primary-button" disabled={busy}>{t("elearning.save")}</button>
    </form>{error && <LearningErrorNotice as="p">{t("elearning.programmes.cefrError")}</LearningErrorNotice>}{saved && <p role="status">{t("elearning.saved")}</p>}
  </section>;
}

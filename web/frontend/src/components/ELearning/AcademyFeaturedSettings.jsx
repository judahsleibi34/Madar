import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { fetchCourses } from "../../services/elearningCourses";
export default function AcademyFeaturedSettings({ selected, onChange }) {
  const { t } = useTranslation("dashboard");
  const [courses, setCourses] = useState([]), [more, setMore] = useState(false), [busy, setBusy] = useState(true), [error, setError] = useState(false);
  async function load(offset = 0) {
    setBusy(true); setError(false);
    try { const data = await fetchCourses(offset); setCourses(previous => offset ? [...previous, ...data.courses] : data.courses); setMore(data.has_more); } catch { setError(true); } finally { setBusy(false); }
  }
  useEffect(() => { let active = true; fetchCourses(0).then(data => { if (active) { setCourses(data.courses); setMore(data.has_more); } }).catch(() => { if (active) setError(true); }).finally(() => { if (active) setBusy(false); }); return () => { active = false; }; }, []);
  return <fieldset className="settings-wide-field"><legend>{t("elearning.academy.featured")}</legend><p>{t("elearning.academy.featuredHelp")}</p>{courses.filter(c => c.status === "published" && c.catalog_visible && c.access_type !== "private").map(c => <label className="elearning-toggle" key={c.id}><span>{c.name}</span><input type="checkbox" checked={selected.includes(c.id)} onChange={e => onChange(e.target.checked ? [...selected, c.id] : selected.filter(id => id !== c.id))} /></label>)}
    {selected.filter(id => !courses.some(c => c.id === id)).map(id => <label key={id}>{id}<button type="button" onClick={() => onChange(selected.filter(value => value !== id))}>{t("elearning.commerce.cancel")}</button></label>)}
    {busy && <p role="status">{t("elearning.loading")}</p>}{error && <p role="alert">{t("elearning.loadError")}<button type="button" onClick={() => load()}>{t("elearning.retry")}</button></p>}{more && <button type="button" disabled={busy} onClick={() => load(courses.length)}>{t("elearning.player.more")}</button>}
  </fieldset>;
}

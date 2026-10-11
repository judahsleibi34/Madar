import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { academyOwnerApi } from "./academyOwnerApi";
export default function AcademyExchangeSelector({ required, selectedId }) {
  const { t, i18n } = useTranslation("dashboard");const [items, setItems] = useState([]), [error, setError] = useState(false);
  useEffect(() => { let active = true;academyOwnerApi("/exchange/available/for-me").then(value => { if (active) setItems(value.items || []); }).catch(() => { if (active) setError(true); });return () => { active = false; }; }, []);
  return <label>{t("elearning.owner.opportunities")}<select key={items.map(row => row.id).join(":")} name="opportunity_id" defaultValue={selectedId || ""} required={required}><option value="">{t("elearning.owner.select_opportunity")}</option>{items.map(row => <option key={row.id} value={row.id}>{row.title} · {row.host_institution} · {row.location}</option>)}</select>{error && <span role="alert">{t("elearning.owner.error")}</span>}{items.map(row => <details key={row.id}><summary>{row.title}</summary><p>{row.short_description}</p><p>{row.requirements}</p>{["start_date", "end_date", "deadline", "capacity"].filter(key => row[key] != null).map(key => <p key={key}>{t(`elearning.owner.${key}`)}: {key === "capacity" ? row[key] : new Date(row[key]).toLocaleDateString(i18n.language)}</p>)}</details>)}</label>;
}

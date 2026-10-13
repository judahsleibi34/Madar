import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { OwnerState } from "./OwnerUI";
import { academyOwnerApi } from "./academyOwnerApi";
export default function AcademySupportDocuments({ application, editable = false }) {
  const { t } = useTranslation("dashboard");const label = key => t(`elearning.owner.${key}`);
  const [items, setItems] = useState(null), [file, setFile] = useState(null), [busy, setBusy] = useState(false), [error, setError] = useState(false), [attempt, setAttempt] = useState(0);
  const path = `/applications/${application.id}/documents`;
  useEffect(() => { let active = true;academyOwnerApi(path).then(value => { if (active) setItems(value.items); }).catch(() => { if (active) setError(true); });return () => { active = false; }; }, [path, attempt]);
  async function perform(callback) { setBusy(true);setError(false);try { await callback();setFile(null);setAttempt(attempt + 1); } catch { setError(true); } finally { setBusy(false); } }
  return <section className="elearning-owner-section"><h3>{label("documents")}</h3><p>{label("document_help")}</p><OwnerState error={error} retry={()=>{ setError(false); setAttempt(v=>v+1); }} loading={!items&&!error} empty={items&&!items.length&&t("elearning.ui.no_documents")}/>{(items||[]).map(row => <div key={row.id}><button className="ecommerce-secondary-button" type="button" disabled={busy} onClick={() => perform(() => academyOwnerApi(`${path}/${row.id}`, { download: row.filename }))}>{row.filename} · {Math.ceil(row.size_bytes/1024)} KB</button>{editable && <button className="ecommerce-secondary-button" type="button" disabled={busy} onClick={() => perform(() => academyOwnerApi(`${path}/${row.id}`, { method: "DELETE" }))}>{label("remove")}</button>}</div>)}{editable && <><label>{label("upload")}<input type="file" accept="application/pdf,image/png,image/jpeg" disabled={busy} onChange={event => setFile(event.target.files[0])} /></label><button className="ecommerce-secondary-button" type="button" disabled={busy || !file || file.size > 5242880} onClick={() => perform(() => academyOwnerApi(path, { method: "POST", file }))}>{label("upload")}</button></>}</section>;
}

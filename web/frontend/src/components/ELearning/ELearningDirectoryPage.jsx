import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDirectorySummary } from "../../services/elearningRelationships";
import { useTranslation } from "react-i18next";
import { Users, GraduationCap, Plus, Pencil, Archive, Tag, Trash2 } from "lucide-react";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import { fetchDirectory, archiveDirectoryItem, deleteDirectoryItem } from "../../services/elearningDirectory";
import ELearningSkeleton from "./ELearningSkeleton";
import ELearningDirectoryForm from "./ELearningDirectoryForm";
import ELearningDialog from "./ELearningDialog";
import "../../styles/admin/dashboard/elearning-directory.css";
import EcommerceToast from "../DashboardBuilder/EcommerceToast";
import { notifyCommerceAction } from "../../utils/commerceActionToast";

export default function ELearningDirectoryPage({ kind }) {
  const { t, i18n } = useTranslation("dashboard");
  const { labels, loading: labelsLoading, error: labelsError, retry } = useELearningTerminology();
  const [summary, setSummary] = useState({});
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [available, setAvailable] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState(null);
  const [archiving, setArchiving] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const instructor = kind === "instructors";
  const entity = instructor ? "instructor" : "group";
  const Icon = instructor ? GraduationCap : Users;
  useEffect(() => {
    let cancelled = false;
    fetchDirectorySummary(kind).then((data) => { if (!cancelled) setSummary(data); }).catch(() => {});
    fetchDirectory(kind).then((data) => { if (!cancelled) { setItems(data.items); setAvailable(data.available); setHasMore(data.has_more); } })
      .catch((failure) => { if (!cancelled) setError(failure.status === 403 ? "forbidden" : "directory.loadError"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [kind, reload]);
  const apply = (item) => setItems((current) => current.some((row) => row.id === item.id) ? current.map((row) => row.id === item.id ? item : row) : [item, ...current]);
  const refresh = () => { setError(""); setLoading(true); setReload((value) => value + 1); };
  const loadMore = async () => {
    setBusy(true); setError("");
    try { const data = await fetchDirectory(kind, items.length); setItems((current) => [...current, ...data.items.filter((row) => !current.some((existing) => existing.id === row.id))]); setHasMore(data.has_more); }
    catch (failure) { setError(failure.status === 403 ? "forbidden" : "directory.loadError"); } finally { setBusy(false); }
  };
  const archive = async () => {
    setBusy(true); setError("");
    try { const data = await archiveDirectoryItem(kind, archiving); apply(data.item); setArchiving(null); notifyCommerceAction({ type: "success", title: t("elearning.directory.archived", { label: labels[entity] }) }); }
    catch (failure) { setError(failure.status === 409 ? "directory.conflict" : failure.status === 403 ? "forbidden" : "directory.saveError"); }
    finally { setBusy(false); }
  };
  const remove = async () => {
    setBusy(true); setError("");
    try {
      await deleteDirectoryItem(kind, deleting);
      setItems(current => current.filter(item => item.id !== deleting.id));
      setDeleting(null);
      notifyCommerceAction({ type: "success", title: t("elearning.directory.deleted", { label: labels[entity] }) });
      // Reload pagination and assignment summaries after removing a row.
      setReload(value => value + 1);
    } catch (failure) { setError(failure.status === 409 ? "directory.conflict" : failure.status === 403 ? "forbidden" : instructor ? "directory.deleteInstructorError" : "directory.deleteError"); }
    finally { setBusy(false); }
  };
  const disabled = busy || !available || error === "forbidden" || labelsError?.status === 403;
  if (loading || labelsLoading) return <ELearningSkeleton variant={kind} label={t("elearning.loading")} lang={i18n.language} direction={i18n.dir()} />;
  return <main className="ecommerce-page elearning-management" dir={i18n.dir()}>
    <header className="ecommerce-page-header app-page-intro"><div><h1>{t(`elearning.navigation.${kind}`)}</h1><p>{t(`elearning.directory.${kind}Subtitle`, { labels: labels.plural[entity] })}</p></div></header>
    <div className="elearning-course-toolbar"><button className="ecommerce-primary-button" disabled={disabled} onClick={() => setForm({})}><Plus size={18} aria-hidden="true" />{t(instructor ? "elearning.courses.add" : "elearning.courses.create", { label: labels[entity] })}</button></div>
    {error && !archiving && !deleting && <div role="alert" className="elearning-feedback is-error">{t(`elearning.${error}`)} <button className="ecommerce-secondary-button" onClick={refresh}>{t("elearning.retry")}</button></div>}
    {labelsError && <div role="alert" className="elearning-feedback">{t(labelsError.status === 403 ? "elearning.forbidden" : "elearning.courses.labelsUnavailable")} <button className="ecommerce-secondary-button" onClick={retry}>{t("elearning.retry")}</button></div>}
    {!available && !error ? <p role="status" className="elearning-feedback">{t("elearning.directory.upgradeRequired")}</p> : !items.length && !error ? <section className="ecommerce-list-card ecommerce-empty-state"><Icon size={36} aria-hidden="true" /><h2>{t(`elearning.placeholders.${kind}Empty`, { labels: labels.plural[entity] })}</h2><p>{t(`elearning.directory.${kind}Help`, { label: labels[entity] })}</p></section> : <section className="ecommerce-list-card elearning-directory-list"><header className="ecommerce-list-header"><h2>{t("commerce:admin.manage", { items: labels.plural[entity] })}</h2></header>
      {items.map((item) => <article key={item.id} className="elearning-directory-card elearning-directory-row">
        <div className="ecommerce-record-icon elearning-directory-row-icon">{instructor ? <GraduationCap size={24} aria-hidden="true" /> : <Tag size={24} aria-hidden="true" />}</div>
        <div className="elearning-directory-row-copy">
          <h2><Link to={`/e-learning/${kind}/${item.id}`}>{item.name}</Link></h2>
          {instructor && item.email && <p className="elearning-directory-email">{item.email}</p>}
          {item.description?.trim() && <p className="elearning-directory-description">{item.description}</p>}
          {summary[item.id] && <dl className="elearning-course-counts">{Object.entries(summary[item.id]).map(([key, value]) => <div key={key}><dt>{key === "members" ? t("elearning.assignments.members") : labels.plural[key.replace(/s$/, "")]}</dt><dd>{value}</dd></div>)}</dl>}
          <dl className="elearning-directory-dates">{["created_at", "updated_at"].map(key => item[key] && <div key={key}><dt>{t(`elearning.directory.${key}`)}</dt><dd><time dateTime={item[key]}>{new Date(item[key]).toLocaleString(i18n.language)}</time></dd></div>)}</dl>
        </div>
        <span className={`elearning-course-status is-${item.status}`}>{t(`elearning.directory.statuses.${item.status}`)}</span>
        <div className="ecommerce-record-actions elearning-directory-row-actions">
          <button type="button" aria-label={t("elearning.courses.editAction")} title={t("elearning.courses.editAction")} disabled={disabled} onClick={() => setForm({ item })}><Pencil size={20} aria-hidden="true" /></button>
          {item.status !== "archived" && <button type="button" aria-label={t("elearning.courses.archive")} title={t("elearning.courses.archive")} disabled={disabled} onClick={() => { setError(""); setArchiving(item); }}><Archive size={20} aria-hidden="true" /></button>}
          <button type="button" aria-label={t("elearning.structure.delete")} title={t("elearning.structure.delete")} disabled={disabled} onClick={() => { setError(""); setDeleting(item); }}><Trash2 size={20} aria-hidden="true" /></button>
        </div>
      </article>)}
    </section>}
    {hasMore && <button className="ecommerce-secondary-button" disabled={busy} onClick={loadMore}>{t("elearning.courses.loadMore")}</button>}
    {form && <ELearningDirectoryForm kind={kind} item={form.item} onClose={() => setForm(null)} onSaved={(item) => { apply(item); setForm(null); notifyCommerceAction({ type: "success", title: t("elearning.directory.saved", { label: labels[entity] }) }); }} />}
    {deleting && <ELearningDialog title={t("elearning.directory.deleteTitle", { label: labels[entity] })} closeLabel={t("elearning.courses.close")} busy={busy} onClose={() => { setDeleting(null); setError(""); }}>
      <EcommerceToast type="error" title={error ? t("elearning.directory.validationTitle") : ""} message={error ? t(`elearning.${error}`) : ""} dir={i18n.dir()} onDismiss={() => setError("")} />
      <p>{t(instructor ? "elearning.directory.deleteInstructorHelp" : "elearning.directory.deleteHelp", { name: deleting.name })}</p>
      <footer><button className="ecommerce-secondary-button" disabled={busy} onClick={() => { setDeleting(null); setError(""); }}>{t("elearning.courses.cancel")}</button><button className="ecommerce-primary-button" disabled={busy} onClick={remove}>{t("elearning.structure.delete")}</button></footer>
    </ELearningDialog>}
    {archiving && <ELearningDialog title={t("elearning.courses.archiveTitle", { label: labels[entity] })} closeLabel={t("elearning.courses.close")} busy={busy} onClose={() => { setArchiving(null); setError(""); }}>
      <EcommerceToast type="error" title={error ? t("elearning.directory.validationTitle") : ""} message={error ? t(`elearning.${error}`) : ""} dir={i18n.dir()} onDismiss={() => setError("")} />
      <p>{t(instructor ? "elearning.directory.archiveHelp" : "elearning.assignments.archiveGroupHelp", { name: archiving.name, label: labels.group })}</p><footer><button className="ecommerce-secondary-button" disabled={busy} onClick={() => { setArchiving(null); setError(""); }}>{t("elearning.courses.cancel")}</button><button className="ecommerce-primary-button" disabled={busy} onClick={archive}>{t("elearning.courses.archive")}</button></footer>
    </ELearningDialog>}
  </main>;
}

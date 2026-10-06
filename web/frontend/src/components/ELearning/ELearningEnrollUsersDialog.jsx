import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Search } from "lucide-react";
import ELearningDialog from "./ELearningDialog";
import { fetchEnrollmentCandidates, enrollCourseUsers } from "../../services/elearningParticipation";

function alreadyEnrolled(user, source) {
  return user.individual_sources ? user.individual_sources.includes(source) : user.already_enrolled;
}

export default function ELearningEnrollUsersDialog({ course, onClose, onSaved }) {
  const { t } = useTranslation("dashboard");
  const [query, setQuery] = useState("");
  const [users, setUsers] = useState([]);
  const [selected, setSelected] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [source, setSource] = useState(course.access_type === "free" ? "free" : "manual");
  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(() => {
      fetchEnrollmentCandidates(course.id, query).then((data) => { if (!cancelled) { setUsers(data.users); setHasMore(data.has_more); setSelected((current) => current.filter((id) => !data.users.some((user) => user.id === id && alreadyEnrolled(user, source)))); } })
        .catch(() => { if (!cancelled) setError("candidatesError"); }).finally(() => { if (!cancelled) setLoading(false); });
    }, 200);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [course.id, query, reload, source]);
  const loadMore = async () => {
    setBusy(true); setError("");
    try { const data = await fetchEnrollmentCandidates(course.id, query, users.length); setUsers((current) => [...current, ...data.users.filter((user) => !current.some((existing) => existing.id === user.id))]); setHasMore(data.has_more); }
    catch { setError("candidatesError"); } finally { setBusy(false); }
  };
  const submit = async (event) => {
    event.preventDefault(); if (!selected.length || busy || loading) return;
    setBusy(true); setError("");
    try {
      // The API accepts 100 users per request; enrollment has no total selection cap.
      for (let offset = 0; offset < selected.length; offset += 100) {
        const batch = selected.slice(offset, offset + 100);
        await enrollCourseUsers(course.id, batch, source);
        setSelected((current) => current.filter((id) => !batch.includes(id)));
        setUsers((current) => current.map((user) => batch.includes(user.id)
          ? { ...user, already_enrolled: true, individual_sources: [...(user.individual_sources || []), source] }
          : user));
      }
      onSaved();
    }
    catch (failure) { setError(failure.status === 409 ? "duplicateError" : failure.status === 403 ? "forbidden" : "enrollError"); }
    finally { setBusy(false); }
  };
  return <ELearningDialog title={t("elearning.enrollments.enroll")} closeLabel={t("elearning.courses.close")} busy={busy} onClose={onClose}><form onSubmit={submit} className="elearning-enroll-form">
    <p>{t("elearning.enrollments.selectHelp")}</p>
    {error && <p role="alert" className="elearning-feedback is-error">{t(error === "forbidden" ? "elearning.forbidden" : `elearning.enrollments.${error}`)} <button type="button" className="ecommerce-secondary-button" disabled={busy} onClick={() => { setError(""); setLoading(true); setReload((value) => value + 1); }}>{t("elearning.retry")}</button></p>}
    <label className="ecommerce-search"><Search size={18} aria-hidden="true" /><input type="search" aria-label={t("elearning.enrollments.searchUsers")} placeholder={t("elearning.enrollments.searchUsers")} maxLength={120} value={query} disabled={busy} onChange={(event) => { setQuery(event.target.value); setLoading(true); setError(""); }} /></label>
    <fieldset disabled={busy || loading} className="elearning-enroll-selection"><legend>{t("elearning.enrollments.existingUsers")}</legend>{loading ? <p role="status">{t("elearning.enrollments.loadingUsers")}</p> : users.length === 0 ? <p>{t("elearning.enrollments.noUsers")}</p> : users.map((user) => <label key={user.id}><input type="checkbox" disabled={alreadyEnrolled(user, source)} checked={selected.includes(user.id)} onChange={(event) => setSelected((current) => event.target.checked ? [...current, user.id] : current.filter((id) => id !== user.id))} /><span><strong>{user.name}</strong><small>{user.email}</small></span>{alreadyEnrolled(user, source) && <small>{t("elearning.enrollments.alreadyEnrolled")}</small>}</label>)}</fieldset>
    {hasMore && <button type="button" className="ecommerce-secondary-button" disabled={busy || loading} onClick={loadMore}>{t("elearning.courses.loadMore")}</button>}
    <label className="elearning-progress-filter">{t("elearning.enrollments.accessSource")}<select value={source} disabled={busy} onChange={(event) => { setSource(event.target.value); setSelected([]); }}><option value="manual">{t("elearning.participation.access_manual")}</option>{course.access_type === "free" && <option value="free">{t("elearning.participation.access_free")}</option>}</select></label>
    <footer><button type="button" className="ecommerce-secondary-button" disabled={busy} onClick={onClose}>{t("elearning.courses.cancel")}</button><button type="submit" className="ecommerce-primary-button" disabled={busy || loading || !selected.length}>{t("elearning.enrollments.enrollSelected")}</button></footer>
  </form></ELearningDialog>;
}

import { OwnerHeader,OwnerState } from "./OwnerUI";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { apiFetch, getApiUrl } from "../../utils/apiClient";
import { fetchCourses } from "../../services/elearningCourses";
export default function AcademyReportsPage() {
  const { t, i18n } = useTranslation("dashboard");
  const label = key => t(`elearning.programmes.${key}`);
  const [courses, setCourses] = useState([]);
  const [filters, setFilters] = useState({});
  const [directory, setDirectory] = useState({ students: [], levels: [] });
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [attempt,setAttempt]=useState(0);
  const [busy, setBusy] = useState(false);
  const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value)).toString();
  const path = getApiUrl(`/elearning/programmes/reports?${params}`);
  useEffect(() => {
    let active = true;
    fetchCourses().then(value => { if (active) setCourses(value.courses || []); }).catch(() => {});
    return () => { active = false; };
  }, []);
  useEffect(() => {
    let active = true;
    apiFetch(path).then(response => { if (!response.ok) throw new Error(); return response.json(); })
      .then(value => { if (active) {
        setData(value); setError(false);
        setDirectory(previous => ({
          students: [...new Map([...previous.students, ...value.enrollments.filter(row => row.user_id).map(row => ({ id: row.user_id, name: row.name, email: row.email }))].map(row => [row.id, row])).values()],
          levels: [...new Map([...previous.levels, ...value.enrollments.flatMap(row => (row.sections || []).map(section => ({ ...section, course_id: row.course_id, course_name: row.course_name })))].map(row => [row.id, row])).values()],
        }));
      } }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [path,attempt]);
  async function download() {
    setBusy(true);setError(false);
    try {
      const response = await apiFetch(`${path}&export=true`);if (!response.ok) throw new Error();
      const url = URL.createObjectURL(await response.blob());const anchor = document.createElement("a");anchor.href = url;anchor.download = "academy-progress.csv";anchor.click();window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { setError(true); } finally { setBusy(false); }
  }
  return <section className="ecommerce-page elearning-management" dir={i18n.dir()}><OwnerHeader title={label("reports")} description={label("reportsHelp")}/>
    <div className="elearning-owner-filters"><label>{label("course")}<select value={filters.course_id || ""} onChange={event => setFilters({ ...filters, course_id: event.target.value, section_id: "" })}><option value="">{label("all")}</option>{courses.map(course => <option key={course.id} value={course.id}>{course.name}</option>)}</select></label>
      <label>{label("student")}<select value={filters.user_id || ""} onChange={event => setFilters({ ...filters, user_id: event.target.value })}><option value="">{label("all")}</option>{directory.students.map(row => <option key={row.id} value={row.id}>{row.name} · {row.email}</option>)}</select></label>
      <label>{label("level")}<select value={filters.section_id || ""} onChange={event => setFilters({ ...filters, section_id: event.target.value })}><option value="">{label("all")}</option>{directory.levels.filter(row => !filters.course_id || row.course_id === filters.course_id).map(row => <option key={row.id} value={row.id}>{row.name} · {row.course_name}</option>)}</select></label>
      <label>{label("status")}<select value={filters.status || ""} onChange={event => setFilters({ ...filters, status: event.target.value })}><option value="">{label("all")}</option>{["active", "suspended", "archived", "completed", "not_started"].map(value => <option key={value} value={value}>{t(`elearning.enrollments.${value}`, { defaultValue: value })}</option>)}</select></label>
      {["date_from", "date_to"].map(key => <label key={key}>{label(key)}<input type="date" onChange={event => setFilters({ ...filters, [key]: event.target.value ? `${event.target.value}T${key === "date_to" ? "23:59:59" : "00:00:00"}Z` : "" })} /></label>)}</div>
    <OwnerState error={error} loading={!data&&!error} retry={()=>{ setError(false); setAttempt(v=>v+1); }}/>
    {data && <><div className="elearning-owner-metrics">{Object.entries(data.summary).map(([key, value]) => <article className="ecommerce-list-card" key={key}><h3>{label(key)}</h3><strong>{value}{key === "pass_rate" ? "%" : ""}</strong></article>)}</div>
      <div className="elearning-course-grid">{["progress_distribution", "level_distribution"].map(key => <article className="ecommerce-list-card" key={key}><h2>{label(key)}</h2>{(data[key] || []).map((row, index) => <label key={index}>{row.level || label(row.status)} · {row.count}<progress aria-label={row.level || label(row.status)} value={row.count} max={Math.max(1, ...(data[key] || []).map(item => item.count))}/></label>)}</article>)}</div>
      <button className="ecommerce-secondary-button" disabled={busy} onClick={download}>{label("export")}</button>
      <div className="elearning-owner-table-wrap"><table className="elearning-owner-table"><thead><tr>{["student", "course", "progress", "status"].map(key => <th key={key}>{label(key)}</th>)}</tr></thead><tbody>{data.enrollments.map(row => <tr key={`${row.course_id}:${row.id}`}><td>{row.name}</td><td><Link to={`/e-learning/courses/${row.course_id}/learners`}>{row.course_name}</Link></td><td>{row.progress_percent}%</td><td>{t(`elearning.player.${row.progress_status}`, { defaultValue: row.progress_status })}</td></tr>)}</tbody></table>{!data.enrollments.length && <p>{label("empty")}</p>}</div>
      <div className="elearning-course-grid">{data.rewards.map((row, index) => <article className="ecommerce-list-card" key={index}><h3>{label("rewards")}</h3><p>{row.sales} · {row.amount} {row.currency} · {label(row.status)} {row.simulated && label("simulated")}</p></article>)}{data.applications.map(row => <article className="ecommerce-list-card" key={`${row.kind}:${row.status}`}><h3>{label(row.kind)}</h3><p>{label(row.status)} · {row.count}</p></article>)}</div>
    </>}
  </section>;
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { apiFetch, getApiUrl } from "../../utils/apiClient";
import { OwnerHeader, OwnerPage, OwnerState, OwnerStatus, OwnerTable, OwnerPagination } from "./OwnerUI";
import { useLearningExperience } from "./LearningExperienceContext";
export default function AcademyStudentsPage() {
  const { t } = useTranslation("dashboard");
  // EduHope: "Verified PAU Student" is set only by an admin, so the automatic email flag is not shown.
  const enhanced = useLearningExperience()?.studentDashboard === true;
  const [data, setData] = useState(null), [page, setPage] = useState(0), [query, setQuery] = useState(""), [error, setError] = useState(false), [classification, setClassification] = useState(""), [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    apiFetch(getApiUrl(`/elearning/owner/students?limit=50&offset=${page * 50}${classification ? `&classification=${classification}` : ""}`)).then(response => { if (!response.ok) throw new Error(); return response.json(); }).then(value => { if (active) { setData(value); setError(false); } }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [page, classification, attempt]);
  const rows = data?.learners.filter(row => `${row.name} ${row.email}`.toLowerCase().includes(query.toLowerCase())) || [];
  return <OwnerPage><OwnerHeader title={t("elearning.programmes.students")} description={t("elearning.ui.students_help")} actions={<Link className="ecommerce-secondary-button" to="/e-learning/reports">{t("elearning.programmes.reports")}</Link>} />
    <div className="elearning-owner-filters"><label>{t("elearning.programmes.search")}<input value={query} onChange={event => setQuery(event.target.value)} /></label><label>{t("elearning.owner.classification")}<select value={classification} onChange={event => { setClassification(event.target.value); setPage(0); }}><option value="">{t("elearning.programmes.all")}</option><option value="institution">{t("elearning.owner.institution_verified")}</option><option value="regular">{t("elearning.owner.regular_student")}</option></select></label></div>
    <OwnerState error={error} retry={()=>{ setError(false); setAttempt(v=>v+1); }} loading={!data&&!error} empty={data&&!rows.length&&t("elearning.programmes.empty")} />
    {rows.length>0&&<OwnerTable caption={t("elearning.programmes.students")} columns={[t("elearning.programmes.student"),t("elearning.owner.classification"),t("elearning.programmes.status"),t("elearning.ui.actions")]}>{rows.map(row=><tr key={row.id}><td>{row.name}<p>{row.email}</p></td><td>{row.classification&&!['Institution Student','Regular Student','institution','regular'].includes(row.classification)?row.classification:t(`elearning.owner.${row.institution_verified?'institution_verified':'regular_student'}`)}{!enhanced && <> · {t(`elearning.owner.${row.email_verified?"verified":"unverified"}`)}</>}</td><td><OwnerStatus value={row.status}>{t(`elearning.programmes.${row.status}`,{defaultValue:t("elearning.ui.member")})}</OwnerStatus></td><td><Link className="ecommerce-secondary-button" to="/e-learning/courses">{t("elearning.programmes.manageEnrollments")}</Link></td></tr>)}</OwnerTable>}
    {data&&<OwnerPagination page={page} setPage={setPage} more={data.has_more}/>}</OwnerPage>;
}

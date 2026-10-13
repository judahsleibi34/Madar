import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { BookCheck, Layers, Library, ClipboardCheck, ChartNoAxesCombined, Target } from "lucide-react";
import { formatCommerceMoney, formatCommerceDateTime } from "../../utils/commerceI18n";
import { OwnerStatus, OwnerTable } from "./OwnerUI";

const performanceMetrics = [
  ["completed_courses", "completed_enrollments", BookCheck],
  ["completed_topics", "topic_completions", Library],
  ["completed_levels", "level_completions", Layers],
  ["attempts", "submitted_attempts", ClipboardCheck],
  ["average_score", "average_score", ChartNoAxesCombined],
  ["pass_rate", "pass_rate", Target],
];

export function AcademyLearningPerformance({ progress }) {
  const {t,i18n}=useTranslation("dashboard");
  const copy=key=>t(`elearning.admin_overview.${key}`);
  return <section className="elearning-owner-section">
    <div className="academy-overview-section-heading"><div><h2>{copy("learning_title")}</h2><p>{copy("learning_help")}</p></div><Link to="/e-learning/reports">{copy("view_reports")}</Link></div>
    <div className="user-dashboard-metrics-grid">
      {performanceMetrics.filter(([key])=>progress[key]!=null).map(([key,label,Icon])=>{
        const percentage=["average_score","pass_rate"].includes(key);
        const hasAttempts=Number(progress.attempts)>0;
        const value=percentage && !hasAttempts ? "—" : `${Number(progress[key]).toLocaleString(i18n.language)}${percentage ? "%" : ""}`;
        return <article className="user-dashboard-metric-card" key={key}>
          <div className="user-dashboard-metric-heading"><span className="user-dashboard-metric-icon" aria-hidden="true"><Icon size={21} /></span><span className="user-dashboard-metric-label">{copy(label)}</span></div>
          <div><strong className="user-dashboard-metric-value">{value}</strong><p className="user-dashboard-metric-note">{copy(percentage && !hasAttempts ? "no_attempts" : `${label}_help`)}</p></div>
        </article>;
      })}
    </div>
  </section>;
}

export function AcademyFinanceSummary({ data, capabilities }) {
  const {t,i18n}=useTranslation("dashboard");
  const copy=key=>t(`elearning.admin_overview.${key}`);
  const groups=["wallets","revenue","rewards","withdrawals"].filter(key=>data[key]?.length);
  if(!groups.length)return null;
  const money=(value,currency)=>formatCommerceMoney(value,currency,i18n.language);
  const destinations={wallets:["rewards","/e-learning/finance/rewards"],revenue:["transactions","/e-learning/finance/transactions"],rewards:["rewards","/e-learning/finance/rewards"],withdrawals:["withdrawal","/e-learning/finance/withdrawals"]};
  return <section className="elearning-owner-section">
    <div className="academy-overview-section-heading"><div><h2>{copy("finance_title")}</h2><p>{copy("finance_help")}</p></div></div>
    <div className="academy-overview-finance-grid">{groups.map(kind=>{
      const wallets=kind==="wallets",hasStatus=["rewards","withdrawals"].includes(kind);
      const [capability,path]=destinations[kind];
      const columns=wallets ? [copy("currency"),copy("available"),copy("reserved")] : [copy("currency"),...(hasStatus ? [t("elearning.owner.status"),copy(kind==="withdrawals" ? "requests" : "sales")] : []),copy("amount")];
      return <section className="academy-overview-finance-panel" key={kind}>
        <div className="academy-overview-section-heading"><h3>{copy(kind)}</h3>{capabilities?.[capability] && <Link to={path}>{copy("view_details")}</Link>}</div>
        <OwnerTable caption={copy(kind)} columns={columns}>{data[kind].map((row,index)=><tr key={`${row.currency}:${row.status || "total"}:${index}`}>
          <th scope="row">{row.currency}</th>
          {wallets ? <><td>{money(row.available,row.currency)}</td><td>{money(row.pending,row.currency)}</td></> : <>
            {hasStatus && <><td><OwnerStatus value={row.status}>{t(`elearning.programmes.${row.status}`)}</OwnerStatus></td><td>{Number(row.count ?? row.sales ?? 0).toLocaleString(i18n.language)}</td></>}
            <td>{money(row.amount,row.currency)}</td>
          </>}
        </tr>)}</OwnerTable>
      </section>;
    })}</div>
  </section>;
}

export function AcademyRecentActivity({ events, canReport }) {
  const {t,i18n}=useTranslation("dashboard");
  const copy=key=>t(`elearning.admin_overview.${key}`);
  return <section className="elearning-owner-section">
    <div className="academy-overview-section-heading"><div><h2>{copy("activity_title")}</h2><p>{copy("activity_help")}</p></div>{canReport && <Link to="/e-learning/reports">{copy("view_reports")}</Link>}</div>
    {!events?.length ? <p>{t("elearning.ui.no_activity")}</p> : <OwnerTable caption={copy("activity_title")} columns={[copy("event"),copy("recorded_at")]}>{events.map((row,index)=><tr key={`${row.event_type}:${row.created_at}:${index}`}>
      <td>{t(`elearning.ui.events.${row.event_type}`,{defaultValue:t("elearning.ui.academy_activity")})}</td>
      <td><time dateTime={row.created_at}>{formatCommerceDateTime(row.created_at,i18n.language)}</time></td>
    </tr>)}</OwnerTable>}
  </section>;
}

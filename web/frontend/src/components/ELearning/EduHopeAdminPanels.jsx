import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { fetchELearningSettings } from "../../services/elearningSettings";
import { fetchPlans } from "../../services/elearningCommerce";
import { formatCommerceMoney } from "../../utils/commerceI18n";
import "../../styles/eduhope-admin.css";

/** Horizontal bars; every bar also shows its number as text. */
function Bars({ title, rows }) {
  const { i18n } = useTranslation("dashboard");
  const max = Math.max(1, ...rows.map(([, value]) => Number(value) || 0));
  return <section className="eh-chart" aria-label={title}>
    <h3>{title}</h3>
    <ul>{rows.map(([label, value, tone]) => <li key={label}>
      <span className="eh-chart-label">{label}</span>
      <span className="eh-chart-track" aria-hidden="true"><span className={`eh-chart-bar ${tone || ""}`} style={{ width: `${(Number(value) || 0) / max * 100}%` }} /></span>
      <strong className="eh-chart-value">{Number(value || 0).toLocaleString(i18n.language)}</strong>
    </li>)}</ul>
  </section>;
}

const sum = (rows, status) => (rows || []).filter(row => !status || row.status === status).reduce((total, row) => total + Number(row.count ?? row.sales ?? 0), 0);

/** EH / Admin overview charts (website document §22), from the existing owner dashboard data. */
export function EduHopeAdminCharts({ data }) {
  const { t } = useTranslation("dashboard");
  const owner = key => t(`elearning.owner.${key}`), programme = key => t(`elearning.programmes.${key}`);
  const people = [["total_learners"], ["active_learners"], ["purchases"], ["affiliates"], ["support_eligible"], ["certificates"]]
    .filter(([key]) => data[key] != null).map(([key]) => [owner(key), data[key]]);
  const kinds = [...new Set((data.applications || []).map(row => row.kind))];
  const tone = status => ({ approved: "is-green", paid: "is-green", earned: "is-green", not_approved: "is-red", rejected: "is-red", reversed: "is-red", suspended: "is-red" })[status] || "is-blue";
  return <section className="elearning-owner-section eh-charts">
    <div className="academy-overview-section-heading"><div><h2>{t("elearning.ehAdmin.chartsTitle")}</h2><p>{t("elearning.ehAdmin.chartsHelp")}</p></div></div>
    <div className="eh-chart-grid">
      {people.length > 0 && <Bars title={t("elearning.ehAdmin.people")} rows={people} />}
      {kinds.map(kind => <Bars key={kind} title={programme(kind)} rows={data.applications.filter(row => row.kind === kind).map(row => [programme(row.status), row.count, tone(row.status)])} />)}
      {data.rewards?.length > 0 && <Bars title={t("elearning.ehAdmin.rewardSales")} rows={["earned", "reversed"].map(status => [t(`elearning.referrals.${status}`), sum(data.rewards, status), tone(status)])} />}
      {data.withdrawals?.length > 0 && <Bars title={programme("withdrawal")} rows={[...new Set(data.withdrawals.map(row => row.status))].map(status => [programme(status), sum(data.withdrawals, status), tone(status)])} />}
    </div>
  </section>;
}

/**
 * EH / Settings at a glance: course price, reward, minimum withdrawal, required
 * sales, payment methods, PAU domains and languages, each linking to the
 * existing editor (values stay tenant data, edited in one place).
 */
export function EduHopeSettingsSummary({ sample }) {
  const { t, i18n } = useTranslation("dashboard");
  const [loaded, setState] = useState(null);
  const state = sample || loaded; // sample: development gallery only
  useEffect(() => {
    if (sample) return undefined;
    let active = true;
    Promise.all([fetchELearningSettings(), fetchPlans().catch(() => null)])
      .then(([settings, plans]) => { if (active) setState({ settings: settings.settings || {}, plans: plans?.plans || [] }); })
      .catch(() => { if (active) setState({ error: true }); });
    return () => { active = false; };
  }, [sample]);
  if (!state) return null;
  if (state.error) return <p className="eh-settings-error" role="status">{t("elearning.ehAdmin.settingsUnavailable")}</p>;
  const s = state.settings, money = (amount, currency) => amount == null || amount === "" ? t("elearning.ehAdmin.notSet") : formatCommerceMoney(amount, currency || s.referral_reward_currency || "USD", i18n.language);
  const prices = state.plans.filter(plan => plan.status === "active" && plan.billing_type === "one_time");
  const programmes = section => `/e-learning/settings?tab=programmes&section=${section}`;
  const rows = [
    ["coursePrice", prices.length ? prices.map(plan => `${plan.name}: ${money(plan.amount, plan.currency)}`).join(" · ") : t("elearning.ehAdmin.noActivePlan"), "/e-learning/plans"],
    ["rewardAmount", s.referral_rewards_enabled ? money(s.referral_reward_amount, s.referral_reward_currency) : t("elearning.ehAdmin.off"), "/e-learning/settings?tab=programmes"],
    ["minimumWithdrawal", money(s.minimum_withdrawal_amount), programmes("withdrawal_settings")],
    ["requiredSales", s.tuition_sales_threshold ?? t("elearning.ehAdmin.notSet"), programmes("support_settings")],
    ["paymentMethods", (s.withdrawal_methods || []).join(" · ") || t("elearning.ehAdmin.notSet"), programmes("withdrawal_settings")],
    ["institutionDomains", s.institution_enabled ? `${(s.institution_email_domains || []).join(", ") || t("elearning.ehAdmin.notSet")} — ${s.institution_student_label || ""}` : t("elearning.ehAdmin.off"), "/e-learning/settings?tab=institution"],
    ["languages", t("elearning.ehAdmin.languagesValue"), null],
  ];
  return <section className="elearning-owner-section eh-settings-summary">
    <div className="academy-overview-section-heading"><div><h2>{t("elearning.ehAdmin.settingsTitle")}</h2><p>{t("elearning.ehAdmin.settingsHelp")}</p></div></div>
    <dl>{rows.map(([key, value, path]) => <div key={key}>
      <dt>{t(`elearning.ehAdmin.${key}`)}</dt>
      <dd><span dir="auto">{value}</span>{path && <Link to={path}>{t("elearning.ehAdmin.edit")}</Link>}</dd>
    </div>)}</dl>
  </section>;
}

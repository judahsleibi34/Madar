import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { request } from "./academyProgrammeApi";
import { fetchReferralAccount } from "../../services/elearningPlayer";
import ReferralInvitation from "./ReferralInvitation";
import ELearningSkeleton from "./ELearningSkeleton";

export default function AffiliateDashboard({ site }) {
  const { t, i18n } = useTranslation("dashboard");
  const [state, setState] = useState({ loading: true });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    request("/account").then(async account => {
      if (!account.capabilities?.affiliate) throw new Error("Unavailable");
      const referrals = await fetchReferralAccount().catch(() => null);
      if (active) setState({ account, referrals });
    }).catch(() => { if (active) setState({ error: true }); });
    return () => { active = false; };
  }, [attempt]);
  if (state.loading) return <ELearningSkeleton label={t("elearning.loading")} direction={i18n.dir()} />;
  if (state.error) return <section role="alert"><p>{t("elearning.affiliate.unavailable")}</p><button className="ecommerce-secondary-button" onClick={() => { setState({ loading: true }); setAttempt(value => value + 1); }}>{t("elearning.retry")}</button></section>;
  const { account, referrals } = state;
  const application = account.applications.filter(row => row.kind === "affiliate").sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];
  const status = application?.status;
  const money = (amount, currency) => new Intl.NumberFormat(i18n.language, { style: "currency", currency }).format(Number(amount));
  return <section className="learner-account affiliate-dashboard" dir={i18n.dir()}>
    <header className="ecommerce-page-header"><h1>{t("elearning.affiliate.dashboard")}</h1><p>{t("elearning.affiliate.intro")}</p></header>
    <section className="learner-account-panel"><h2>{t("elearning.affiliate.status")}</h2><p className="elearning-course-status">{status ? t(`elearning.programmes.${status}`) : t("elearning.affiliate.notApplied")}</p><p>{t(`elearning.affiliate.${status === "approved" ? "approvedHelp" : status === "suspended" ? "suspendedHelp" : "applicationHelp"}`)}</p>
      {account.settings.affiliates_enabled && <Link className="ecommerce-secondary-button" to="/my-learning/affiliate/application">{t(!status || status === "not_approved" ? "elearning.affiliate.apply" : "elearning.affiliate.application")}</Link>}
    </section>
    <ReferralInvitation referrals={referrals} academy={site} />
    {referrals === null && <p role="alert">{t("elearning.referrals.loadError")}</p>}
    {referrals?.available && <div className="learner-account-stats">
      <section className="learner-account-panel"><h2>{t("elearning.programmes.referrals")}</h2><p>{t("elearning.referrals.counts", { referred: referrals.referred_count, earned: referrals.earned_count })}</p><Link to="/my-learning/referrals">{t("elearning.affiliate.referralLink")}</Link></section>
      <section className="learner-account-panel"><h2>{t("elearning.referrals.rewards")}</h2>{referrals.balances.map(balance => <p key={`${balance.currency}:${balance.simulated}`}>{money(balance.amount, balance.currency)} · {t(balance.simulated ? "elearning.referrals.demoBalance" : "elearning.referrals.balance")}</p>)}<Link to="/my-learning/rewards">{t("elearning.affiliate.rewardDetails")}</Link></section>
      {account.wallet && <section className="learner-account-panel"><h2>{t("elearning.programmes.wallet")}</h2><p>{t("elearning.programmes.available")}: {money(account.wallet.available, account.wallet.currency)}</p>{account.wallet.verified_sales != null && <p>{t("elearning.programmes.sales")}: {account.wallet.verified_sales}</p>}<Link to="/my-learning/wallet">{t("elearning.programmes.wallet")}</Link>{account.capabilities.withdrawal && account.settings.withdrawals_enabled && <p><Link to="/my-learning/withdrawals">{t("elearning.programmes.withdrawal")}</Link></p>}</section>}
    </div>}
    <section className="learner-account-panel"><h2>{t("elearning.affiliate.recentActivity")}</h2>{(referrals?.history || []).slice(0, 3).map(row => <p key={row.id}>{new Date(row.reversed_at || row.earned_at || row.created_at).toLocaleDateString(i18n.language)} · {t(`elearning.referrals.${row.status}`)} · {money(row.amount, row.currency)}{row.simulated && ` · ${t("elearning.referrals.demo")}`}</p>)}{account.withdrawals.slice(0, 3).map(row => <p key={row.id}>{new Date(row.updated_at || row.created_at).toLocaleDateString(i18n.language)} · {t("elearning.programmes.withdrawal")} · {t(`elearning.programmes.${row.status}`)}</p>)}<Link to="/my-learning/notifications">{t("sidebar.notifications")}</Link></section>
  </section>;
}

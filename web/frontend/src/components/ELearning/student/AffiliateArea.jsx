import { useEffect, useState } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowDownCircle, Award, Clock, KeyRound, MousePointerClick, ShoppingCart, Wallet } from "lucide-react";
import { apiFetch, getApiUrl } from "../../../utils/apiClient";
import { formatMoney, latestAffiliate, pendingRewards, referralState, referralView } from "../../../utils/studentFinance";
import ELearningSkeleton from "../ELearningSkeleton";
import AcademyProgrammesPage from "../AcademyProgrammesPage";
import NotificationsPage from "../../DashboardBuilder/NotificationsPage";
import useStudentData from "./useStudentData";
import { ReferralLink } from "./StudentReferral";
import { StudentWallet, StudentWithdraw, WalletHistory } from "./StudentWallet";
import { StatCard, StatusPill, StudentPage } from "./StudentParts";

/** Not applied, Under Review, Not Approved and Suspended (website document §10). */
function AffiliateStatus({ application, paths }) {
  const { t } = useTranslation("dashboard");
  const status = application?.status || "none";
  const apply = paths?.affiliate || "/my-learning/affiliate/application";
  return <StudentPage title={t("elearning.affiliateArea.title")}>
    <section className="student-panel" data-testid={`affiliate-${status}`}>
      {application && <StatusPill status={status}>{t(`elearning.affiliateArea.status_${status}`)}</StatusPill>}
      <p>{t(`elearning.affiliateArea.help_${status}`)}</p>
      {(status === "none" || status === "not_approved") && <Link className="ecommerce-primary-button" to={apply}>{t("elearning.student.becomeAffiliate")}</Link>}
    </section>
  </StudentPage>;
}

function Overview({ data }) {
  const { t, i18n } = useTranslation("dashboard");
  const wallet = data.programmes?.wallet, money = value => formatMoney(value, wallet?.currency, i18n.language);
  return <StudentPage title={t("elearning.affiliateArea.title")} intro={t("elearning.affiliateArea.intro")}>
    <StatusPill status="approved">{t("elearning.affiliateArea.status_approved")}</StatusPill>
    <div className="stat-grid">
      <StatCard icon={MousePointerClick} label={t("elearning.affiliateArea.totalClicks")} value={data.referrals?.clicks == null ? "—" : Number(data.referrals.clicks).toLocaleString(i18n.language)} detail={data.referrals?.clicks == null ? t("elearning.affiliateArea.clicksPending") : undefined} to="/my-learning/affiliate/clicks" />
      <StatCard icon={ShoppingCart} label={t("elearning.affiliateArea.successfulSales")} value={String(Number(wallet?.verified_sales) || 0)} to="/my-learning/affiliate/sales" />
      <StatCard icon={Clock} label={t("elearning.student.pendingRewards")} value={money(pendingRewards(data.referrals))} to="/my-learning/affiliate/rewards" />
      <StatCard icon={Wallet} label={t("elearning.student.availableBalance")} value={money(wallet?.available)} to="/my-learning/affiliate/wallet" />
      <StatCard icon={Award} label={t("elearning.student.totalEarned")} value={money(wallet?.total_earned)} />
      <StatCard icon={ArrowDownCircle} label={t("elearning.student.totalWithdrawn")} value={money(wallet?.total_withdrawn)} />
    </div>
    <Link className="ecommerce-primary-button" to="/my-learning/affiliate/link">{t("elearning.affiliateArea.referralLink")}</Link>
  </StudentPage>;
}

/** Sales: every referred sign-up and purchase. Rewards: purchases only. */
function ReferralRows({ data, rewards }) {
  const { t, i18n } = useTranslation("dashboard");
  const rows = (data.referrals?.history || []).filter(row => !rewards || !referralState(row).signup);
  if (!rows.length) return <p className="student-empty">{t(rewards ? "elearning.student.noTransactions" : "elearning.affiliateArea.noSales")}</p>;
  return <div className="affiliate-table-scroll"><table className="student-table">
    <thead><tr><th scope="col">{t("elearning.student.column_date")}</th><th scope="col">{t(rewards ? "elearning.student.column_amount" : "elearning.affiliateArea.column_sale")}</th><th scope="col">{t("elearning.student.column_status")}</th></tr></thead>
    <tbody>{rows.map(row => {
      const { signup, reward } = referralState(row);
      const sale = signup ? "signup" : reward === "reversed" ? "refunded" : reward === "rejected" ? "rejected" : "purchased";
      return <tr key={row.id}>
        <td>{new Date(rewards ? row.reversed_at || row.earned_at || row.created_at : row.created_at).toLocaleDateString(i18n.language)}</td>
        <td dir={rewards ? "ltr" : undefined}>{rewards ? `+${formatMoney(row.amount, row.currency, i18n.language)}` : t(row.simulated ? "elearning.student.rewardTestDescription" : "elearning.student.rewardDescription")}</td>
        <td>{rewards ? <StatusPill status={reward === "available" ? "earned" : reward}>{t(`elearning.student.reward_${reward}`)}</StatusPill>
          : <StatusPill status={{ signup: "pending", purchased: "earned", refunded: "reversed", rejected: "rejected" }[sale]}>{t(`elearning.affiliateArea.sale_${sale}`)}</StatusPill>}</td>
      </tr>;
    })}</tbody>
  </table></div>;
}

/** Clicks on the affiliate's link and how many became successful sales. */
function Clicks({ data }) {
  const { t, i18n } = useTranslation("dashboard");
  const clicks = data.referrals?.clicks, sales = Number(data.programmes?.wallet?.verified_sales) || 0;
  return <StudentPage title={t("elearning.affiliateArea.clicks")} intro={t("elearning.affiliateArea.clicksIntro")}>
    {clicks == null ? <section className="student-panel"><p>{t("elearning.affiliateArea.clicksPending")}</p></section> : <div className="stat-grid">
      <StatCard icon={MousePointerClick} label={t("elearning.affiliateArea.totalClicks")} value={Number(clicks).toLocaleString(i18n.language)} />
      <StatCard icon={ShoppingCart} label={t("elearning.affiliateArea.successfulSales")} value={sales.toLocaleString(i18n.language)} />
    </div>}
  </StudentPage>;
}

/** Affiliate profile: account details only (no course list). */
function Profile() {
  const { t } = useTranslation("dashboard");
  const [user, setUser] = useState(null);
  useEffect(() => {
    let active = true;
    apiFetch(getApiUrl("/auth/user_status"), { cache: "no-store" }).then(response => response.ok ? response.json() : null).then(value => { if (active) setUser(value?.user || null); }).catch(() => {});
    return () => { active = false; };
  }, []);
  return <StudentPage title={t("elearning.affiliateArea.profile")}>
    <section className="student-panel">
      <h2 dir="auto">{[user?.first_name, user?.last_name].filter(Boolean).join(" ") || t("elearning.affiliateArea.profile")}</h2>
      {user?.email && <p dir="ltr" className="student-note">{user.email}</p>}
      <Link className="ecommerce-secondary-button" to="/my-learning/account/password"><KeyRound size={17} aria-hidden="true" />{t("elearning.learner.changePassword")}</Link>
    </section>
  </StudentPage>;
}

/**
 * EH / Affiliate dashboard (website document §20): for approved affiliates who
 * did not buy the course — no course or Tuition Support here.
 */
export default function AffiliateArea() {
  const { t, i18n } = useTranslation("dashboard");
  const data = useStudentData({ withCourse: false });
  if (data.loading) return <ELearningSkeleton label={t("elearning.loading")} direction={i18n.dir()} />;
  const application = latestAffiliate(data.programmes);
  const approved = application?.status === "approved" && referralView(data.referrals) === "link";
  const academy = data.learning?.academy;
  const gated = element => approved ? element : <AffiliateStatus application={application} paths={data.programmes?.application_paths} />;
  return <Routes>
    <Route index element={gated(<Overview data={data} />)} />
    <Route path="application" element={<AcademyProgrammesPage key="affiliate-application" affiliateOnly />} />
    <Route path="link" element={gated(<StudentPage title={t("elearning.affiliateArea.referralLink")}><ReferralLink referrals={data.referrals} academy={academy} /></StudentPage>)} />
    <Route path="clicks" element={gated(<Clicks data={data} />)} />
    <Route path="sales" element={gated(<StudentPage title={t("elearning.affiliateArea.sales")} intro={t("elearning.affiliateArea.salesIntro")}><section className="student-panel"><ReferralRows data={data} /></section></StudentPage>)} />
    <Route path="rewards" element={gated(<StudentPage title={t("elearning.affiliateArea.rewards")} intro={t("elearning.student.rewardRules")}><section className="student-panel"><ReferralRows data={data} rewards /></section></StudentPage>)} />
    <Route path="wallet" element={gated(<StudentWallet />)} />
    <Route path="withdraw" element={gated(<StudentWithdraw walletPath="/my-learning/affiliate/wallet" />)} />
    <Route path="transactions" element={gated(<StudentPage title={t("elearning.affiliateArea.transactions")}><WalletHistory referrals={data.referrals} withdrawals={data.programmes?.withdrawals || []} currency={data.programmes?.wallet?.currency} /></StudentPage>)} />
    <Route path="notifications" element={<NotificationsPage />} />
    <Route path="profile" element={<Profile />} />
    <Route path="*" element={gated(<Overview data={data} />)} />
  </Routes>;
}

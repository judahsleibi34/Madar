import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Award, Check, Copy, Mail, MessageCircle, MousePointerClick, Send, Share2, ShoppingCart, Wallet } from "lucide-react";
import { formatMoney, latestAffiliate, pendingRewards, referralView, shareTargets, tuitionProgress } from "../../../utils/studentFinance";
import ELearningSkeleton from "../ELearningSkeleton";
import LearningErrorNotice from "../LearningErrorNotice";
import { academyPath } from "../AcademyNav";
import useStudentData from "./useStudentData";
import { ProgressBar, StatCard, StatusPill, StudentPage } from "./StudentParts";

const SHARE_ICONS = { whatsapp: MessageCircle, facebook: Share2, instagram: Share2, telegram: Send, email: Mail };

/** Tuition Support referral progress (website document §11C/D, §16). */
export function TuitionProgress({ wallet, title, children }) {
  const { t } = useTranslation("dashboard");
  const { sales, threshold, remaining, eligible } = tuitionProgress(wallet);
  return <section className="student-panel tuition-progress">
    <h2>{title || t("elearning.student.tuitionSupport")}</h2>
    <StatusPill status={eligible ? "eligible" : "locked"}>{t(eligible ? "elearning.student.tuitionEligible" : "elearning.student.tuitionLocked")}</StatusPill>
    {!eligible && <p>{t("elearning.student.tuitionLockedHelp", { count: threshold })}</p>}
    <p><strong>{t("elearning.student.successfulSales", { sales: Math.min(sales, threshold), threshold })}</strong>{!eligible && <> · {t("elearning.student.remainingSales", { count: remaining })}</>}</p>
    <ProgressBar value={Math.min(sales, threshold)} max={threshold} label={t("elearning.student.tuitionProgress")} />
    <small>{t("elearning.student.tuitionLevelNote")}</small>
    {children}
  </section>;
}

export function ReferralLink({ referrals, academy }) {
  const { t } = useTranslation("dashboard");
  const [copied, setCopied] = useState("");
  const url = new URL(academy?.subdomain ? academyPath(academy) : "/", window.location.origin);
  url.searchParams.set("ref", referrals.code);
  const link = url.href;
  async function copy(target = "link") {
    try { await navigator.clipboard.writeText(link); setCopied(target); }
    catch { setCopied("help"); }
  }
  return <section className="student-panel referral-link-panel">
    <h2>{t("elearning.student.yourReferralLink")}</h2>
    <div className="referral-link-row">
      <input aria-label={t("elearning.student.yourReferralLink")} value={link} readOnly dir="ltr" onFocus={event => event.target.select()} />
      <button type="button" className="ecommerce-primary-button" onClick={() => copy()}>{copied === "link" ? <Check size={17} aria-hidden="true" /> : <Copy size={17} aria-hidden="true" />}{t(copied === "link" ? "elearning.accountPage.copied" : "elearning.student.copyLink")}</button>
    </div>
    <div className="referral-share" role="group" aria-label={t("elearning.student.shareOn")}>
      {shareTargets(link, t("elearning.student.shareMessage")).map(([key, name, href]) => {
        const Icon = SHARE_ICONS[key];
        return href ? <a key={key} className="referral-share-button" href={href} target="_blank" rel="noopener noreferrer"><Icon size={17} aria-hidden="true" />{name}</a>
          : <button key={key} type="button" className="referral-share-button" onClick={() => copy(key)}><Icon size={17} aria-hidden="true" />{copied === key ? t("elearning.student.copiedForInstagram") : name}</button>;
      })}
    </div>
    <p role="status" className="referral-copy-status">{copied === "help" ? t("elearning.accountPage.copyHelp") : ""}</p>
  </section>;
}

/** EH / My Referral (website document §16): purchased and not-purchased versions. */
export default function StudentReferral() {
  const { t, i18n } = useTranslation("dashboard");
  const data = useStudentData({ withCourse: false });
  if (data.loading) return <ELearningSkeleton label={t("elearning.loading")} direction={i18n.dir()} />;
  const { referrals, programmes } = data, academy = data.learning?.academy;
  const view = referralView(referrals);
  if (view === "unavailable") return <StudentPage title={t("elearning.student.myReferral")}><LearningErrorNotice as="p">{t("elearning.referrals.unavailable")}</LearningErrorNotice></StudentPage>;
  if (view === "invite") {
    const affiliate = latestAffiliate(programmes);
    return <StudentPage title={t("elearning.student.myReferral")}>
      <section className="student-panel student-invite" data-testid="referral-invite">
        <ShoppingCart size={28} aria-hidden="true" />
        {/* Website document §16, word for word. */}
        <p>{t("elearning.student.notPurchasedHelp")}</p>
        {affiliate && affiliate.status !== "not_approved"
          ? <StatusPill status={affiliate.status}>{t(`elearning.programmes.${affiliate.status}`)}</StatusPill>
          : <Link className="ecommerce-primary-button" to={programmes?.application_paths?.affiliate || "/my-learning/affiliate/application"}>{t("elearning.student.becomeAffiliate")}</Link>}
      </section>
    </StudentPage>;
  }
  const wallet = programmes?.wallet || referrals.wallet, currency = wallet?.currency || referrals.currency;
  const money = value => formatMoney(value, currency, i18n.language);
  return <StudentPage title={t("elearning.student.myReferral")} intro={t("elearning.student.referralIntro", { reward: money(referrals.reward_amount) })}>
    <ReferralLink referrals={referrals} academy={academy} />
    <div className="stat-grid">
      {referrals.clicks != null && <StatCard icon={MousePointerClick} label={t("elearning.student.referralClicks")} value={Number(referrals.clicks).toLocaleString(i18n.language)} />}
      <StatCard icon={ShoppingCart} label={t("elearning.student.successfulCourseSales")} value={String(tuitionProgress(wallet).sales)} />
      <StatCard icon={Wallet} label={t("elearning.student.pendingRewards")} value={money(pendingRewards(referrals))} />
      <StatCard icon={Wallet} label={t("elearning.student.availableRewards")} value={money(wallet?.available)} to="/my-learning/wallet" />
      <StatCard icon={Award} label={t("elearning.student.totalEarned")} value={money(wallet?.total_earned)} />
    </div>
    <TuitionProgress wallet={wallet || programmes?.eligibility} />
    <p className="student-note">{t("elearning.student.rewardRules", { reward: money(referrals.reward_amount) })}</p>
  </StudentPage>;
}

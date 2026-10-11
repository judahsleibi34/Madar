import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, Copy, Share2 } from "lucide-react";
import { academyPath } from "./AcademyNav";

export default function ReferralInvitation({ referrals, academy }) {
  const { t, i18n } = useTranslation("dashboard");
  const [copyState, setCopyState] = useState("");
  if (!referrals?.available || !referrals.enabled || !referrals.code) return null;
  const url = academy?.subdomain ? new URL(academyPath(academy), window.location.origin) : null;
  if (url) url.searchParams.set("ref", referrals.code);
  const invitation = url?.href;
  const reward = new Intl.NumberFormat(i18n.language, { style: "currency", currency: referrals.currency }).format(Number(referrals.reward_amount));
  async function copy() {
    try { await navigator.clipboard.writeText(invitation); setCopyState("copied"); }
    catch { setCopyState("copyHelp"); }
  }
  async function share() {
    try { await navigator.share({ url: invitation }); }
    catch (error) { if (error.name !== "AbortError") setCopyState("copyHelp"); }
  }
  return <aside className="learner-account-panel learner-account-referral">
    <span className="learner-account-share-icon"><Share2 size={25} aria-hidden="true" /></span>
    <h2>{t("elearning.accountPage.inviteFriends")}</h2><p>{t("elearning.referrals.inviteHelp", { reward })}</p>
    <p>{t("elearning.affiliate.referralCode")}: <strong dir="ltr">{referrals.code}</strong></p>
    {invitation ? <><label htmlFor="learner-invitation-link">{t("elearning.accountPage.invitationLink")}</label><input id="learner-invitation-link" value={invitation} readOnly dir="ltr" onFocus={event => event.target.select()} /><button className="ecommerce-primary-button" onClick={copy}>{copyState === "copied" ? <Check size={17} /> : <Copy size={17} />}{t(`elearning.accountPage.${copyState === "copied" ? "copied" : "copyLink"}`)}</button>{navigator.share && <button className="ecommerce-secondary-button" onClick={share}>{t("elearning.affiliate.share")}</button>}<small>{t("elearning.referrals.linkHelp")}</small><p role="status">{copyState === "copyHelp" ? t("elearning.accountPage.copyHelp") : ""}</p></> : <p>{t("elearning.accountPage.inviteUnavailable")}</p>}
  </aside>;
}

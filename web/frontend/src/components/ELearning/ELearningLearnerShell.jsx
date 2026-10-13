import { useCallback, useContext, useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Bell, Award, BadgeCheck, BookOpen, ClipboardList, CreditCard, Globe2, Home, LayoutDashboard, Library, Menu, Share2, UserRound, Wallet, X } from "lucide-react";
import { getAcademyAppearance } from "../../services/academyAppearance";
import { getPageBuilderThemeVars } from "../PageBuilder/core/PageBuilder.theme";
import { apiFetch, getApiUrl } from "../../utils/apiClient";
import { resolveMediaUrl } from "../../utils/media";
import { academyPath } from "./AcademyNav";
import "../../styles/elearning-learner-shell.css";
import { NotificationProvider } from "../../notifications/NotificationProvider";
import { NotificationContext } from "../../notifications/NotificationContext";
import NotificationToastViewport from "../../notifications/NotificationToastViewport";
import useAcademyCapabilities from "../../hooks/useAcademyCapabilities";
import { fetchReferralAccount } from "../../services/elearningPlayer";
import useLearningDrawer from "../../hooks/useLearningDrawer";

export default function ELearningLearnerShell({ site: suppliedSite, children }) {
  const notifications = useContext(NotificationContext);
  const site = getAcademyAppearance(suppliedSite);
  const theme = getPageBuilderThemeVars(site?.theme);
  const { t, i18n } = useTranslation("dashboard");
  const location = useLocation();
  const [drawerPath, setDrawerPath] = useState(null);
  const open = drawerPath === location.pathname;
  const setOpen = value => setDrawerPath(value ? location.pathname : null);
  const [user, setUser] = useState(null);
  const [reviewCapabilities, setReviewCapabilities] = useState(null);
  useEffect(() => {
    if (!user?.id) return;
    let active = true;
    Promise.resolve().then(() => apiFetch(getApiUrl("/elearning/assessment-capabilities"), {cache:"no-store"})).then(response => response?.ok ? response.json() : null).then(value => { if (active) setReviewCapabilities({identity:user.id, ...value}); }).catch(() => {});
    return () => { active=false; };
  }, [user?.id]);
  const [finance, setFinance] = useState(null);
  useEffect(() => { let active = true; Promise.resolve().then(() => fetchReferralAccount()).then(value => { if (active) setFinance(value); }).catch(() => {}); return () => { active = false; }; }, []);
  const academyAccess = useAcademyCapabilities(user);
  useEffect(() => {
    let active = true;
    apiFetch(getApiUrl("/auth/user_status"), { cache: "no-store" })
      .then(response => response.ok ? response.json() : null)
      .then(data => { if (active) setUser(data?.user || null); }).catch(() => {});
    return () => { active = false; };
  }, []);
  const panelRef = useRef(null);
  const closeDrawer = useCallback(() => setDrawerPath(null), []);
  useLearningDrawer(open, panelRef, closeDrawer);
  const base = site ? academyPath(site) : "/my-learning";
  const home = site ? base : "/my-learning";
  // Website document §14: the EduHope student navigation (opt-in per academy).
  const studentLinks = site?.experience?.studentDashboard === true && [
    [home, t("elearning.academy.home"), Home],
    ["/my-learning/dashboard", t("elearning.student.navDashboard"), LayoutDashboard],
    ["/my-learning/course", t("elearning.student.myCourse"), BookOpen],
    ["/my-learning/exams", t("elearning.student.examsCertificates"), Award],
    ["/my-learning/referral", t("elearning.student.myReferral"), Share2],
    ["/my-learning/wallet", t("elearning.student.wallet"), Wallet],
    ["/my-learning/withdraw", t("elearning.student.withdraw"), CreditCard],
    ["/my-learning/applications", t("elearning.student.applications"), ClipboardList],
    ["/my-learning/notifications", t("sidebar.notifications"), Bell],
    ["/my-learning/account", t("elearning.student.profileSettings"), UserRound],
  ];
  const links = studentLinks || [
    ...(site ? [[home, t("elearning.academy.home"), Home]] : []),
    ["/my-learning/dashboard", t("sidebar.dashboard"), Library],
    ["/my-learning", t("elearning.player.myLearning"), BookOpen],
    [site ? `${base}/courses` : "/my-learning/catalog", t("elearning.commerce.catalog"), Library],
    ["/my-learning/plans", t("elearning.commerce.myPlans"), CreditCard],
    ...(site?.certificates_enabled !== false ? [["/my-learning/certificates", t("elearning.certificates.myCertificates"), Award]] : []),
    ...(academyAccess?.capabilities?.affiliate && academyAccess?.programme_flags?.affiliate ? [["/my-learning/affiliate", t("elearning.affiliate.dashboard"), CreditCard]] : []),
    ...(academyAccess?.capabilities?.exchange && academyAccess?.programme_flags?.exchange && academyAccess?.exchange_intake_available ? [[site?.application_paths?.exchange || "/my-learning/exchange", t("elearning.programmes.exchange"), CreditCard]] : []),
    ...(["tuition"].some(key => academyAccess?.capabilities?.[key] && academyAccess?.programme_flags?.[key]) ? [["/my-learning/programmes", t("elearning.owner.applications"), CreditCard]] : []),
    ...(finance?.available && (finance.enabled || finance.history?.length) ? [["/my-learning/referrals", t("elearning.programmes.referrals"), CreditCard], ["/my-learning/rewards", t("elearning.referrals.rewards"), Award]] : []),
    ...(finance?.wallet ? [["/my-learning/wallet", t("elearning.programmes.wallet"), CreditCard]] : []),
    ...(reviewCapabilities?.identity === user?.id && reviewCapabilities?.can_review ? [["/my-learning/assessment-reviews", t("elearning.assessment.reviews"), BookOpen]] : []),
    ...(academyAccess?.form_reviews_available && academyAccess?.capabilities?.forms ? [["/my-learning/form-responses", t("elearning.forms_review.my_submissions"), BookOpen]] : []),
    ["/my-learning/notifications", t("sidebar.notifications"), Bell],
    ["/my-learning/account", t("elearning.learner.account"), UserRound],
  ];
  async function signOut() {
    const response = await apiFetch(getApiUrl("/auth/log_out"), { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    if (response.ok) window.location.assign(site ? base : "/login");
  }
  const content = <div className="learning-shell" dir={i18n.dir()} lang={i18n.language} style={theme}>
    <header className="learning-shell-header">
      <button className="learning-drawer-toggle" aria-controls="learning-navigation" aria-expanded={open} aria-label={t("elearning.academy.menu")} onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button>
      <Link className="learning-shell-brand" to={home}>{site?.logo_url ? <img className="learning-shell-logo" src={resolveMediaUrl(site.logo_url)} alt="" /> : <span className="learning-shell-mark" aria-hidden="true">{(site?.brand || "M").slice(0,1).toUpperCase()}</span>}{site?.brand || t("elearning.player.myLearning")}</Link>
      <div className="learning-shell-actions">
      {site?.institution?.member && site.institution.label && <span className="learning-shell-institution"><BadgeCheck size={16} aria-hidden="true" />{site.institution.label}</span>}
      <Link className="learning-shell-user" to="/my-learning/account"><UserRound size={18} aria-hidden="true" />{[user?.first_name, user?.last_name].filter(Boolean).join(" ") || t("elearning.learner.account")}</Link>
      <button type="button" className="learning-shell-language" lang={i18n.language.startsWith("ar") ? "en" : "ar"} aria-label={i18n.language.startsWith("ar") ? "English" : "العربية"} title={i18n.language.startsWith("ar") ? "English" : "العربية"} onClick={() => i18n.changeLanguage(i18n.language.startsWith("ar") ? "en" : "ar")}><Globe2 size={20} aria-hidden="true" /></button>
      <button type="button" className="learning-shell-signout" onClick={signOut}>{t("elearning.learner.signOut")}</button>
      </div>
    </header>
    {open && <button className="learning-drawer-backdrop" aria-label={t("elearning.learner.closeMenu")} onClick={() => setOpen(false)} />}
    <div className="learning-shell-layout">
      <aside ref={panelRef} tabIndex={-1} role={open ? "dialog" : undefined} aria-modal={open || undefined} aria-label={t("elearning.academy.navigation")} id="learning-navigation" className={`learning-shell-sidebar${open ? " is-open" : ""}`}>
        <button className="learning-drawer-close" onClick={closeDrawer} aria-label={t("elearning.learner.closeMenu")}><X /></button>
        <nav aria-label={t("elearning.academy.navigation")}>{links.map(([to, label, Icon], index) => <NavLink key={`${to}:${index}`} end={to === home || to === "/my-learning"} className={({ isActive }) => isActive || (to === (studentLinks ? "/my-learning/course" : "/my-learning") && location.pathname.startsWith("/my-learning/courses/")) ? "active" : undefined} to={to}><Icon size={19} aria-hidden="true" />{label}{to === "/my-learning/notifications" && <LearnerUnreadBadge />}</NavLink>)}</nav>
      </aside>
      <div className="learning-shell-content">{children}</div>
    </div>
  </div>;
  return notifications ? content : <NotificationProvider user={user}>{content}<NotificationToastViewport /></NotificationProvider>;
}

function LearnerUnreadBadge() {
 const value = useContext(NotificationContext);
 return value?.unreadCount > 0 ? <span className="learning-unread-count">{value.unreadCount}</span> : null;
}

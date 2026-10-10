import { useCallback, useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Award, BookOpen, CreditCard, Globe2, Home, Library, LogOut, Menu, UserRound, X } from "lucide-react";
import { getAcademyAppearance } from "../../services/academyAppearance";
import { getPageBuilderThemeVars } from "../PageBuilder/core/PageBuilder.theme";
import { apiFetch, getApiUrl } from "../../utils/apiClient";
import { resolveMediaUrl } from "../../utils/media";
import { academyPath } from "./AcademyNav";
import "../../styles/elearning-learner-shell.css";
import useLearningDrawer from "../../hooks/useLearningDrawer";

export default function ELearningLearnerShell({ site: suppliedSite, children }) {
  const site = getAcademyAppearance(suppliedSite);
  const theme = getPageBuilderThemeVars(site?.theme);
  const { t, i18n } = useTranslation("dashboard");
  const location = useLocation();
  const [drawerPath, setDrawerPath] = useState(null);
  const open = drawerPath === location.pathname;
  const setOpen = value => setDrawerPath(value ? location.pathname : null);
  const [user, setUser] = useState(null);
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
  const home = site ? `${base}/dashboard` : "/my-learning";
  const links = [
    [home, t("elearning.academy.home"), Home],
    ["/my-learning", t("elearning.player.myLearning"), BookOpen],
    [site ? `${base}/courses` : "/my-learning/catalog", t("elearning.commerce.catalog"), Library],
    ["/my-learning/plans", t("elearning.commerce.myPlans"), CreditCard],
    ["/my-learning/certificates", t("elearning.certificates.myCertificates"), Award],
    ["/my-learning/account", t("elearning.learner.account"), UserRound],
  ];
  async function signOut() {
    const response = await apiFetch(getApiUrl("/auth/log_out"), { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    if (response.ok) window.location.assign(site ? base : "/login");
  }
  return <div className="learning-shell" dir={i18n.dir()} lang={i18n.language} style={theme}>
    <header className="learning-shell-header">
      <button className="learning-drawer-toggle" aria-controls="learning-navigation" aria-expanded={open} aria-label={t("elearning.academy.menu")} onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button>
      <Link className="learning-shell-brand" to={home}>{site?.logo_url ? <img className="learning-shell-logo" src={resolveMediaUrl(site.logo_url)} alt="" /> : <span className="learning-shell-mark" aria-hidden="true">{(site?.brand || "M").slice(0,1).toUpperCase()}</span>}{site?.brand || t("elearning.player.myLearning")}</Link>
      <div className="learning-shell-actions">
      <Link className="learning-shell-user" to="/my-learning/account"><UserRound size={18} aria-hidden="true" />{[user?.first_name, user?.last_name].filter(Boolean).join(" ") || t("elearning.learner.account")}</Link>
      <button onClick={() => i18n.changeLanguage(i18n.language.startsWith("ar") ? "en" : "ar")}><Globe2 size={18} aria-hidden="true" />{i18n.language.startsWith("ar") ? "English" : "العربية"}</button>
      <button onClick={signOut}><LogOut size={18} aria-hidden="true" />{t("elearning.learner.signOut")}</button>
      </div>
    </header>
    {open && <button className="learning-drawer-backdrop" aria-label={t("elearning.learner.closeMenu")} onClick={() => setOpen(false)} />}
    <div className="learning-shell-layout">
      <aside ref={panelRef} tabIndex={-1} role={open ? "dialog" : undefined} aria-modal={open || undefined} aria-label={t("elearning.academy.navigation")} id="learning-navigation" className={`learning-shell-sidebar${open ? " is-open" : ""}`}>
        <button className="learning-drawer-close" onClick={closeDrawer} aria-label={t("elearning.learner.closeMenu")}><X /></button>
        <nav aria-label={t("elearning.academy.navigation")}>{links.map(([to, label, Icon], index) => <NavLink key={`${to}:${index}`} end={to === home || to === "/my-learning"} to={to}><Icon size={19} aria-hidden="true" />{label}</NavLink>)}</nav>
      </aside>
      <div className="learning-shell-content">{children}</div>
    </div>
  </div>;
}

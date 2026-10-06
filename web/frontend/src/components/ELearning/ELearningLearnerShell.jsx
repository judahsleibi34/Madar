import { useCallback, useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { BookOpen, GraduationCap, Home, Library, Menu, UserRound, X } from "lucide-react";
import { apiFetch, getApiUrl } from "../../utils/apiClient";
import { resolveMediaUrl } from "../../utils/media";
import { academyPath } from "./AcademyNav";
import "../../styles/elearning-learner-shell.css";
import useLearningDrawer from "../../hooks/useLearningDrawer";

export default function ELearningLearnerShell({ site, children }) {
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
  const links = [
    [base, t("elearning.academy.home"), Home],
    ["/my-learning", t("elearning.player.myLearning"), BookOpen],
    [site ? `${base}/courses` : "/my-learning/catalog", t("elearning.commerce.catalog"), Library],
    ["/my-learning/plans", t("elearning.commerce.myPlans"), BookOpen],
    ["/my-learning/certificates", t("elearning.certificates.myCertificates"), GraduationCap],
    ["/my-learning/account", t("elearning.learner.account"), UserRound],
  ];
  async function signOut() {
    const response = await apiFetch(getApiUrl("/auth/log_out"), { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    if (response.ok) window.location.assign(site ? base : "/login");
  }
  return <div className="learning-shell" dir={i18n.dir()} lang={i18n.language}>
    <header className="learning-shell-header">
      <button className="learning-drawer-toggle" aria-controls="learning-navigation" aria-expanded={open} aria-label={t("elearning.academy.menu")} onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button>
      <Link className="learning-shell-brand" to={base}>{site?.logo_url ? <img className="learning-shell-logo" src={resolveMediaUrl(site.logo_url)} alt="" /> : <GraduationCap aria-hidden="true" />}{site?.brand || t("elearning.player.myLearning")}</Link>
      <Link className="learning-shell-user" to="/my-learning/account"><UserRound size={18} aria-hidden="true" />{[user?.first_name, user?.last_name].filter(Boolean).join(" ") || t("elearning.learner.account")}</Link>
      {site?.management_path === "/e-learning/settings/academy" && <Link className="learning-admin-link" to={site.management_path}>{t("elearning.learner.backAdmin")}</Link>}
      <button onClick={() => i18n.changeLanguage(i18n.language.startsWith("ar") ? "en" : "ar")}>{i18n.language.startsWith("ar") ? "English" : "العربية"}</button>
      <button onClick={signOut}>{t("elearning.learner.signOut")}</button>
    </header>
    {open && <button className="learning-drawer-backdrop" aria-label={t("elearning.learner.closeMenu")} onClick={() => setOpen(false)} />}
    <div className="learning-shell-layout">
      <aside ref={panelRef} tabIndex={-1} role={open ? "dialog" : undefined} aria-modal={open || undefined} aria-label={t("elearning.academy.navigation")} id="learning-navigation" className={`learning-shell-sidebar${open ? " is-open" : ""}`}>
        <button className="learning-drawer-close" onClick={closeDrawer} aria-label={t("elearning.learner.closeMenu")}><X /></button>
        <nav aria-label={t("elearning.academy.navigation")}>{links.map(([to, label, Icon], index) => <NavLink key={`${to}:${index}`} end={to === base || to === "/my-learning"} to={to}><Icon size={19} aria-hidden="true" />{label}</NavLink>)}</nav>
      </aside>
      <div className="learning-shell-content">{children}</div>
    </div>
  </div>;
}

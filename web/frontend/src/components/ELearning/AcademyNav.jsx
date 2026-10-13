/* eslint-disable react-refresh/only-export-components -- shared route helper */
import { useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { GraduationCap, Languages, Menu, X } from "lucide-react";
import { getBrandedMadarSubdomain } from "../../utils/hostedAddress";
import { resolveMediaUrl } from "../../utils/media";
import LanguageText from "./AcademyLanguageText";
import "../../styles/elearning-academy.css";

export const academyPath = (site) => getBrandedMadarSubdomain(window.location.hostname) ? "/academy" : `/academy/${encodeURIComponent(site.subdomain)}`;
export default function AcademyNav({ site, authenticated = false, hasPlans = false, utility = false, chrome = {} }) {
  const { t, i18n } = useTranslation("dashboard");
  const [open, setOpen] = useState(false);
  const base = academyPath(site);
  return <header className={`academy-header${utility ? " academy-utility-header" : ""}`} dir={i18n.dir()}>
    {!utility && <Link className="academy-brand" to={base}>{site.logo_url ? <img src={resolveMediaUrl(site.logo_url)} alt="" /> : <span className="academy-brand-mark" aria-hidden="true">{site.brand?.slice(0, 1).toUpperCase()}</span>}<span>{site.brand}</span></Link>}
    <button className="academy-menu" aria-label={t("elearning.academy.menu")} aria-expanded={open} onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button>
    <nav aria-label={t("elearning.academy.navigation")} className={open ? "is-open" : ""} onClick={() => setOpen(false)}>
      <div className="academy-page-links">
      <NavLink end to={base}>{t("elearning.academy.home")}</NavLink><NavLink to={`${base}/courses`}>{t("elearning.academy.courses")}</NavLink>
      {hasPlans && <NavLink to={`${base}/plans`}>{t("elearning.academy.plans")}</NavLink>}
      </div>
      <div className="academy-account-links">
      {authenticated ? <Link className="academy-icon-action" to={`${base}/dashboard`} aria-label={t("elearning.player.myLearning")} title={t("elearning.player.myLearning")}><GraduationCap aria-hidden="true" /></Link> : <><Link to={`${base}/login`}>{t("elearning.learner.logIn")}</Link>{["open", "email_domain"].includes(site.academy_registration) && <Link className="academy-nav-signup" to={`${base}/login?register=1`}>{chrome.signUpLabel?.[i18n.language.startsWith("ar") ? "ar" : "en"] || t("elearning.learner.signUp")}</Link>}</>}
      {chrome.languageSwitcher === "text" ? <LanguageText language={i18n.language.startsWith("ar") ? "ar" : "en"} onChange={next => i18n.changeLanguage(next)} /> : <button type="button" className="academy-icon-action" lang={i18n.language.startsWith("ar") ? "en" : "ar"} aria-label={i18n.language.startsWith("ar") ? "English" : "العربية"} title={i18n.language.startsWith("ar") ? "English" : "العربية"} onClick={() => i18n.changeLanguage(i18n.language.startsWith("ar") ? "en" : "ar")}><Languages aria-hidden="true" /></button>}
      </div>
    </nav>
  </header>;
}

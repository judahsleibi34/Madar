/* eslint-disable react-refresh/only-export-components -- shared route helper */
import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Menu, X } from "lucide-react";
import { getBrandedMadarSubdomain } from "../../utils/hostedAddress";
import { resolveMediaUrl } from "../../utils/media";
import "../../styles/elearning-academy.css";

export const academyPath = (site) => getBrandedMadarSubdomain(window.location.hostname) ? "/academy" : `/academy/${encodeURIComponent(site.subdomain)}`;
export default function AcademyNav({ site, authenticated = false, hasPlans = false, utility = false }) {
  const { t, i18n } = useTranslation("dashboard");
  const [open, setOpen] = useState(false);
  const base = academyPath(site);
  return <header className={`academy-header${utility ? " academy-utility-header" : ""}`} dir={i18n.dir()}>
    {!utility && <Link className="academy-brand" to={base}>{site.logo_url ? <img src={resolveMediaUrl(site.logo_url)} alt="" /> : <span className="academy-brand-mark" aria-hidden="true">{site.brand?.slice(0, 1).toUpperCase()}</span>}<span>{site.brand}</span></Link>}
    <button className="academy-menu" aria-label={t("elearning.academy.menu")} aria-expanded={open} onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button>
    <nav aria-label={t("elearning.academy.navigation")} className={open ? "is-open" : ""} onClick={() => setOpen(false)}>
      <div className="academy-page-links">
      <Link to={base}>{t("elearning.academy.home")}</Link><Link to={`${base}/courses`}>{t("elearning.academy.courses")}</Link>
      {hasPlans && <Link to={`${base}/plans`}>{t("elearning.academy.plans")}</Link>}
      </div>
      <div className="academy-account-links">
      {authenticated ? <Link to={`${base}/dashboard`}>{t("elearning.player.myLearning")}</Link> : <><Link to={`${base}/login`}>{t("elearning.learner.logIn")}</Link>{["open", "email_domain"].includes(site.academy_registration) && <Link className="academy-nav-signup" to={`${base}/login?register=1`}>{t("elearning.learner.signUp")}</Link>}</>}
      <button onClick={() => i18n.changeLanguage(i18n.language.startsWith("ar") ? "en" : "ar")}>{i18n.language.startsWith("ar") ? "English" : "العربية"}</button>
      </div>
    </nav>
  </header>;
}

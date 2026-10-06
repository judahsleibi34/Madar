/* eslint-disable react-refresh/only-export-components -- shared route helper */
import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Menu, X, GraduationCap } from "lucide-react";
import { getBrandedMadarSubdomain } from "../../utils/hostedAddress";
import { resolveMediaUrl } from "../../utils/media";
import "../../styles/elearning-academy.css";

export const academyPath = (site) => getBrandedMadarSubdomain(window.location.hostname) ? "/academy" : `/academy/${encodeURIComponent(site.subdomain)}`;
export default function AcademyNav({ site, authenticated = false, hasPlans = false, utility = false }) {
  const { t, i18n } = useTranslation("dashboard");
  const [open, setOpen] = useState(false);
  const base = academyPath(site);
  return <header className={`academy-header${utility ? " academy-utility-header" : ""}`} dir={i18n.dir()}>
    {!utility && <Link className="academy-brand" to={base}>{site.logo_url ? <img src={resolveMediaUrl(site.logo_url)} alt="" /> : <GraduationCap aria-hidden="true" />}<span>{site.brand}</span></Link>}
    <button className="academy-menu" aria-label={t("elearning.academy.menu")} aria-expanded={open} onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button>
    <nav aria-label={t("elearning.academy.navigation")} className={open ? "is-open" : ""} onClick={() => setOpen(false)}>
      <Link to={base}>{t("elearning.academy.home")}</Link><Link to={`${base}/courses`}>{t("elearning.academy.courses")}</Link>
      {hasPlans && <Link to={`${base}/plans`}>{t("elearning.academy.plans")}</Link>}
      {authenticated ? <><Link to="/my-learning">{t("elearning.player.myLearning")}</Link><Link to="/my-learning/plans">{t("elearning.commerce.myPlans")}</Link><Link to="/my-learning/certificates">{t("elearning.certificates.myCertificates")}</Link></> : <><Link to={`${base}/login`}>{t("elearning.academy.signIn")}</Link>{["open", "email_domain"].includes(site.academy_registration) && <Link to={`${base}/login?register=1`}>{t("elearning.learner.createAccount")}</Link>}</>}
      <button onClick={() => i18n.changeLanguage(i18n.language.startsWith("ar") ? "en" : "ar")}>{i18n.language.startsWith("ar") ? "English" : "العربية"}</button>
    </nav>
  </header>;
}

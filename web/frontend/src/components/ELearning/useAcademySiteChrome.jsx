import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { GraduationCap, Languages } from "lucide-react";
import LanguageText from "./AcademyLanguageText";
import { createSiteChromeRenderers } from "../PageBuilder/core/PageBuilder.siteChrome";
import { getPublicPagePath } from "../PageBuilder/core/PageBuilder.routing";
import { getAcademyNavigationDestinations } from "../PageBuilder/core/PageBuilder.academyProfile";

export default function useAcademySiteChrome({ schema, basePath, authenticated, registration, activePage }) {
  const { t, i18n } = useTranslation("dashboard");
  const navigate = useNavigate();
  const location = useLocation();
  const query = new URLSearchParams(location.search);
  const continuation = new URLSearchParams();
  for (const key of ["returnTo", "ref"]) if (query.has(key)) continuation.set(key, query.get(key));
  const loginSearch = continuation.toString();
  continuation.set("register", "1");
  const language = i18n.language.startsWith("ar") ? "ar" : "en";
  // Optional tenant-owned header wording from the academy's published website.
  const chrome = schema?.academyChrome || {};
  const signUpLabel = chrome.signUpLabel?.[language] || t("elearning.learner.signUp");
  const textSwitcher = chrome.languageSwitcher === "text";
  const renderHeaderActions = () => <>
    {authenticated ? <Link className="academy-login-link academy-icon-action" to={`${basePath}/dashboard`} aria-label={t("elearning.player.myLearning")} title={t("elearning.player.myLearning")}><GraduationCap aria-hidden="true" /></Link> : <>
      <Link className="academy-login-link" to={`${basePath}/login${loginSearch ? `?${loginSearch}` : ""}`}>{t("elearning.learner.logIn")}</Link>
      {["open", "email_domain"].includes(registration) && <Link className="academy-signup-link" to={`${basePath}/login?${continuation}`}>{signUpLabel}</Link>}
    </>}
    {textSwitcher ? <LanguageText language={language} onChange={next => i18n.changeLanguage(next)} /> : <button type="button" className="academy-icon-action" lang={language === "ar" ? "en" : "ar"} aria-label={language === "ar" ? "English" : "العربية"} title={language === "ar" ? "English" : "العربية"} onClick={() => i18n.changeLanguage(language === "ar" ? "en" : "ar")}><Languages aria-hidden="true" /></button>}
  </>;
  return createSiteChromeRenderers({ project: schema || { pages: [] }, activePage, selected: { type: "", id: "" }, preview: true, publicRuntime: true,
    selectPage: id => { const page = schema?.pages.find(item => item.id === id); if (page) navigate(getPublicPagePath(basePath, page)); },
    setSelected: () => {}, navigateUrl: url => navigate(url), navigationDestinations: getAcademyNavigationDestinations(basePath), authenticated, renderHeaderActions,
    renderFooterActions: () => <button type="button" onClick={() => i18n.changeLanguage(language === "ar" ? "en" : "ar")}>English | العربية</button>,
    direction: i18n.dir(), chromeLabels: { menu: language === "ar" ? "فتح قائمة التنقّل" : "Open navigation menu", attribution: language === "ar" ? "مدعوم بمنصة مدار" : "Powered by Madar" },
  });
}

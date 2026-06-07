import { useEffect, useState } from "react";
import { NavLink, Link } from "react-router-dom";
import { Moon, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";

import LanguageSwitcher from "../LanguageSwitcher";
import logo from "../../assets/MadarTemplates/madar_header.svg";

const navItems = [
  { id: "home", labelKey: "nav.home", path: "/" },
  { id: "features", labelKey: "nav.features", path: "/features" },
  { id: "pricing", labelKey: "nav.pricing", path: "/pricing" },
  { id: "team", labelKey: "nav.team", path: "/team" },
  { id: "about", labelKey: "nav.about", path: "/about" },
  { id: "contact", labelKey: "nav.contact", path: "/contact" },
];

export default function Header({
  lang = "en",
  onLanguageChange,
  isLoggedIn = false,
  onLogout,
  themeMode = "light",
  onThemeModeChange,
}) {
  const { t } = useTranslation(["common", "public"]);
  const [menuOpen, setMenuOpen] = useState(false);

  const isRTL = lang === "ar";
  const isDark = themeMode === "dark";

  const finalNavItems = isLoggedIn
    ? [...navItems, { id: "dashboard", labelKey: "nav.dashboard", path: "/dashboard" }]
    : navItems;

  const closeMenu = () => {
    setMenuOpen(false);
  };

  const handleThemeClick = () => {
    if (typeof onThemeModeChange === "function") {
      onThemeModeChange(isDark ? "light" : "dark");
    }
  };

  const handleLangSelect = (code) => {
    setMenuOpen(false);

    if (typeof onLanguageChange === "function") {
      onLanguageChange(code);
    }
  };

  const handleLogout = () => {
    setMenuOpen(false);

    if (onLogout) {
      onLogout();
    }
  };

  useEffect(() => {
    function handleResize() {
      if (window.innerWidth > 1400) {
        setMenuOpen(false);
      }
    }

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    }

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  useEffect(() => {
    document.body.classList.toggle("mobile-menu-open", menuOpen);

    return () => {
      document.body.classList.remove("mobile-menu-open");
    };
  }, [menuOpen]);

  return (
    <>
      <header className="site-header" dir={isRTL ? "rtl" : "ltr"}>
        <Link to="/" className="brand" onClick={closeMenu}>
          <img className="logo" src={logo} alt={t("common:app.logoAlt")} />
          <h1 className="brand-name">{t("common:app.brand")}</h1>
        </Link>

        <nav className="nav-menu" aria-label={t("common:navigation.main")}>
          {finalNavItems.map((item) => (
            <NavLink
              key={item.id}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              {t(`public:${item.labelKey}`)}
            </NavLink>
          ))}
        </nav>

        <div className="header-right">
          <button
            type="button"
            className={`header-theme-toggle ${isDark ? "is-dark" : "is-light"}`}
            onClick={handleThemeClick}
            aria-label={
              isDark
                ? t("common:theme.switchLight")
                : t("common:theme.switchDark")
            }
            title={
              isDark
                ? t("common:theme.switchLight")
                : t("common:theme.switchDark")
            }
          >
            {isDark ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          {isLoggedIn && (
            <LanguageSwitcher
              current={lang}
              onChange={handleLangSelect}
              compact
              className="header-language-switcher"
            />
          )}

          {isLoggedIn ? (
            <button type="button" className="btn-signup" onClick={handleLogout}>
              {t("public:nav.logout")}
            </button>
          ) : (
            <>
              <Link to="/login" className="btn-login">
                {t("public:nav.login")}
              </Link>

              <Link to="/signup" className="btn-signup">
                {t("public:nav.signup")}
              </Link>

              <LanguageSwitcher
                current={lang}
                onChange={handleLangSelect}
                compact
                className="header-language-switcher"
              />
            </>
          )}

          <button
            type="button"
            className={`hamburger${menuOpen ? " open" : ""}`}
            onClick={() => setMenuOpen((open) => !open)}
            aria-label={
              menuOpen
                ? t("common:navigation.closeMenu")
                : t("common:navigation.openMenu")
            }
            aria-expanded={menuOpen}
            aria-controls="mobile-menu"
          >
            <span />
            <span />
            <span />
          </button>
        </div>
      </header>

      {menuOpen && (
        <>
          <button
            type="button"
            className="mobile-menu-backdrop"
            aria-label={t("common:navigation.closeMenu")}
            onClick={closeMenu}
          />

          <aside
            id="mobile-menu"
            className="mobile-menu"
            aria-label={t("common:navigation.mobile")}
            dir={isRTL ? "rtl" : "ltr"}
          >
            <div className="mobile-menu-head">
              <Link to="/" className="mobile-menu-brand" onClick={closeMenu}>
                <img src={logo} alt={t("common:app.logoAlt")} />
                <span>{t("common:app.brand")}</span>
              </Link>

              <button
                type="button"
                className="mobile-menu-close"
                onClick={closeMenu}
                aria-label={t("common:navigation.closeMenu")}
              >
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 20 20"
                  fill="none"
                  aria-hidden="true"
                >
                  <path
                    d="M5 5L15 15M15 5L5 15"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            </div>

            <div className="mobile-menu-body">
              <div className="mobile-menu-title">{t("common:navigation.menu")}</div>

              <button
                type="button"
                className={`mobile-theme-toggle ${isDark ? "is-dark" : "is-light"}`}
                onClick={handleThemeClick}
              >
                <span>
                  {isDark ? <Sun size={18} /> : <Moon size={18} />}
                  {t("common:theme.appearance")}
                </span>
                <strong>
                  {isDark ? t("common:theme.dark") : t("common:theme.light")}
                </strong>
              </button>

              <nav
                className="mobile-menu-links"
                aria-label={t("common:navigation.mobileLinks")}
              >
                {finalNavItems.map((item) => (
                  <NavLink
                    key={item.id}
                    to={item.path}
                    end={item.path === "/"}
                    className={({ isActive }) => (isActive ? "active" : "")}
                    onClick={closeMenu}
                  >
                    <span>{t(`public:${item.labelKey}`)}</span>

                    <svg
                      width="18"
                      height="18"
                      viewBox="0 0 18 18"
                      fill="none"
                      aria-hidden="true"
                    >
                      <path
                        d={isRTL ? "M11 4L6 9L11 14" : "M7 4L12 9L7 14"}
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </NavLink>
                ))}
              </nav>

              <div className="mobile-menu-auth">
                {isLoggedIn ? (
                  <button
                    type="button"
                    className="btn-signup mobile-auth-full"
                    onClick={handleLogout}
                  >
                    {t("public:nav.logout")}
                  </button>
                ) : (
                  <>
                    <Link
                      to="/login"
                      className="btn-login"
                      onClick={closeMenu}
                    >
                      {t("public:nav.login")}
                    </Link>

                    <Link
                      to="/signup"
                      className="btn-signup"
                      onClick={closeMenu}
                    >
                      {t("public:nav.signup")}
                    </Link>
                  </>
                )}
              </div>

              <div className="mobile-menu-lang-wrap">
                <span>{t("common:language.label")}</span>

                <LanguageSwitcher
                  current={lang}
                  onChange={handleLangSelect}
                  className="mobile-menu-lang"
                />
              </div>
            </div>
          </aside>
        </>
      )}
    </>
  );
}

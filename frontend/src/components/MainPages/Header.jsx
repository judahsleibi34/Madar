import { useState, useRef, useEffect } from "react";
import { NavLink, Link } from "react-router-dom";
import { Moon, Sun } from "lucide-react";
import logo from "../../assets/MadarTemplates/madar_header.svg";

const navItems = {
  en: [
    { id: "home", label: "Home", path: "/" },
    { id: "features", label: "Product Tour", path: "/features" },
    { id: "pricing", label: "Plans and Pricing", path: "/pricing" },
    { id: "team", label: "Madar Team", path: "/team" },
    { id: "about", label: "About Us", path: "/about" },
    { id: "contact", label: "Contact Us", path: "/contact" },
  ],
  ar: [
    { id: "home", label: "الرئيسية", path: "/" },
    { id: "features", label: "جولة المنتج", path: "/features" },
    { id: "pricing", label: "الخطط والأسعار", path: "/pricing" },
    { id: "team", label: "فريق مدار", path: "/team" },
    { id: "about", label: "من نحن", path: "/about" },
    { id: "contact", label: "تواصل معنا", path: "/contact" },
  ],
};

const authLabels = {
  en: {
    login: "Log In",
    signup: "Sign Up",
    logout: "Logout",
    dashboard: "Dashboard",
    openMenu: "Open menu",
    closeMenu: "Close menu",
    menu: "Menu",
    language: "Language",
    switchLight: "Switch to light mode",
    switchDark: "Switch to dark mode",
    appearance: "Appearance",
  },
  ar: {
    login: "تسجيل الدخول",
    signup: "إنشاء حساب",
    logout: "تسجيل الخروج",
    dashboard: "لوحة التحكم",
    openMenu: "فتح القائمة",
    closeMenu: "إغلاق القائمة",
    menu: "القائمة",
    language: "اللغة",
    switchLight: "التبديل إلى الوضع الفاتح",
    switchDark: "التبديل إلى الوضع الداكن",
    appearance: "المظهر",
  },
};

const langOptions = [
  { code: "en", label: "EN" },
  { code: "ar", label: "AR" },
];

export default function Header({
  lang = "en",
  onLanguageChange,
  isLoggedIn = false,
  onLogout,
  themeMode = "light",
  onThemeModeChange,
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [langOpen, setLangOpen] = useState(false);
  const langRef = useRef(null);

  const isRTL = lang === "ar";
  const isDark = themeMode === "dark";
  const items = navItems[lang] || navItems.en;
  const auth = authLabels[lang] || authLabels.en;
  const currentLang =
    langOptions.find((item) => item.code === lang) || langOptions[0];

  const finalNavItems = isLoggedIn
    ? [...items, { id: "dashboard", label: auth.dashboard, path: "/dashboard" }]
    : items;

  const closeMenu = () => {
    setMenuOpen(false);
  };

  const handleThemeClick = () => {
    if (typeof onThemeModeChange === "function") {
      onThemeModeChange(isDark ? "light" : "dark");
    }
  };

  useEffect(() => {
    function handleClickOutside(event) {
      if (langRef.current && !langRef.current.contains(event.target)) {
        setLangOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

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
        setLangOpen(false);
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

  const handleLangSelect = (code) => {
    setLangOpen(false);
    setMenuOpen(false);

    if (onLanguageChange) {
      onLanguageChange(code);
    }
  };

  const handleLogout = () => {
    setMenuOpen(false);

    if (onLogout) {
      onLogout();
    }
  };

  return (
    <>
      <header className="site-header" dir={isRTL ? "rtl" : "ltr"}>
        <Link to="/" className="brand" onClick={closeMenu}>
          <img className="logo" src={logo} alt="Madar logo" />
          <h1 className="brand-name">{isRTL ? "مدار" : "Madar"}</h1>
        </Link>

        <nav className="nav-menu" aria-label="Main navigation">
          {finalNavItems.map((item) => (
            <NavLink
              key={item.id}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="header-right">
          <button
            type="button"
            className={`header-theme-toggle ${isDark ? "is-dark" : "is-light"}`}
            onClick={handleThemeClick}
            aria-label={isDark ? auth.switchLight : auth.switchDark}
            title={isDark ? auth.switchLight : auth.switchDark}
          >
            {isDark ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          {isLoggedIn ? (
            <button type="button" className="btn-signup" onClick={handleLogout}>
              {auth.logout}
            </button>
          ) : (
            <>
              <Link to="/login" className="btn-login">
                {auth.login}
              </Link>

              <Link to="/signup" className="btn-signup">
                {auth.signup}
              </Link>
            </>
          )}

          <div className="lang-switcher" ref={langRef}>
            <button
              type="button"
              className="lang-toggle"
              onClick={() => setLangOpen((open) => !open)}
              aria-expanded={langOpen}
              aria-haspopup="listbox"
            >
              {currentLang.label}

              <svg
                className={`lang-chevron${langOpen ? " open" : ""}`}
                width="12"
                height="12"
                viewBox="0 0 12 12"
                fill="none"
                aria-hidden="true"
              >
                <path
                  d="M2 4L6 8L10 4"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>

            {langOpen && (
              <ul className="lang-dropdown" role="listbox">
                {langOptions.map((option) => (
                  <li key={option.code}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={option.code === lang}
                      className={option.code === lang ? "active" : ""}
                      onClick={() => handleLangSelect(option.code)}
                    >
                      {option.label}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <button
            type="button"
            className={`hamburger${menuOpen ? " open" : ""}`}
            onClick={() => setMenuOpen((open) => !open)}
            aria-label={menuOpen ? auth.closeMenu : auth.openMenu}
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
            aria-label={auth.closeMenu}
            onClick={closeMenu}
          />

          <aside
            id="mobile-menu"
            className="mobile-menu"
            aria-label="Mobile navigation"
            dir={isRTL ? "rtl" : "ltr"}
          >
            <div className="mobile-menu-head">
              <Link to="/" className="mobile-menu-brand" onClick={closeMenu}>
                <img src={logo} alt="Madar logo" />
                <span>{isRTL ? "مدار" : "Madar"}</span>
              </Link>

              <button
                type="button"
                className="mobile-menu-close"
                onClick={closeMenu}
                aria-label={auth.closeMenu}
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
              <div className="mobile-menu-title">{auth.menu}</div>

              <button
                type="button"
                className={`mobile-theme-toggle ${isDark ? "is-dark" : "is-light"}`}
                onClick={handleThemeClick}
              >
                <span>
                  {isDark ? <Sun size={18} /> : <Moon size={18} />}
                  {auth.appearance}
                </span>
                <strong>{isDark ? "Dark" : "Light"}</strong>
              </button>

              <nav className="mobile-menu-links" aria-label="Mobile menu links">
                {finalNavItems.map((item) => (
                  <NavLink
                    key={item.id}
                    to={item.path}
                    end={item.path === "/"}
                    className={({ isActive }) => (isActive ? "active" : "")}
                    onClick={closeMenu}
                  >
                    <span>{item.label}</span>

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
                    {auth.logout}
                  </button>
                ) : (
                  <>
                    <Link
                      to="/login"
                      className="btn-login"
                      onClick={closeMenu}
                    >
                      {auth.login}
                    </Link>

                    <Link
                      to="/signup"
                      className="btn-signup"
                      onClick={closeMenu}
                    >
                      {auth.signup}
                    </Link>
                  </>
                )}
              </div>

              <div className="mobile-menu-lang-wrap">
                <span>{auth.language}</span>

                <div className="mobile-menu-lang">
                  {langOptions.map((option) => (
                    <button
                      type="button"
                      key={option.code}
                      className={`lang-mobile-btn${
                        option.code === lang ? " active" : ""
                      }`}
                      onClick={() => handleLangSelect(option.code)}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </aside>
        </>
      )}
    </>
  );
}
import { useState, useRef, useEffect } from "react";
import { NavLink, Link } from "react-router-dom";
import logo from "../assets/madar_header.svg";

const navItems = {
  en: [
    { id: "home", label: "Home", path: "/" },
    { id: "features", label: "Features", path: "/features" },
    { id: "pricing", label: "Plans and Pricing", path: "/pricing" },
    { id: "team", label: "Madar Team", path: "/team" },
    { id: "about", label: "About Us", path: "/about" },
    { id: "contact", label: "Contact Us", path: "/contact" },
    
  ],
  ar: [
    { id: "home", label: "الرئيسية", path: "/" },
    { id: "features", label: "المميزات", path: "/features" },
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
  },
  ar: {
    login: "تسجيل الدخول",
    signup: "إنشاء حساب",
    logout: "تسجيل الخروج",
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
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [langOpen, setLangOpen] = useState(false);
  const langRef = useRef(null);

  const items = navItems[lang] || navItems.en;
  const auth = authLabels[lang] || authLabels.en;
  const currentLang =
    langOptions.find((item) => item.code === lang) || langOptions[0];

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
      if (window.innerWidth > 900) {
        setMenuOpen(false);
      }
    }

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, []);

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
    <header className="site-header">
      <Link to="/" className="brand" onClick={() => setMenuOpen(false)}>
        <img className="logo" src={logo} alt="Madar logo" />
        <h1 className="brand-name">{lang === "ar" ? "مدار" : "Madar"}</h1>
      </Link>

      <nav className="nav-menu" aria-label="Main navigation">
        {items.map((item) => (
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
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          aria-controls="mobile-menu"
        >
          <span />
          <span />
          <span />
        </button>
      </div>

      {menuOpen && (
        <nav
          id="mobile-menu"
          className="mobile-menu"
          aria-label="Mobile navigation"
        >
          {items.map((item) => (
            <NavLink
              key={item.id}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) => (isActive ? "active" : "")}
              onClick={() => setMenuOpen(false)}
            >
              {item.label}
            </NavLink>
          ))}

          <div className="mobile-menu-auth">
            {isLoggedIn ? (
              <button
                type="button"
                className="btn-signup"
                onClick={handleLogout}
              >
                {auth.logout}
              </button>
            ) : (
              <>
                <Link
                  to="/login"
                  className="btn-login"
                  onClick={() => setMenuOpen(false)}
                >
                  {auth.login}
                </Link>

                <Link
                  to="/signup"
                  className="btn-signup"
                  onClick={() => setMenuOpen(false)}
                >
                  {auth.signup}
                </Link>
              </>
            )}
          </div>

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
        </nav>
      )}
    </header>
  );
}
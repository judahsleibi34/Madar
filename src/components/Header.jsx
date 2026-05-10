import { useState } from "react";
import { NavLink } from "react-router-dom";
import LanguageSwitcher from "./LanguageSwitcher";
import logo from "../assets/madar_header.svg";

const navItems = {
  en: [
    { id: "home", label: "Home", path: "/" },
    { id: "about", label: "About Us", path: "/about" },
    { id: "features", label: "Features", path: "/features" },
    { id: "contact", label: "Contact Us", path: "/contact" },
    { id: "pricing", label: "Plans and Pricing", path: "/pricing" },
  ],
  ar: [
    { id: "home", label: "الرئيسية", path: "/" },
    { id: "about", label: "من نحن", path: "/about" },
    { id: "features", label: "المميزات", path: "/features" },
    { id: "contact", label: "تواصل معنا", path: "/contact" },
    { id: "pricing", label: "الخطط والأسعار", path: "/pricing" },
  ],
};

export default function Header({ lang, onLanguageChange }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const items = navItems[lang];

  return (
    <header className="site-header">
      <div className="brand">
        <img className="logo" src={logo} alt="Madar logo" />
        <h1 className="brand-name">{lang === "ar" ? "مدار" : "Madar"}</h1>
      </div>

      <nav className="nav-menu">
        {items.map((item) => (
          <NavLink
            key={item.id}
            to={item.path}
            end={item.path === "/"}
            className={({ isActive }) => isActive ? "active" : ""}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="header-right">
        <LanguageSwitcher current={lang} onChange={onLanguageChange} />
        <button
          className={"hamburger" + (menuOpen ? " open" : "")}
          onClick={() => setMenuOpen((o) => !o)}
          aria-label="Toggle menu"
        >
          <span />
          <span />
          <span />
        </button>
      </div>

      {menuOpen && (
        <nav className="mobile-menu">
          {items.map((item) => (
            <NavLink
              key={item.id}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) => isActive ? "active" : ""}
              onClick={() => setMenuOpen(false)}
            >
              {item.label}
            </NavLink>
          ))}
          <div className="mobile-menu-lang">
            <LanguageSwitcher
              current={lang}
              onChange={(code) => {
                onLanguageChange(code);
                setMenuOpen(false);
              }}
            />
          </div>
        </nav>
      )}
    </header>
  );
}
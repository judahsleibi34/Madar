import { NavLink } from "react-router-dom";
import logo from "../assets/madar_header.svg";

const navItems = {
  en: [
    { id: "home", label: "Home", path: "/" },
    { id: "features", label: "Product Tour", path: "/features" },
    { id: "pricing", label: "Plans and Pricing", path: "/pricing" },
    { id: "contact", label: "Contact Us", path: "/contact" },
  ],
  ar: [
    { id: "home", label: "الرئيسية", path: "/" },
    { id: "about", label: "من نحن", path: "/about" },
    { id: "features", label: "المميزات", path: "/features" },
    { id: "contact", label: "تواصل معنا", path: "/contact" },
    { id: "pricing", label: "الخطط والأسعار", path: "/pricing" },
  ],
};

const footerText = {
  en: {
    brand: "Madar",
    description:
      "An adaptive business management platform for creating and managing digital systems.",
    linksTitle: "Links",
    contactTitle: "Contact",
    rights: "All rights reserved.",
  },
  ar: {
    brand: "مدار",
    description:
      "منصة إدارة أعمال مرنة لإنشاء وإدارة الأنظمة الرقمية.",
    linksTitle: "الروابط",
    contactTitle: "تواصل معنا",
    rights: "جميع الحقوق محفوظة.",
  },
};

export default function Footer({ lang = "en" }) {
  const t = footerText[lang] || footerText.en;
  const items = (navItems[lang] || navItems.en).filter((item) => item.id !== "about");

  return (
    <footer className="site-footer">
      <div className="footer-content">
        <div className="footer-brand">
      <div className="footer-logo-row">
        <img className="footer-logo" src={logo} alt="Madar logo" />
        <h3>{t.brand}</h3>
      </div>

        <p>{t.description}</p>
      </div>

        <div className="footer-links">
          <h4>{t.linksTitle}</h4>

          <div className="footer-links-grid">
            {items.map((item) => (
              <NavLink
                key={item.id}
                to={item.path}
                end={item.path === "/"}
                className={({ isActive }) => (isActive ? "active" : "")}
              >
                {item.id === "features"
                  ? lang === "ar"
                    ? "جولة المنتج"
                    : "Product Tour"
                  : item.label}
              </NavLink>
            ))}
          </div>
        </div>

        <div className="footer-contact">
          <h4>{t.contactTitle}</h4>
          <p>info@madar.com</p>
          <p dir="ltr" className="phone-number">
            +972 0599203857
          </p>
        </div>
      </div>

      <div className="footer-bottom">
        <p>
          © 2026 {t.brand}. {t.rights}
        </p>
      </div>
    </footer>
  );
}

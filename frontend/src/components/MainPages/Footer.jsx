import { NavLink } from "react-router-dom";
import logo from "../../assets/MadarTemplates/madar_header.svg";

const navItems = {
  en: [
    { id: "home", label: "Home", path: "/" },
    { id: "features", label: "Product Tour", path: "/features" },
    { id: "pricing", label: "Plans and Pricing", path: "/pricing" },
    { id: "contact", label: "Contact Us", path: "/contact" },
  ],
  ar: [
    { id: "home", label: "الرئيسية", path: "/" },
    { id: "features", label: "جولة المنتج", path: "/features" },
    { id: "pricing", label: "الخطط والأسعار", path: "/pricing" },
    { id: "contact", label: "تواصل معنا", path: "/contact" },
  ],
};

const footerText = {
  en: {
    brand: "Madar",
    description:
      "An adaptive business management platform for creating, managing, and scaling digital systems.",
    linksTitle: "Company",
    contactTitle: "Get in touch",
    emailLabel: "Email",
    phoneLabel: "Phone",
    followLabel: "Follow us",
    rights: "All rights reserved.",
  },
  ar: {
    brand: "مدار",
    description: "منصة إدارة أعمال مرنة لإنشاء وإدارة وتوسيع الأنظمة الرقمية.",
    linksTitle: "الشركة",
    contactTitle: "تواصل معنا",
    emailLabel: "البريد الإلكتروني",
    phoneLabel: "الهاتف",
    followLabel: "تابعنا",
    rights: "جميع الحقوق محفوظة.",
  },
};

export default function Footer({ lang = "en" }) {
  const t = footerText[lang] || footerText.en;
  const items = navItems[lang] || navItems.en;

  return (
    <footer className="site-footer">
      <div className="footer-bg-orb footer-bg-orb-one" />
      <div className="footer-bg-orb footer-bg-orb-two" />

      <div className="footer-shell">
        <div className="footer-main">
          <section className="footer-brand" aria-label="Madar footer brand">
            <NavLink to="/" className="footer-logo-link" aria-label="Madar Home">
              <img className="footer-logo" src={logo} alt="Madar logo" />
              <span>{t.brand}</span>
            </NavLink>

            <p>{t.description}</p>
          </section>

          <nav className="footer-links" aria-label="Footer navigation">
            <h4>{t.linksTitle}</h4>

            <div className="footer-links-grid">
              {items.map((item) => (
                <NavLink
                  key={item.id}
                  to={item.path}
                  end={item.path === "/"}
                  className={({ isActive }) =>
                    isActive ? "footer-link active" : "footer-link"
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          </nav>

          <section className="footer-contact" aria-label="Footer contact">
            <h4>{t.contactTitle}</h4>

            <div className="footer-contact-list">
              <a href="mailto:info@madar.com">
                <span>{t.emailLabel}</span>
                <strong>info@madar.com</strong>
              </a>

              <a href="tel:+972599203857" dir="ltr">
                <span>{t.phoneLabel}</span>
                <strong>+972 599 203 857</strong>
              </a>
            </div>

            <div className="footer-social-row">
              <span>{t.followLabel}</span>

              <a
                className="footer-social-link"
                href="https://www.instagram.com/maadar_ps/"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Madar Instagram"
                title="Instagram"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="18"
                  height="18"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
                  <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
                  <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
                </svg>
              </a>
            </div>
          </section>
        </div>

        <div className="footer-bottom">
          <p>
            © 2026 {t.brand}. {t.rights}
          </p>
        </div>
      </div>
    </footer>
  );
}
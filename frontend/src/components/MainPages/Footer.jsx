import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";

import logo from "../../assets/MadarTemplates/madar_header.svg";

const navItems = [
  { id: "home", labelKey: "nav.home", path: "/" },
  { id: "features", labelKey: "nav.features", path: "/features" },
  { id: "pricing", labelKey: "nav.pricing", path: "/pricing" },
  { id: "contact", labelKey: "nav.contact", path: "/contact" },
];

export default function Footer({ lang = "en" }) {
  const { t } = useTranslation(["common", "public"]);
  const currentLang = lang === "ar" ? "ar" : "en";
  const isAr = currentLang === "ar";
  const brand = t("common:app.brand");

  return (
    <footer
      className={`site-footer ${isAr ? "footer-ar" : "footer-en"}`}
      dir={isAr ? "rtl" : "ltr"}
      lang={currentLang}
    >
      <div className="footer-shell">
        <div className="footer-main">
          <section className="footer-brand" aria-label={t("public:footer.brandAria")}>
            <NavLink to="/" className="footer-logo-link" aria-label={t("public:footer.homeAria")}>
              <img className="footer-logo" src={logo} alt={t("common:app.logoAlt")} />
              <span>{brand}</span>
            </NavLink>

            <p>{t("public:footer.description")}</p>
          </section>

          <nav className="footer-links" aria-label={t("public:footer.navigation")}>
            <h4>{t("public:footer.linksTitle")}</h4>

            <div className="footer-links-grid">
              {navItems.map((item) => (
                <NavLink
                  key={item.id}
                  to={item.path}
                  end={item.path === "/"}
                  className={({ isActive }) =>
                    isActive ? "footer-link active" : "footer-link"
                  }
                >
                  {t(`public:${item.labelKey}`)}
                </NavLink>
              ))}
            </div>
          </nav>

          <section className="footer-contact" aria-label={t("public:footer.contactAria")}>
            <h4>{t("public:footer.contactTitle")}</h4>

            <div className="footer-contact-list">
              <a href="mailto:info@madar.com" className="footer-contact-item">
                <span>{t("public:footer.emailLabel")}</span>
                <strong dir="ltr">info@madar.com</strong>
              </a>

              <a href="tel:+972599203857" className="footer-contact-item">
                <span>{t("public:footer.phoneLabel")}</span>
                <strong dir="ltr">+972 599 203 857</strong>
              </a>
            </div>

            <div className="footer-social-row">
              <a
                className="footer-social-link"
                href="https://www.instagram.com/maadar_ps/"
                target="_blank"
                rel="noopener noreferrer"
                aria-label={t("public:footer.instagramAria")}
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

              <span>{t("public:footer.followLabel")}</span>
            </div>
          </section>
        </div>

        <div className="footer-bottom">
          <p>
            {t("public:footer.copyright", {
              brand,
              rights: t("public:footer.rights"),
            })}
          </p>
        </div>
      </div>
    </footer>
  );
}

import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";

import logo from "../../assets/MadarTemplates/madar_header.svg";
import {
  footerNavigationItems,
  getFooterContent,
  getNavigationContent,
} from "../../content";

const publicFooterNavItems = [
  ...footerNavigationItems,
  { id: "privacy", labelKey: "privacy", path: "/privacy-policy" },
  { id: "terms", labelKey: "terms", path: "/terms-and-conditions" },
];

export default function Footer({ lang = "en" }) {
  const { t } = useTranslation(["common", "public"]);
  const currentLang = lang === "ar" ? "ar" : "en";
  const isAr = currentLang === "ar";
  const brand = t("common:app.brand");
  const content = getFooterContent(currentLang);
  const navigation = getNavigationContent(currentLang);

  return (
    <footer
      className={`site-footer ${isAr ? "footer-ar" : "footer-en"}`}
      dir={isAr ? "rtl" : "ltr"}
      lang={currentLang}
    >
      <div className="footer-shell">
        <div className="footer-main">
          <section className="footer-brand" aria-label={content.brandAria}>
            <NavLink to="/" className="footer-logo-link" aria-label={content.homeAria}>
              <img
                className="footer-logo"
                src={logo}
                alt={t("common:app.logoAlt")}
                width="813"
                height="828"
                loading="lazy"
                decoding="async"
              />
              <span>{brand}</span>
            </NavLink>

            <p>{content.description}</p>
          </section>

          <nav className="footer-links" aria-label={content.navigation}>
            <h4>{content.linksTitle}</h4>

            <div className="footer-links-grid">
              {publicFooterNavItems.map((item) => (
                <NavLink
                  key={item.id}
                  to={item.path}
                  end={item.path === "/"}
                  className={({ isActive }) =>
                    isActive ? "footer-link active" : "footer-link"
                  }
                >
                  {navigation[item.labelKey]}
                </NavLink>
              ))}
            </div>
          </nav>

          <section className="footer-contact" aria-label={content.contactAria}>
            <h4>{content.contactTitle}</h4>

            <div className="footer-contact-list">
              <a href={content.emailHref} className="footer-contact-item">
                <span>{content.emailLabel}</span>
                <strong dir="ltr">{content.email}</strong>
              </a>

              <a href={content.phoneHref} className="footer-contact-item">
                <span>{content.phoneLabel}</span>
                <strong dir="ltr">{content.phone}</strong>
              </a>
            </div>

            <div className="footer-social-row">
              <a
                className="footer-social-link"
                href={content.instagramHref}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={content.instagramAria}
                title={content.instagramTitle}
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

              <span>{content.followLabel}</span>
            </div>
          </section>
        </div>

        <div className="footer-bottom">
          <p>
            {content.copyright
              .replace("{{brand}}", brand)
              .replace("{{rights}}", content.rights)}
          </p>
        </div>
      </div>
    </footer>
  );
}

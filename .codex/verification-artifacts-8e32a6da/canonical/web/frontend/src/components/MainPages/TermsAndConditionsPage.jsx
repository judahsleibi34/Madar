import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

export default function TermsAndConditionsPage({ lang = "en" }) {
  const { t } = useTranslation("public");
  const currentLang = lang === "ar" ? "ar" : "en";
  const page = t("terms", { returnObjects: true });

  return (
    <section
      id="terms"
      className="privacy-policy-page terms-and-conditions-page"
      dir={currentLang === "ar" ? "rtl" : "ltr"}
      lang={currentLang}
    >
      <header className="privacy-policy-hero app-page-section-heading app-major-section">
        <p>{page.updated}</p>
        <h2>{page.title}</h2>
        <span>{page.intro}</span>
      </header>

      <div className="privacy-policy-content">
        {page.sections.map((section) => (
          <section className="privacy-policy-section" key={section.title}>
            <h3>{section.title}</h3>
            <p>{section.body}</p>
          </section>
        ))}

        <p className="privacy-policy-related-link">
          {page.privacyPrefix}{" "}
          <Link to="/privacy-policy">{page.privacyLink}</Link>.
        </p>
      </div>
    </section>
  );
}

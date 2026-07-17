import { useTranslation } from "react-i18next";

export default function PrivacyPolicyPage({ lang = "en" }) {
  const { t } = useTranslation("public");
  const currentLang = lang === "ar" ? "ar" : "en";
  const page = t("privacy", { returnObjects: true });

  return (
    <main
      id="privacy"
      className="privacy-policy-page"
      dir={currentLang === "ar" ? "rtl" : "ltr"}
      lang={currentLang}
    >
      <header className="privacy-policy-hero">
        <p>{page.updated}</p>
        <h1>{page.title}</h1>
        <span>{page.intro}</span>
      </header>

      <div className="privacy-policy-content">
        {page.sections.map((section) => (
          <section className="privacy-policy-section" key={section.title}>
            <h2>{section.title}</h2>
            <p>{section.body}</p>
          </section>
        ))}
      </div>
    </main>
  );
}

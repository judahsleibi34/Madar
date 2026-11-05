import { ArrowRight, Globe2, GraduationCap, Layers, ShoppingBag } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import FadeIn from "../Animations/FadeIn";
import { SectionBlock } from "../../blocks";

const aboutIcons = [Globe2, ShoppingBag, GraduationCap];

export default function AboutSection({ lang }) {
  const { t } = useTranslation("public");
  const content = t("about", { returnObjects: true, lng: lang === "ar" ? "ar" : "en" });
  const isRTL = lang === "ar";

  return (
    <SectionBlock id="about" className="about-section about-page" dir={isRTL ? "rtl" : "ltr"}>
      <FadeIn delay={0}>
        <div className="about-page-hero">
          <div className="about-page-hero-copy">
            <h1>
              {content.hero.titlePrefix} <span>{content.hero.titleHighlight}</span>
            </h1>
            <p className="about-page-lead">
              <strong>{content.hero.name}</strong> {content.hero.description}
            </p>
            <div className="about-page-actions">
              <Link className="about-page-primary-action" to="/pricing">
                {content.actions.explorePlans}<ArrowRight size={18} aria-hidden="true" />
              </Link>
              <Link className="about-page-secondary-action" to="/contact">{content.actions.contactUs}</Link>
            </div>
          </div>

          <div className="about-system-card" aria-label={content.panel.ariaLabel}>
            <div className="about-system-card-heading">
              <span className="about-panel-icon"><Layers size={22} aria-hidden="true" /></span>
              <div><strong>{content.panel.title}</strong><p>{content.panel.description}</p></div>
            </div>
            <ul className="about-product-list" aria-label={content.visual.ariaLabel}>
              {content.metrics.map((product, index) => {
                const Icon = aboutIcons[index] || Globe2;
                return <li key={product.value}><Icon size={20} aria-hidden="true" /><div><strong>{product.value}</strong><p>{product.label}</p></div></li>;
              })}
            </ul>
          </div>
        </div>
      </FadeIn>

      <FadeIn delay={0.2}>
        <header className="about-page-story-heading">
          <h2>{content.story.title}</h2>
          <p>{content.hero.secondDescription}</p>
        </header>
      </FadeIn>

      <div className="about-page-grid">
        {content.sections.map((section, index) => {
          const Icon = aboutIcons[index] || Globe2;
          return (
            <FadeIn delay={0.28 + index * 0.07} key={section.title}>
              <article className="about-page-card">
                <div className="about-page-card-top">
                  <Icon size={21} aria-hidden="true" />
                </div>
                <h3>{section.title}</h3>
                <p>{section.body}</p>
              </article>
            </FadeIn>
          );
        })}
      </div>

      <FadeIn delay={0.52}>
        <div className="about-page-closing">
          <div><h2>{content.closingSection.title}</h2><p>{content.closing}</p></div>
          <Link to="/contact">{content.actions.contactUs}<ArrowRight size={18} aria-hidden="true" /></Link>
        </div>
      </FadeIn>
    </SectionBlock>
  );
}

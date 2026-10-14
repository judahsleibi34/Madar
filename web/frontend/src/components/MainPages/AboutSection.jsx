import { ArrowRight, Globe2, GraduationCap, ShieldCheck, ShoppingBag } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import FadeIn from "../Animations/FadeIn";
import { SectionBlock } from "../../blocks";

const aboutIcons = [Globe2, ShoppingBag, GraduationCap];

export default function AboutSection({ lang }) {
  const { t } = useTranslation("public");
  const content = t("about", { returnObjects: true });
  const isRTL = lang === "ar";

  return (
    <SectionBlock id="about" className="about-section about-page" dir={isRTL ? "rtl" : "ltr"}>
      <FadeIn delay={0}>
        <div className="about-page-hero">
          <div className="about-page-hero-copy">
            <h1>
              {content.hero.titlePrefix} <span className="heading-accent">{content.hero.titleHighlight}</span>
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
              <span className="about-panel-icon"><ShieldCheck size={23} /></span>
              <div><strong>{content.panel.title}</strong><p>{content.panel.description}</p></div>
            </div>
            <div className="about-system-map" aria-label={content.visual.ariaLabel}>
              <div className="about-system-node is-forms"><Globe2 size={19} /><span>{content.visual.forms}</span></div>
              <div className="about-system-core"><span>M</span><small>{content.hero.name}</small></div>
              <div className="about-system-node is-records"><GraduationCap size={19} /><span>{content.visual.records}</span></div>
              <div className="about-system-node is-workflows"><ShoppingBag size={19} /><span>{content.visual.workflows}</span></div>
            </div>
          </div>
        </div>
      </FadeIn>

      <div className="about-page-metrics" aria-label={content.metricsAriaLabel}>
        {content.metrics.map((metric, index) => {
          const Icon = aboutIcons[index] || Globe2;

          return (
            <FadeIn delay={0.08 + index * 0.06} key={metric.value}>
              <article className="about-page-metric">
                <span><Icon size={20} /></span>
                <div><strong>{metric.value}</strong><p>{metric.label}</p></div>
              </article>
            </FadeIn>
          );
        })}
      </div>

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
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <Icon size={21} aria-hidden="true" />
                </div>
                <h2>{section.title}</h2>
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

import { Database, FileText, ShieldCheck, Workflow } from "lucide-react";
import { useTranslation } from "react-i18next";
import FadeIn from "../Animations/FadeIn";
import { SectionBlock } from "../../blocks";

const aboutIcons = [FileText, Workflow, Database];

export default function AboutSection({ lang }) {
  const { t } = useTranslation("public");
  const content = t("about", { returnObjects: true });
  const isRTL = lang === "ar";

  return (
    <SectionBlock id="about" className="about-section" dir={isRTL ? "rtl" : "ltr"}>
      <FadeIn delay={0}>
        <div className="about-hero">
          <div className="about-hero-copy">
            <span className="about-eyebrow">{content.hero.eyebrow}</span>
            <h1>
              {content.hero.titlePrefix} <span>{content.hero.titleHighlight}</span>
            </h1>
            <p>
              <strong>{content.hero.name}</strong> {content.hero.description}
            </p>
            <p>{content.hero.secondDescription}</p>
          </div>

          <div className="about-hero-panel" aria-label={content.panel.ariaLabel}>
            <div className="about-panel-icon">
              <ShieldCheck size={26} />
            </div>
            <h2>{content.panel.title}</h2>
            <p>{content.panel.description}</p>
          </div>
        </div>
      </FadeIn>

      <div className="about-metrics" aria-label={content.metricsAriaLabel}>
        {content.metrics.map((metric, index) => {
          const Icon = aboutIcons[index] || FileText;

          return (
            <FadeIn delay={0.12 + index * 0.08} key={metric.value}>
              <article className="about-metric">
                <Icon size={20} />
                <strong>{metric.value}</strong>
                <span>{metric.label}</span>
              </article>
            </FadeIn>
          );
        })}
      </div>

      <div className="about-grid">
        {content.sections.map((section, index) => (
          <FadeIn delay={0.25 + index * 0.08} key={section.title}>
            <article className="about-card">
              <span>{String(index + 1).padStart(2, "0")}</span>
              <h2>{section.title}</h2>
              <p>{section.body}</p>
            </article>
          </FadeIn>
        ))}
      </div>

      <FadeIn delay={0.55}>
        <p className="about-closing">{content.closing}</p>
      </FadeIn>
    </SectionBlock>
  );
}

import { Database, FileText, ShieldCheck, Workflow } from "lucide-react";
import FadeIn from "../Animations/FadeIn";
import { getAboutContent } from "../../content";
import { SectionBlock } from "../../blocks";

const aboutIcons = [FileText, Workflow, Database];

export default function AboutSection({ lang }) {
  const t = getAboutContent(lang);

  return (
    <SectionBlock id="about" className="about-section">
      <FadeIn delay={0}>
        <div className="about-hero">
          <div className="about-hero-copy">
            <span className="about-eyebrow">{t.hero.eyebrow}</span>
            <h1>
              {t.hero.titlePrefix} <span>{t.hero.titleHighlight}</span>
            </h1>
            <p>
              <strong>{t.hero.name}</strong> {t.hero.description}
            </p>
            <p>{t.hero.secondDescription}</p>
          </div>

          <div className="about-hero-panel" aria-label="Madar digitalization focus">
            <div className="about-panel-icon">
              <ShieldCheck size={26} />
            </div>
            <h2>Digital operations, without the clutter</h2>
            <p>
              Replace scattered paperwork with structured pages, forms, records,
              and workflows your team can actually use every day.
            </p>
          </div>
        </div>
      </FadeIn>

      <div className="about-metrics" aria-label="Madar platform strengths">
        {t.metrics.map((metric, index) => {
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
        {t.sections.map((section, index) => (
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
        <p className="about-closing">{t.closing}</p>
      </FadeIn>
    </SectionBlock>
  );
}

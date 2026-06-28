import { PlayCircle } from "lucide-react";
import { Link } from "react-router-dom";
import GradientText from "../Animations/GradientText";
import { getFeaturesContent } from "../../content";
import { CardGridBlock, CTASectionBlock, HeroBlock } from "../../blocks";

export default function FeaturesPage({ lang = "en" }) {
  const t = getFeaturesContent(lang);

  return (
    <main className="features-page">
      <HeroBlock className="features-hero">
        <h1>
          {lang === "en" ? (
            <>
              {t.titleParts[0]}{" "}
              <GradientText pauseOnHover>{t.titleParts[1]}</GradientText>,{" "}
              {t.titleParts[2]}{" "}
              <GradientText pauseOnHover>{t.titleParts[3]}</GradientText>
            </>
          ) : (
            <GradientText pauseOnHover>{t.title}</GradientText>
          )}
        </h1>
        <p>{t.subtitle}</p>
      </HeroBlock>

      <CTASectionBlock className="features-demo-panel" aria-label={t.demoTitle}>
        <div className="features-demo-copy">
          <div className="features-demo-icon">
            <PlayCircle size={26} />
          </div>
          <div>
            <h2>
              <GradientText pauseOnHover>{t.demoTitle}</GradientText>
            </h2>
            <p>{t.demoDescription}</p>
          </div>
        </div>

        <ul className="features-demo-list">
          {t.demoPoints.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>

        <Link className="features-demo-cta" to="/demo">
          {t.demoCta}
        </Link>
      </CTASectionBlock>

      <CardGridBlock
        className="features-grid"
        aria-label={t.eyebrow}
        items={t.features}
        renderItem={(feature) => {
          const Icon = feature.icon;

          return (
            <article className="feature-card" key={feature.title}>
              <div className="feature-card-icon">
                <Icon size={22} />
              </div>
              <h2>
                <GradientText pauseOnHover>{feature.title}</GradientText>
              </h2>
              <p>{feature.description}</p>
            </article>
          );
        }}
      />
    </main>
  );
}

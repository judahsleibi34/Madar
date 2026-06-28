import FadeIn from "../Animations/FadeIn";
import GradientText from "../Animations/GradientText";
import SplitText from "../Animations/SplitText";
import { getAboutContent } from "../../content";
import { HeroBlock, SectionBlock } from "../../blocks";

export default function AboutSection({ lang }) {
  const t = getAboutContent(lang);

  return (
    <SectionBlock id="about" className="about-section">
      <FadeIn delay={0}>
        <h1 className="hero-title">
          {lang === "en" ? (
            <>
              {t.hero.titlePrefix}{" "}
              <GradientText pauseOnHover>{t.hero.titleHighlight}</GradientText>
            </>
          ) : (
            <GradientText pauseOnHover>{t.hero.title}</GradientText>
          )}
        </h1>
      </FadeIn>

      <FadeIn delay={0.15}>
        <p className="hero-description">
          <SplitText className="arabic-name">{t.hero.name}</SplitText>{" "}
          {t.hero.description}
        </p>
      </FadeIn>

      <FadeIn delay={0.25}>
        <p className="hero-description">{t.hero.secondDescription}</p>
      </FadeIn>

      {t.sections.map((section, index) => (
        <FadeIn delay={0.35 + index * 0.1} key={section.title}>
          <HeroBlock as="div">
            <h2 className="hero-subtitle">
              <GradientText pauseOnHover>{section.title}</GradientText>
            </h2>
            <p className="hero-description">{section.body}</p>
          </HeroBlock>
        </FadeIn>
      ))}
    </SectionBlock>
  );
}

import {
  ClipboardList,
  Database,
  LayoutTemplate,
  PlayCircle,
  ShieldCheck,
  UsersRound,
  Workflow,
} from "lucide-react";
import { Link } from "react-router-dom";
import GradientText from "./GradientText";

const featureText = {
  en: {
    eyebrow: "Platform features",
    title: "Tour the builder, then try it live",
    subtitle:
      "Open the demo to edit the default template in the browser. Refreshing the demo restores the original showcase, so every visitor starts clean.",
    demoTitle: "Try the interactive builder demo",
    demoDescription:
      "Explore the same default template we use to show pages, forms, data, workflows, users, roles, theme controls, and preview behavior.",
    demoCta: "Try the demo",
    demoPoints: [
      "Edit page content, layout, sections, and visual elements",
      "Preview the responsive page template",
      "Try forms, data, responses, workflows, users, and theme controls",
      "Refresh anytime to reload the original default template",
    ],
    features: [
      {
        icon: LayoutTemplate,
        title: "Page builder",
        description:
          "Create public pages, internal screens, dashboards, and service flows without starting from code.",
      },
      {
        icon: ClipboardList,
        title: "Smart forms",
        description:
          "Collect requests, approvals, reservations, and customer information with forms that connect to your workspace.",
      },
      {
        icon: Database,
        title: "Data records",
        description:
          "Organize submitted information into collections that teams can review, search, and manage.",
      },
      {
        icon: Workflow,
        title: "Workflows",
        description:
          "Prototype approval steps, assignments, and operating processes around the way your team already works.",
      },
      {
        icon: UsersRound,
        title: "Users and roles",
        description:
          "Prepare role-based access so the right people see the right pages, forms, and actions.",
      },
      {
        icon: ShieldCheck,
        title: "Ready to grow",
        description:
          "Start with a front-end system prototype and keep the structure ready for deeper backend integration.",
      },
    ],
  },
  ar: {
    eyebrow: "\u0645\u0645\u064a\u0632\u0627\u062a \u0627\u0644\u0645\u0646\u0635\u0629",
    title: "\u062a\u0639\u0631\u0641 \u0639\u0644\u0649 \u0627\u0644\u0645\u0646\u0634\u0626 \u062b\u0645 \u062c\u0631\u0628\u0647 \u0645\u0628\u0627\u0634\u0631\u0629",
    subtitle:
      "\u0627\u0641\u062a\u062d \u0627\u0644\u062a\u062c\u0631\u0628\u0629 \u0644\u062a\u0639\u062f\u064a\u0644 \u0627\u0644\u0642\u0627\u0644\u0628 \u0627\u0644\u0627\u0641\u062a\u0631\u0627\u0636\u064a \u0645\u0646 \u0627\u0644\u0645\u062a\u0635\u0641\u062d. \u0639\u0646\u062f \u062a\u062d\u062f\u064a\u062b \u0627\u0644\u0635\u0641\u062d\u0629 \u064a\u0639\u0648\u062f \u0627\u0644\u0642\u0627\u0644\u0628 \u0627\u0644\u0623\u0635\u0644\u064a.",
    demoTitle: "\u062c\u0631\u0628 \u0645\u0646\u0634\u0626 \u0627\u0644\u0635\u0641\u062d\u0627\u062a",
    demoDescription:
      "\u0627\u0633\u062a\u0643\u0634\u0641 \u0642\u0627\u0644\u0628\u0627 \u064a\u0639\u0631\u0636 \u0627\u0644\u0635\u0641\u062d\u0627\u062a \u0648\u0627\u0644\u0646\u0645\u0627\u0630\u062c \u0648\u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a \u0648\u0633\u064a\u0631 \u0627\u0644\u0639\u0645\u0644 \u0648\u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645\u064a\u0646 \u0648\u0627\u0644\u0623\u062f\u0648\u0627\u0631 \u0648\u0627\u0644\u0645\u0639\u0627\u064a\u0646\u0629.",
    demoCta: "\u062c\u0631\u0651\u0628 \u0627\u0644\u062f\u064a\u0645\u0648",
    demoPoints: [
      "\u062a\u0639\u062f\u064a\u0644 \u0627\u0644\u0645\u062d\u062a\u0648\u0649 \u0648\u0627\u0644\u062a\u062e\u0637\u064a\u0637 \u0648\u0627\u0644\u0639\u0646\u0627\u0635\u0631",
      "\u0645\u0639\u0627\u064a\u0646\u0629 \u0627\u0644\u0642\u0627\u0644\u0628 \u0628\u0623\u062d\u062c\u0627\u0645 \u0645\u062e\u062a\u0644\u0641\u0629",
      "\u062a\u062c\u0631\u0628\u0629 \u0627\u0644\u0646\u0645\u0627\u0630\u062c \u0648\u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a \u0648\u0633\u064a\u0631 \u0627\u0644\u0639\u0645\u0644 \u0648\u0627\u0644\u062b\u064a\u0645",
      "\u062a\u062d\u062f\u064a\u062b \u0627\u0644\u0635\u0641\u062d\u0629 \u064a\u0639\u064a\u062f \u0627\u0644\u0642\u0627\u0644\u0628 \u0627\u0644\u0627\u0641\u062a\u0631\u0627\u0636\u064a",
    ],
    features: [
      {
        icon: LayoutTemplate,
        title: "\u0645\u0646\u0634\u0626 \u0627\u0644\u0635\u0641\u062d\u0627\u062a",
        description:
          "\u0623\u0646\u0634\u0626 \u0635\u0641\u062d\u0627\u062a \u0639\u0627\u0645\u0629 \u0648\u0634\u0627\u0634\u0627\u062a \u062f\u0627\u062e\u0644\u064a\u0629 \u0648\u0644\u0648\u062d\u0627\u062a \u0645\u062a\u0627\u0628\u0639\u0629 \u0648\u062a\u062f\u0641\u0642\u0627\u062a \u062e\u062f\u0645\u064a\u0629 \u0628\u062f\u0648\u0646 \u0627\u0644\u0628\u062f\u0621 \u0645\u0646 \u0627\u0644\u0643\u0648\u062f.",
      },
      {
        icon: ClipboardList,
        title: "\u0646\u0645\u0627\u0630\u062c \u0630\u0643\u064a\u0629",
        description:
          "\u0627\u062c\u0645\u0639 \u0627\u0644\u0637\u0644\u0628\u0627\u062a \u0648\u0627\u0644\u0645\u0648\u0627\u0641\u0642\u0627\u062a \u0648\u0627\u0644\u062d\u062c\u0648\u0632\u0627\u062a \u0648\u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u0639\u0645\u0644\u0627\u0621 \u0645\u0646 \u062e\u0644\u0627\u0644 \u0646\u0645\u0627\u0630\u062c \u0645\u0631\u062a\u0628\u0637\u0629 \u0628\u0645\u0633\u0627\u062d\u0629 \u0639\u0645\u0644\u0643.",
      },
      {
        icon: Database,
        title: "\u0633\u062c\u0644\u0627\u062a \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a",
        description:
          "\u0646\u0638\u0645 \u0627\u0644\u0645\u0639\u0644\u0648\u0645\u0627\u062a \u0627\u0644\u0645\u0631\u0633\u0644\u0629 \u0641\u064a \u0645\u062c\u0645\u0648\u0639\u0627\u062a \u064a\u0645\u0643\u0646 \u0644\u0644\u0641\u0631\u064a\u0642 \u0645\u0631\u0627\u062c\u0639\u062a\u0647\u0627 \u0648\u0627\u0644\u0628\u062d\u062b \u0641\u064a\u0647\u0627 \u0648\u0625\u062f\u0627\u0631\u062a\u0647\u0627.",
      },
      {
        icon: Workflow,
        title: "\u0633\u064a\u0631 \u0627\u0644\u0639\u0645\u0644",
        description:
          "\u062c\u0631\u0628 \u062e\u0637\u0648\u0627\u062a \u0627\u0644\u0645\u0648\u0627\u0641\u0642\u0629 \u0648\u0627\u0644\u062a\u0643\u0644\u064a\u0641 \u0648\u0627\u0644\u0639\u0645\u0644\u064a\u0627\u062a \u062d\u0633\u0628 \u0627\u0644\u0637\u0631\u064a\u0642\u0629 \u0627\u0644\u062a\u064a \u064a\u0639\u0645\u0644 \u0628\u0647\u0627 \u0641\u0631\u064a\u0642\u0643.",
      },
      {
        icon: UsersRound,
        title: "\u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645\u0648\u0646 \u0648\u0627\u0644\u0623\u062f\u0648\u0627\u0631",
        description:
          "\u062c\u0647\u0632 \u0635\u0644\u0627\u062d\u064a\u0627\u062a \u0645\u0628\u0646\u064a\u0629 \u0639\u0644\u0649 \u0627\u0644\u0623\u062f\u0648\u0627\u0631 \u0644\u064a\u0631\u0649 \u0643\u0644 \u0634\u062e\u0635 \u0627\u0644\u0635\u0641\u062d\u0627\u062a \u0648\u0627\u0644\u0646\u0645\u0627\u0630\u062c \u0648\u0627\u0644\u0625\u062c\u0631\u0627\u0621\u0627\u062a \u0627\u0644\u0645\u0646\u0627\u0633\u0628\u0629.",
      },
      {
        icon: ShieldCheck,
        title: "\u062c\u0627\u0647\u0632 \u0644\u0644\u0646\u0645\u0648",
        description:
          "\u0627\u0628\u062f\u0623 \u0628\u0646\u0645\u0648\u0630\u062c \u0646\u0638\u0627\u0645 \u0623\u0645\u0627\u0645\u064a \u0648\u0627\u062d\u0641\u0638 \u0627\u0644\u0628\u0646\u064a\u0629 \u062c\u0627\u0647\u0632\u0629 \u0644\u062a\u0643\u0627\u0645\u0644 \u062e\u0644\u0641\u064a \u0623\u0639\u0645\u0642.",
      },
    ],
  },
};

export default function FeaturesPage({ lang = "en" }) {
  const t = featureText[lang] || featureText.en;

  return (
    <main className="features-page">
      <section className="features-hero">
        <h1>
          {lang === "en" ? (
            <>
              Tour the <GradientText pauseOnHover>builder</GradientText>, then try it <GradientText pauseOnHover>live</GradientText>
            </>
          ) : (
            <GradientText pauseOnHover>{t.title}</GradientText>
          )}
        </h1>
        <p>{t.subtitle}</p>
      </section>

      <section className="features-demo-panel" aria-label={t.demoTitle}>
        <div className="features-demo-copy">
          <div className="features-demo-icon">
            <PlayCircle size={26} />
          </div>
          <div>
            <h2><GradientText pauseOnHover>{t.demoTitle}</GradientText></h2>
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
      </section>

      <section className="features-grid" aria-label={t.eyebrow}>
        {t.features.map((feature) => {
          const Icon = feature.icon;

          return (
            <article className="feature-card" key={feature.title}>
              <div className="feature-card-icon">
                <Icon size={22} />
              </div>
              <h2><GradientText pauseOnHover>{feature.title}</GradientText></h2>
              <p>{feature.description}</p>
            </article>
          );
        })}
      </section>
    </main>
  );
}

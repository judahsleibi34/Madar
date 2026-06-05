import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  CreditCard,
  Database,
  Grid2X2,
  ClipboardList,
  Settings,
} from "lucide-react";

export default function UserDashboard({ user }) {
  const { t } = useTranslation(["dashboard"]);
  const navigate = useNavigate();

  const displayName =
    user?.first_name || user?.name || user?.email || t("user.fallbackName");

  const cards = [
    {
      title: t("userDashboard.cards.builder.title", {
        defaultValue: "Page Builder",
      }),
      description: t("userDashboard.cards.builder.description", {
        defaultValue: "Build and edit your public website.",
      }),
      icon: Grid2X2,
      path: "/page-builder",
    },
    {
      title: t("userDashboard.cards.submissions.title", {
        defaultValue: "Submissions",
      }),
      description: t("userDashboard.cards.submissions.description", {
        defaultValue: "Review messages and form responses.",
      }),
      icon: ClipboardList,
      path: "/builder-responses",
    },
    {
      title: t("userDashboard.cards.data.title", {
        defaultValue: "Data Logs",
      }),
      description: t("userDashboard.cards.data.description", {
        defaultValue: "View your collected website data.",
      }),
      icon: Database,
      path: "/builder-data",
    },
    {
      title: t("userDashboard.cards.plan.title", {
        defaultValue: "My Plan",
      }),
      description: t("userDashboard.cards.plan.description", {
        defaultValue: "Manage your subscription and billing status.",
      }),
      icon: CreditCard,
      path: "/my-plan",
    },
  ];

  return (
    <section className="user-dashboard-page">
      <div className="user-dashboard-hero">
        <p className="user-dashboard-eyebrow">
          {t("userDashboard.eyebrow", {
            defaultValue: "Workspace",
          })}
        </p>

        <h1>
          {t("userDashboard.title", {
            name: displayName,
            defaultValue: `Welcome, ${displayName}`,
          })}
        </h1>

        <p>
          {t("userDashboard.subtitle", {
            defaultValue:
              "Manage your website, submissions, data, plan, and account settings from one place.",
          })}
        </p>
      </div>

      <div className="user-dashboard-grid">
        {cards.map((card) => {
          const Icon = card.icon;

          return (
            <button
              type="button"
              className="user-dashboard-card"
              key={card.path}
              onClick={() => navigate(card.path)}
            >
              <span className="user-dashboard-card-icon" aria-hidden="true">
                <Icon size={22} />
              </span>

              <strong>{card.title}</strong>
              <span>{card.description}</span>
            </button>
          );
        })}
      </div>

      <div className="user-dashboard-panel">
        <div>
          <h2>
            {t("userDashboard.quickSettings.title", {
              defaultValue: "Account settings",
            })}
          </h2>

          <p>
            {t("userDashboard.quickSettings.description", {
              defaultValue: "Update your profile, password, and preferences.",
            })}
          </p>
        </div>

        <button type="button" onClick={() => navigate("/settings")}>
          <Settings size={18} />
          {t("userDashboard.quickSettings.action", {
            defaultValue: "Open settings",
          })}
        </button>
      </div>
    </section>
  );
}
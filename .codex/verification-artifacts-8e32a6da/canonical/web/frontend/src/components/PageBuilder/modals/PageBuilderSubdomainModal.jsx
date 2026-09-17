import { useMemo, useState } from "react";
import { getSubdomainModalContent } from "../../../content";
import { sanitizeSubdomain } from "../core/PageBuilder.routing";

const RESERVED_WEBSITE_NAMES = new Set([
  "admin",
  "api",
  "app",
  "auth",
  "billing",
  "dashboard",
  "login",
  "logout",
  "madar",
  "root",
  "settings",
  "signup",
  "support",
  "www",
]);

const getSuggestedWebsiteName = (project, defaultWebsiteName) => {
  const saved = project?.publish?.subdomain || "";
  const brand = project?.siteChrome?.brand || "";
  const projectName = project?.name || "";
  const source = saved || brand || projectName || defaultWebsiteName;

  return sanitizeSubdomain(source) || defaultWebsiteName;
};

const getDomain = (project, defaultDomain) => {
  const savedDomain = String(project?.publish?.siteBaseDomain || "").trim();
  return !savedDomain || savedDomain === "madar.app"
    ? defaultDomain
    : savedDomain;
};

export default function PageBuilderSubdomainModal({
  project,
  lang = "en",
  onSave,
  onSkip,
}) {
  void onSkip;

  const content = getSubdomainModalContent(lang);
  const [websiteName, setWebsiteName] = useState(
    getSuggestedWebsiteName(project, content.defaultWebsiteName)
  );
  const [error, setError] = useState("");

  const domain = getDomain(project, content.defaultDomain);

  const cleanWebsiteName = useMemo(
    () => sanitizeSubdomain(websiteName),
    [websiteName]
  );

  const websiteLink = `${domain}/site/${cleanWebsiteName || content.defaultWebsiteName}`;

  const handleWebsiteNameChange = (event) => {
    setWebsiteName(sanitizeSubdomain(event.target.value));
    setError("");
  };

  const handleSave = () => {
    if (!cleanWebsiteName) {
      setError(content.errors.required);
      return;
    }

    if (cleanWebsiteName.length < 3) {
      setError(content.errors.minLength);
      return;
    }

    if (RESERVED_WEBSITE_NAMES.has(cleanWebsiteName)) {
      setError(content.errors.reserved);
      return;
    }

    onSave({
      subdomain: cleanWebsiteName,
      siteBaseDomain: domain,
    });
  };

  return (
    <>
      <style>
        {`
          .madar-website-name-overlay {
            position: fixed;
            inset: 0;
            z-index: 9999;
            display: grid;
            place-items: center;
            padding: 24px;
            background: rgba(var(--theme-shadow-rgb), 0.62);
            backdrop-filter: blur(8px);
          }

          .madar-website-name-modal {
            width: min(520px, 100%);
            background: var(--color-card, var(--theme-surface));
            border-radius: var(--radius-xl, 28px);
            padding: 28px;
            box-shadow: var(--shadow-lg, 0 32px 90px rgba(var(--theme-shadow-rgb), 0.28));
            color: var(--color-text-main, var(--theme-text));
          }

          .madar-website-name-top {
            display: flex;
            gap: 16px;
            align-items: flex-start;
            margin-bottom: 22px;
          }

          .madar-website-name-logo {
            width: 56px;
            height: 56px;
            flex: 0 0 56px;
            border-radius: var(--radius-lg, 18px);
            display: grid;
            place-items: center;
            background: var(--theme-gradient);
            color: var(--color-on-theme, var(--theme-text-inverse));
            font-size: 22px;
            font-weight: 950;
            box-shadow: 0 12px 28px rgba(var(--theme-primary-rgb), 0.22);
          }

          .madar-website-name-kicker {
            display: inline-flex;
            margin-bottom: 8px;
            padding: 6px 10px;
            border-radius: var(--radius-full, 999px);
            background: rgba(var(--theme-primary-rgb), 0.1);
            color: var(--theme-primary);
            font-size: 12px;
            font-weight: 950;
            letter-spacing: 0.04em;
            text-transform: uppercase;
          }

          .madar-website-name-modal h2 {
            margin: 0;
            font-size: 32px;
            line-height: 1.05;
            font-weight: 950;
            letter-spacing: -0.04em;
            color: var(--color-text-main, var(--theme-text));
          }

          .madar-website-name-modal p {
            margin: 10px 0 0;
            color: var(--color-text-muted, var(--theme-text-soft));
            font-size: 15px;
            line-height: 1.5;
          }

          .madar-website-name-form {
            display: grid;
            gap: 14px;
          }

          .madar-website-name-label {
            display: grid;
            gap: 8px;
            color: var(--color-text-main, var(--theme-text));
            font-size: 14px;
            font-weight: 950;
          }

          .madar-website-name-input-row {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            align-items: center;
            min-height: 58px;
            border: 1px solid rgba(var(--theme-shadow-rgb), 0.22);
            border-radius: var(--radius-lg, 18px);
            background: var(--color-card, var(--theme-surface));
            overflow: hidden;
            box-shadow: 0 10px 24px rgba(var(--theme-shadow-rgb), 0.05);
          }

          .madar-website-name-input-row:focus-within {
            border-color: var(--theme-primary);
            box-shadow: 0 0 0 4px rgba(var(--theme-primary-rgb), 0.1);
          }

          .madar-website-name-input-row input {
            width: 100%;
            min-height: 58px;
            border: 0 !important;
            outline: 0 !important;
            box-shadow: none !important;
            padding: 0 16px !important;
            color: var(--color-text-main, var(--theme-text));
            font-size: 18px;
            font-weight: 950;
            background: transparent !important;
          }

          .madar-website-name-input-row span {
            padding: 0 16px;
            color: var(--color-text-muted, var(--theme-text-soft));
            font-size: 16px;
            font-weight: 900;
            white-space: nowrap;
          }

          .madar-website-name-error {
            margin: 0;
            padding: 10px 12px;
            border-radius: var(--radius-md, 14px);
            background: rgba(var(--theme-primary-rgb), 0.09);
            color: var(--theme-primary);
            font-size: 13px;
            font-weight: 900;
          }

          .madar-website-name-preview {
            display: grid;
            gap: 6px;
            padding: 16px;
            border-radius: var(--radius-lg, 18px);
            background: var(--color-background-soft, var(--theme-bg-soft));
            border: 1px solid rgba(var(--theme-shadow-rgb), 0.12);
          }

          .madar-website-name-preview span {
            color: var(--color-text-muted, var(--theme-text-soft));
            font-size: 12px;
            font-weight: 950;
            text-transform: uppercase;
            letter-spacing: 0.05em;
          }

          .madar-website-name-preview strong {
            color: var(--color-text-main, var(--theme-text));
            font-size: 22px;
            font-weight: 950;
            letter-spacing: -0.03em;
            word-break: break-word;
          }

          .madar-website-name-note {
            margin: 0 !important;
            color: var(--color-text-muted, var(--theme-text-soft)) !important;
            font-size: 14px !important;
            line-height: 1.5 !important;
          }

          .madar-website-name-actions {
            display: flex;
            justify-content: center;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 4px;
          }

          .madar-website-name-actions button {
            min-height: 46px;
            border: 0;
            border-radius: var(--radius-md, 14px);
            padding: 0 16px;
            font-weight: 950;
            cursor: pointer;
          }

          .madar-website-name-secondary {
            background: rgba(var(--theme-shadow-rgb), 0.08);
            color: var(--color-text-main, var(--theme-text));
          }

          .madar-website-name-primary {
            background: var(--theme-gradient);
            color: var(--color-on-theme, var(--theme-text-inverse));
            box-shadow: 0 12px 28px rgba(var(--theme-primary-rgb), 0.22);
          }

          @media (max-width: 640px) {
            .madar-website-name-modal {
              padding: 22px;
              border-radius: var(--radius-xl, 24px);
            }

            .madar-website-name-top {
              display: grid;
            }

            .madar-website-name-input-row {
              grid-template-columns: 1fr;
            }

            .madar-website-name-input-row span {
              padding: 0 16px 14px;
            }

            .madar-website-name-actions {
              display: grid;
              grid-template-columns: 1fr;
            }

            .madar-website-name-actions button {
              width: 100%;
            }
          }
        `}
      </style>

      <div className="madar-website-name-overlay">
        <section
          className="madar-website-name-modal"
          aria-labelledby="website-name-title"
        >
          <div className="madar-website-name-top">
            <div className="madar-website-name-logo">
              {(project?.siteChrome?.brand || project?.name || content.logoFallback).slice(0, 1)}
            </div>

            <div>

              <h2 id="website-name-title">{content.title}</h2>

              <p>{content.description}</p>
            </div>
          </div>

          <div className="madar-website-name-form">
            <label className="madar-website-name-label">
              {content.websiteNameLabel}

              <div className="madar-website-name-input-row">
                <input
                  value={websiteName}
                  placeholder={content.websiteNamePlaceholder}
                  autoFocus
                  onChange={handleWebsiteNameChange}
                />

                <span>.{domain}</span>
              </div>
            </label>

            {error && <p className="madar-website-name-error">{error}</p>}

            <div className="madar-website-name-preview">
              <span>{content.previewLabel}</span>
              <strong>{websiteLink}</strong>
            </div>

            <p className="madar-website-name-note">
              {content.note}
            </p>

            <div className="madar-website-name-actions">
            <button
              type="button"
              className="madar-website-name-primary"
              onClick={handleSave}
            >
              {content.action}
            </button>
          </div>
          </div>
        </section>
      </div>
    </>
  );
}

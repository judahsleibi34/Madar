import { useMemo, useState } from "react";
import { sanitizeSubdomain } from "./PageBuilder.routing";

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

const getSuggestedWebsiteName = (project) => {
  const saved = project?.publish?.subdomain || "";
  const brand = project?.siteChrome?.brand || "";
  const projectName = project?.name || "";
  const source = saved || brand || projectName || "my-website";

  return sanitizeSubdomain(source) || "my-website";
};

const getDomain = (project) => {
  return project?.publish?.siteBaseDomain || "madar.app";
};

export default function PageBuilderSubdomainModal({
  project,
  onSave,
  onSkip,
}) {
  const [websiteName, setWebsiteName] = useState(
    getSuggestedWebsiteName(project)
  );
  const [error, setError] = useState("");

  const domain = getDomain(project);

  const cleanWebsiteName = useMemo(
    () => sanitizeSubdomain(websiteName),
    [websiteName]
  );

  const websiteLink = `${cleanWebsiteName || "my-website"}.${domain}`;

  const handleWebsiteNameChange = (event) => {
    setWebsiteName(sanitizeSubdomain(event.target.value));
    setError("");
  };

  const handleSave = () => {
    if (!cleanWebsiteName) {
      setError("Add a website name first.");
      return;
    }

    if (cleanWebsiteName.length < 3) {
      setError("Use at least 3 characters.");
      return;
    }

    if (RESERVED_WEBSITE_NAMES.has(cleanWebsiteName)) {
      setError("This name is reserved. Try another one.");
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
            background: rgba(15, 23, 42, 0.62);
            backdrop-filter: blur(8px);
          }

          .madar-website-name-modal {
            width: min(520px, 100%);
            background: #ffffff;
            border-radius: 28px;
            padding: 28px;
            box-shadow: 0 32px 90px rgba(15, 23, 42, 0.28);
            color: #1a2744;
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
            border-radius: 18px;
            display: grid;
            place-items: center;
            background: var(--theme-gradient);
            color: #ffffff;
            font-size: 22px;
            font-weight: 950;
            box-shadow: 0 12px 28px rgba(var(--theme-primary-rgb), 0.22);
          }

          .madar-website-name-kicker {
            display: inline-flex;
            margin-bottom: 8px;
            padding: 6px 10px;
            border-radius: 999px;
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
            color: #1a2744;
          }

          .madar-website-name-modal p {
            margin: 10px 0 0;
            color: #6d7484;
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
            color: #1a2744;
            font-size: 14px;
            font-weight: 950;
          }

          .madar-website-name-input-row {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            align-items: center;
            min-height: 58px;
            border: 1px solid rgba(26, 39, 68, 0.22);
            border-radius: 18px;
            background: #ffffff;
            overflow: hidden;
            box-shadow: 0 10px 24px rgba(26, 39, 68, 0.05);
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
            color: #1a2744;
            font-size: 18px;
            font-weight: 950;
            background: transparent !important;
          }

          .madar-website-name-input-row span {
            padding: 0 16px;
            color: #6d7484;
            font-size: 16px;
            font-weight: 900;
            white-space: nowrap;
          }

          .madar-website-name-error {
            margin: 0;
            padding: 10px 12px;
            border-radius: 14px;
            background: rgba(var(--theme-primary-rgb), 0.09);
            color: var(--theme-primary);
            font-size: 13px;
            font-weight: 900;
          }

          .madar-website-name-preview {
            display: grid;
            gap: 6px;
            padding: 16px;
            border-radius: 18px;
            background: #fbfaf8;
            border: 1px solid rgba(26, 39, 68, 0.12);
          }

          .madar-website-name-preview span {
            color: #6d7484;
            font-size: 12px;
            font-weight: 950;
            text-transform: uppercase;
            letter-spacing: 0.05em;
          }

          .madar-website-name-preview strong {
            color: #1a2744;
            font-size: 22px;
            font-weight: 950;
            letter-spacing: -0.03em;
            word-break: break-word;
          }

          .madar-website-name-note {
            margin: 0 !important;
            color: #6d7484 !important;
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
            border-radius: 14px;
            padding: 0 16px;
            font-weight: 950;
            cursor: pointer;
          }

          .madar-website-name-secondary {
            background: rgba(26, 39, 68, 0.08);
            color: #1a2744;
          }

          .madar-website-name-primary {
            background: var(--theme-gradient);
            color: #ffffff;
            box-shadow: 0 12px 28px rgba(var(--theme-primary-rgb), 0.22);
          }

          @media (max-width: 640px) {
            .madar-website-name-modal {
              padding: 22px;
              border-radius: 24px;
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
              {(project?.siteChrome?.brand || project?.name || "M").slice(0, 1)}
            </div>

            <div>
              <span className="madar-website-name-kicker">
                One quick step
              </span>

              <h2 id="website-name-title">Create your website link</h2>

              <p>Pick a short name people can use to open your website.</p>
            </div>
          </div>

          <div className="madar-website-name-form">
            <label className="madar-website-name-label">
              Website name

              <div className="madar-website-name-input-row">
                <input
                  value={websiteName}
                  placeholder="my-business"
                  autoFocus
                  onChange={handleWebsiteNameChange}
                />

                <span>.{domain}</span>
              </div>
            </label>

            {error && <p className="madar-website-name-error">{error}</p>}

            <div className="madar-website-name-preview">
              <span>Your website link</span>
              <strong>{websiteLink}</strong>
            </div>

            <p className="madar-website-name-note">
              After saving, your Login button will open this website login page.
            </p>

            <div className="madar-website-name-actions">
            <button
              type="button"
              className="madar-website-name-primary"
              onClick={handleSave}
            >
              Create website link
            </button>
          </div>
          </div>
        </section>
      </div>
    </>
  );
}

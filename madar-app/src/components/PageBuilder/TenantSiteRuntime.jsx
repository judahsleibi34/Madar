import { useMemo } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import LoginPage from "../LoginPage";
import { STORAGE_KEY, defaultSiteChrome } from "./PageBuilder.constants";

const splitLines = (value) =>
  String(value || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

const getCleanSubdomain = (value = "") =>
  String(value)
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9-]/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-+|-+$/g, "") || "my-site";

const loadPublishedProject = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

export default function TenantSiteRuntime() {
  const { subdomain = "my-site" } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const cleanSubdomain = getCleanSubdomain(subdomain);

  const project = useMemo(() => loadPublishedProject(), []);
  const site = {
    ...defaultSiteChrome,
    ...(project?.siteChrome || {}),
    headerButtonLabel: "Login",
  };

  const pages = project?.pages || [];
  const activePath = location.pathname;
  const isLoginPage = activePath.endsWith("/login");
  const isDashboardPage = activePath.endsWith("/dashboard");

  const siteHomePath = `/site/${cleanSubdomain}`;
  const loginPath = `/site/${cleanSubdomain}/login`;
  const dashboardPath = `/site/${cleanSubdomain}/dashboard`;

  const pageLinks = splitLines(site.footerShopLinks || "Home\nSubmit Request\nReports");
  const helpLinks = splitLines(site.footerHelpLinks || "About Us\nPolicies\nContact");
  const socialLinks = splitLines(site.footerSocialLinks || "Facebook\nLinkedIn\nX\nInstagram");
  const footerLinks = [...pageLinks, ...helpLinks];

  const brandName = site.brand || "Madar";
  const footerBrand = site.footerStoreName || brandName;
  const footerInitial = footerBrand.trim().slice(0, 1).toUpperCase() || "M";

  const goToPage = (page) => {
    if (!page) {
      navigate(siteHomePath);
      return;
    }

    const slug = page.slug === "/" ? "" : page.slug;
    navigate(`/site/${cleanSubdomain}${slug}`);
  };

  const goToFooterLink = (label) => {
    const normalizedLabel = label.toLowerCase().trim();

    const target = pages.find((page) => {
      const normalizedName = String(page.name || "").toLowerCase().trim();
      const normalizedSlug = String(page.slug || "")
        .toLowerCase()
        .replace(/^\//, "");

      return (
        normalizedName === normalizedLabel ||
        normalizedSlug === normalizedLabel.replace(/\s+/g, "-")
      );
    });

    if (target) {
      goToPage(target);
      return;
    }

    if (normalizedLabel === "home") {
      navigate(siteHomePath);
      return;
    }

    if (normalizedLabel === "login") {
      navigate(loginPath);
    }
  };

  const renderHeader = () => (
    <header className="tenant-site-header">
      <div className="tenant-site-header-inner">
        <button
          type="button"
          className="tenant-site-brand"
          onClick={() => navigate(siteHomePath)}
        >
          {site.logoUrl ? (
            <img src={site.logoUrl} alt={`${brandName} logo`} />
          ) : (
            <span className="tenant-logo-fallback">
              {brandName.slice(0, 1).toUpperCase() || "M"}
            </span>
          )}

          <span>{brandName}</span>
        </button>

        <nav className="tenant-site-nav">
          {pages.map((page) => {
            const pagePath =
              page.slug === "/"
                ? siteHomePath
                : `/site/${cleanSubdomain}${page.slug}`;

            return (
              <button
                type="button"
                key={page.id}
                className={activePath === pagePath ? "active" : ""}
                onClick={() => goToPage(page)}
              >
                {page.name}
              </button>
            );
          })}
        </nav>

        <button
          type="button"
          className="tenant-site-cta"
          onClick={() => navigate(loginPath)}
        >
          Login
        </button>
      </div>
    </header>
  );

  const renderFooter = () => (
    <footer className="tenant-site-footer">
      <div className="tenant-footer-grid">
        <div className="tenant-footer-brand">
          <div className="tenant-footer-logo-row">
            {site.logoUrl ? (
              <img
                className="tenant-footer-logo"
                src={site.logoUrl}
                alt={`${footerBrand} logo`}
              />
            ) : (
              <div className="tenant-footer-logo tenant-footer-logo-fallback">
                {footerInitial}
              </div>
            )}

            <h3>{footerBrand}</h3>
          </div>

          <p>
            {site.description ||
              "An adaptive business management platform for creating and managing digital systems."}
          </p>

          <div className="tenant-social-row">
            {socialLinks.map((item) => (
              <button type="button" key={item} aria-label={item}>
                {item.slice(0, 2).toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        <div className="tenant-footer-column">
          <h4>Links</h4>

          <div className="tenant-footer-links-grid">
            {footerLinks.map((item) => (
              <button
                type="button"
                key={item}
                onClick={() => goToFooterLink(item)}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        <div className="tenant-footer-contact">
          <h4>Contact</h4>

          <div className="tenant-language-pill">
            <span>◎</span>
            <strong>{site.footerLanguageLabel || "AR"}</strong>
          </div>

          <p>{site.contactEmail || "info@madar.com"}</p>
          <p dir="ltr">{site.phone || "+972 0599203857"}</p>
        </div>
      </div>

      <div className="tenant-footer-bottom">
        <p>
          © 2026 {footerBrand}. {site.rights || "All rights reserved."}
        </p>

        <button type="button" onClick={() => navigate("/")}>
          Powered by Madar
        </button>
      </div>
    </footer>
  );

  const renderMainContent = () => {
    if (isLoginPage) {
      return (
        <main className="tenant-login-runtime">
          <LoginPage
            lang="en"
            onLoginSuccess={() => navigate(dashboardPath, { replace: true })}
          />
        </main>
      );
    }

    if (isDashboardPage) {
      return (
        <main className="tenant-runtime-main">
          <section className="tenant-runtime-card">
            <p className="tenant-eyebrow">{cleanSubdomain}.madar.app</p>
            <h1>Website workspace</h1>
            <p>
              This is the private workspace for this website. Later, this page
              will show internal dashboards, forms, responses, and team tools.
            </p>

            <div className="tenant-runtime-actions">
              <button type="button" onClick={() => navigate(siteHomePath)}>
                Open website
              </button>

              <button type="button" onClick={() => navigate(loginPath)}>
                Open login page
              </button>
            </div>
          </section>
        </main>
      );
    }

    return (
      <main className="tenant-runtime-main">
        <section className="tenant-runtime-card">
          <p className="tenant-eyebrow">{cleanSubdomain}.madar.app</p>
          <h1>{project?.name || "Your website is ready"}</h1>
          <p>
            This is the public preview for this website. The full published site
            renderer will be connected here next.
          </p>

          <div className="tenant-runtime-actions">
            <button type="button" onClick={() => navigate(loginPath)}>
              Login
            </button>
          </div>
        </section>
      </main>
    );
  };

  return (
    <div className="tenant-site-runtime">
      {renderHeader()}
      {renderMainContent()}
      {renderFooter()}
    </div>
  );
}
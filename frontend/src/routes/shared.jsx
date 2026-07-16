import { useEffect, useRef } from "react";
import { Menu, X } from "lucide-react";

import DashboardSidebar from "../components/DashboardBuilder/DashboardSidebar";
import { appShellContent } from "../content";

const AUTHENTICATED_REFERENCE_WIDTH = 1440;
const AUTHENTICATED_REFERENCE_HEIGHT = 900;
const AUTHENTICATED_MIN_LAYOUT_SCALE = 0.67;
const AUTHENTICATED_MIN_TEXT_SCALE = 0.82;

function useAuthenticatedReferenceScale() {
  const shellRef = useRef(null);

  useEffect(() => {
    const shell = shellRef.current;
    if (!shell || typeof ResizeObserver === "undefined") return undefined;

    let animationFrame = 0;
    let previousLayoutScale = "";
    let previousTextScale = "";

    const updateScale = () => {
      animationFrame = 0;
      const { width, height } = shell.getBoundingClientRect();
      if (!width || !height) return;

      const rawScale = Math.min(
        width / AUTHENTICATED_REFERENCE_WIDTH,
        height / AUTHENTICATED_REFERENCE_HEIGHT
      );
      const layoutScale = Math.max(
        AUTHENTICATED_MIN_LAYOUT_SCALE,
        Math.min(1, rawScale)
      ).toFixed(4);
      const textScale = Math.max(
        AUTHENTICATED_MIN_TEXT_SCALE,
        Number(layoutScale)
      ).toFixed(4);

      if (layoutScale !== previousLayoutScale) {
        shell.style.setProperty("--ui-layout-scale", layoutScale);
        previousLayoutScale = layoutScale;
      }
      if (textScale !== previousTextScale) {
        shell.style.setProperty("--ui-text-scale", textScale);
        previousTextScale = textScale;
      }
    };

    const scheduleScaleUpdate = () => {
      if (!animationFrame) animationFrame = window.requestAnimationFrame(updateScale);
    };

    const observer = new ResizeObserver(scheduleScaleUpdate);
    observer.observe(shell);
    shell.querySelectorAll(":scope > .admin-sidebar, :scope > .admin-dashboard-page").forEach((element) => observer.observe(element));
    scheduleScaleUpdate();

    return () => {
      observer.disconnect();
      if (animationFrame) window.cancelAnimationFrame(animationFrame);
    };
  }, []);

  return shellRef;
}

export function RestrictedAccessWindow({
  title = appShellContent.restrictedAccess.title,
  message = appShellContent.restrictedAccess.defaultMessage,
  actionLabel = appShellContent.restrictedAccess.actionLabel,
  onAction,
}) {
  return (
    <section className="restricted-access-page">
      <div className="restricted-access-card" role="status">
        <div className="restricted-access-content">
          <p className="restricted-access-eyebrow">{title}</p>
          <h1>{title}</h1>
          <p>{message}</p>
        </div>

        <button type="button" onClick={onAction}>
          {actionLabel}
        </button>
      </div>
    </section>
  );
}

export function DashboardSkeleton({ label, lang }) {
  return (
    <div
      className="dashboard-skeleton-layout"
      aria-label={label}
      dir={lang === "ar" ? "rtl" : "ltr"}
    >
      <aside className="dashboard-skeleton-sidebar">
        <div className="skeleton-logo-row">
          <div className="skeleton-circle" />
          <div>
            <div className="skeleton-line skeleton-title" />
            <div className="skeleton-line skeleton-small" />
          </div>
        </div>

        <div className="skeleton-nav">
          {Array.from({ length: 8 }).map((_, index) => (
            <div className="skeleton-sidebar-row" key={index}>
              <div className="skeleton-circle skeleton-sidebar-icon" />
              <div className="skeleton-line skeleton-sidebar-label" />
            </div>
          ))}
        </div>

        <div className="skeleton-sidebar-bottom">
          <div className="skeleton-sidebar-row">
            <div className="skeleton-circle skeleton-sidebar-icon" />
            <div className="skeleton-line skeleton-sidebar-label" />
          </div>

          <div className="skeleton-sidebar-row">
            <div className="skeleton-circle skeleton-sidebar-icon" />
            <div className="skeleton-line skeleton-sidebar-label" />
          </div>

          <div className="skeleton-user-row">
            <div className="skeleton-circle skeleton-user-avatar" />
            <div className="skeleton-user-lines">
              <div className="skeleton-line skeleton-user-badge" />
              <div className="skeleton-line skeleton-user-name" />
              <div className="skeleton-line skeleton-user-email" />
            </div>
          </div>
        </div>
      </aside>

      <section className="dashboard-skeleton-page">
        <div className="dashboard-skeleton-header">
          <div className="skeleton-line skeleton-heading" />
          <div className="skeleton-line skeleton-subheading" />
        </div>

        <div className="dashboard-skeleton-cards">
          <div className="skeleton-card" />
          <div className="skeleton-card" />
          <div className="skeleton-card" />
          <div className="skeleton-card" />
        </div>

        <div className="dashboard-skeleton-panels">
          <div className="skeleton-panel skeleton-panel-large" />
          <div className="skeleton-panel" />
        </div>

        <div className="dashboard-skeleton-panels lower">
          <div className="skeleton-panel" />
          <div className="skeleton-panel" />
        </div>
      </section>
    </div>
  );
}

export function FormBuilderSkeleton({ lang }) {
  return (
    <div
      className="forms-loading-shell"
      aria-label="Loading forms"
      dir={lang === "ar" ? "rtl" : "ltr"}
    >
      <aside className="forms-loading-app-rail" aria-hidden="true">
        <span className="forms-loading-avatar forms-loading-shimmer" />
        <div className="forms-loading-rail-stack">
          {Array.from({ length: 6 }).map((_, index) => (
            <span className="forms-loading-rail-icon forms-loading-shimmer" key={index} />
          ))}
        </div>
        <span className="forms-loading-avatar small forms-loading-shimmer" />
      </aside>

      <main className="forms-loading-page">
        <header className="forms-loading-header">
          <span className="forms-loading-line title forms-loading-shimmer" />
          <span className="forms-loading-line subtitle forms-loading-shimmer" />
        </header>

        <div className="forms-loading-workspace">
          <aside className="forms-loading-controls">
            {Array.from({ length: 5 }).map((_, index) => (
              <div className="forms-loading-control-group" key={index}>
                <span className="forms-loading-line label forms-loading-shimmer" />
                <span className="forms-loading-control forms-loading-shimmer" />
              </div>
            ))}
            <div className="forms-loading-actions">
              {Array.from({ length: 4 }).map((_, index) => (
                <span className="forms-loading-button forms-loading-shimmer" key={index} />
              ))}
            </div>
          </aside>

          <section className="forms-loading-document">
            <div className="forms-loading-document-top">
              <span className="forms-loading-line page-title forms-loading-shimmer" />
              <span className="forms-loading-pill forms-loading-shimmer" />
            </div>
            <span className="forms-loading-textarea forms-loading-shimmer" />
            <div className="forms-loading-toolbar">
              {Array.from({ length: 5 }).map((_, index) => (
                <span className="forms-loading-tool forms-loading-shimmer" key={index} />
              ))}
            </div>
            {Array.from({ length: 3 }).map((_, index) => (
              <article className="forms-loading-question" key={index}>
                <span className="forms-loading-dot forms-loading-shimmer" />
                <div className="forms-loading-question-body">
                  <span className="forms-loading-line question-title forms-loading-shimmer" />
                  <span className="forms-loading-control answer forms-loading-shimmer" />
                  <span className="forms-loading-line hint forms-loading-shimmer" />
                </div>
                <span className="forms-loading-type forms-loading-shimmer" />
              </article>
            ))}
          </section>
        </div>
      </main>
    </div>
  );
}

export function FormPreviewSkeleton({ lang }) {
  return (
    <main
      className="form-preview-loading-page"
      aria-label={appShellContent.loading.formPreview}
      dir={lang === "ar" ? "rtl" : "ltr"}
    >
      <header className="form-preview-loading-topbar">
        <span className="form-preview-loading-button forms-loading-shimmer" />
        <span className="form-preview-loading-title forms-loading-shimmer" />
      </header>

      <section className="form-preview-loading-shell">
        <div className="form-preview-loading-header">
          <span className="form-preview-loading-line heading forms-loading-shimmer" />
          <span className="form-preview-loading-line copy forms-loading-shimmer" />
        </div>

        {Array.from({ length: 4 }).map((_, index) => (
          <article className="form-preview-loading-question" key={index}>
            <span className="form-preview-loading-line label forms-loading-shimmer" />
            <span className="form-preview-loading-input forms-loading-shimmer" />
            {index < 2 && <span className="form-preview-loading-line help forms-loading-shimmer" />}
          </article>
        ))}

        <footer className="form-preview-loading-actions">
          <span className="form-preview-loading-small-button forms-loading-shimmer" />
          <span className="form-preview-loading-page-pill forms-loading-shimmer" />
          <span className="form-preview-loading-submit forms-loading-shimmer" />
        </footer>
      </section>
    </main>
  );
}

const builderSkeletonTabs = [
  { id: "design", label: "Pages" },
  { id: "forms", label: "Forms" },
  { id: "reservations", label: "Reservations" },
  { id: "chrome", label: "Header & Footer" },
  { id: "users", label: "Users" },
  { id: "publish", label: "Publish" },
];

const builderSkeletonPathTabs = {
  pages: "design",
  design: "design",
  forms: "forms",
  reservations: "reservations",
  chrome: "chrome",
  "header-footer": "chrome",
  users: "users",
  theme: "design",
  themes: "design",
  "website-theme": "design",
  publish: "publish",
  responses: "responses",
  data: "data",
};

const getBuilderSkeletonTab = (pathname = "") => {
  if (pathname.startsWith("/builder-responses")) return "responses";
  if (pathname.startsWith("/builder-data")) return "data";

  const match = pathname.match(/^\/page-builder\/([^/?#]+)/);
  if (!match) return "design";

  return builderSkeletonPathTabs[match[1]] || "design";
};

function BuilderSkeletonPanel({ variant }) {
  if (variant === "design") {
    return (
      <div className="builder-skeleton-design">
        <aside className="builder-skeleton-side-panel">
          {Array.from({ length: 6 }).map((_, index) => (
            <span className="builder-skeleton-line" key={index} />
          ))}
        </aside>
        <section className="builder-skeleton-canvas">
          <span className="builder-skeleton-hero" />
          <div className="builder-skeleton-section-grid">
            <span />
            <span />
            <span />
          </div>
        </section>
        <aside className="builder-skeleton-inspector">
          {Array.from({ length: 7 }).map((_, index) => (
            <span className="builder-skeleton-line" key={index} />
          ))}
        </aside>
      </div>
    );
  }

  if (variant === "forms") {
    return (
      <div className="builder-skeleton-forms">
        <aside className="builder-skeleton-side-panel">
          {Array.from({ length: 5 }).map((_, index) => (
            <span className="builder-skeleton-pill" key={index} />
          ))}
        </aside>
        <section className="builder-skeleton-document">
          <span className="builder-skeleton-wide-line" />
          {Array.from({ length: 3 }).map((_, index) => (
            <article className="builder-skeleton-question" key={index}>
              <span />
              <span />
            </article>
          ))}
        </section>
      </div>
    );
  }

  if (variant === "reservations") {
    return (
      <div className="builder-skeleton-reservations">
        <section className="builder-skeleton-calendar">
          {Array.from({ length: 35 }).map((_, index) => (
            <span key={index} />
          ))}
        </section>
        <aside className="builder-skeleton-side-panel">
          {Array.from({ length: 6 }).map((_, index) => (
            <span className="builder-skeleton-line" key={index} />
          ))}
        </aside>
      </div>
    );
  }

  if (variant === "chrome") {
    return (
      <div className="builder-skeleton-chrome">
        <section className="builder-skeleton-site-preview">
          <span className="builder-skeleton-site-header" />
          <span className="builder-skeleton-site-body" />
          <span className="builder-skeleton-site-footer" />
        </section>
        <aside className="builder-skeleton-side-panel">
          {Array.from({ length: 7 }).map((_, index) => (
            <span className="builder-skeleton-line" key={index} />
          ))}
        </aside>
      </div>
    );
  }

  if (variant === "users") {
    return (
      <div className="builder-skeleton-users">
        <div className="builder-skeleton-stats">
          <span />
          <span />
          <span />
        </div>
        {Array.from({ length: 5 }).map((_, index) => (
          <article className="builder-skeleton-user-row" key={index}>
            <span />
            <span />
            <span />
          </article>
        ))}
      </div>
    );
  }

  if (variant === "theme") {
    return (
      <div className="builder-skeleton-theme">
        <section className="builder-skeleton-swatches">
          {Array.from({ length: 8 }).map((_, index) => (
            <span key={index} />
          ))}
        </section>
        <section className="builder-skeleton-theme-preview">
          <span />
          <span />
          <span />
        </section>
      </div>
    );
  }

  if (variant === "publish") {
    return (
      <div className="builder-skeleton-publish">
        <section className="builder-skeleton-status-grid">
          <span />
          <span />
          <span />
          <span />
        </section>
        <section className="builder-skeleton-share-grid">
          <span />
          <span />
        </section>
      </div>
    );
  }

  if (variant === "responses" || variant === "data") {
    return (
      <div className="builder-skeleton-data">
        <aside className="builder-skeleton-side-panel">
          {Array.from({ length: 6 }).map((_, index) => (
            <span className="builder-skeleton-line" key={index} />
          ))}
        </aside>
        <section className="builder-skeleton-table">
          {Array.from({ length: 7 }).map((_, index) => (
            <span key={index} />
          ))}
        </section>
      </div>
    );
  }

  return <BuilderSkeletonPanel variant="design" />;
}

export function PageBuilderSkeleton({ lang, pathname = "/page-builder" }) {
  const activeTab = getBuilderSkeletonTab(pathname);
  const isSinglePage = activeTab === "responses" || activeTab === "data";
  const titleByTab = {
    design: "Loading pages",
    forms: "Loading forms",
    reservations: "Loading reservations",
    chrome: "Loading header and footer",
    users: "Loading users",
    theme: "Loading themes",
    publish: "Loading publish tools",
    responses: "Loading responses",
    data: "Loading data workspace",
  };

  return (
    <section
      className="builder-skeleton-workspace"
      aria-label={titleByTab[activeTab] || "Loading builder"}
      dir={lang === "ar" ? "rtl" : "ltr"}
    >
      <header className="builder-skeleton-header">
        <div>
          <span className="builder-skeleton-title" />
          <span className="builder-skeleton-subtitle" />
        </div>
      </header>

      {!isSinglePage && (
        <nav className="builder-skeleton-tabs" aria-hidden="true">
          {builderSkeletonTabs.map((tab) => (
            <span
              className={tab.id === activeTab ? "is-active" : ""}
              key={tab.id}
            >
              {tab.label}
            </span>
          ))}
        </nav>
      )}

      <BuilderSkeletonPanel variant={activeTab} />
    </section>
  );
}

export function DashboardLoadingElement({ pathname, labels, lang }) {
  if (pathname.startsWith("/page-builder/form-preview")) {
    return <FormPreviewSkeleton lang={lang} />;
  }

  if (
    pathname.startsWith("/page-builder") ||
    pathname.startsWith("/builder-responses") ||
    pathname.startsWith("/builder-data")
  ) {
    return <PageBuilderSkeleton lang={lang} pathname={pathname} />;
  }

  const safeLabels = labels || appShellContent.loading || {};
  let label = safeLabels.dashboard || "Loading dashboard";

  if (pathname.startsWith("/page-builder")) label = safeLabels.pageBuilder || label;
  if (pathname.startsWith("/builder-responses")) label = safeLabels.submissions || label;
  if (pathname.startsWith("/builder-data")) label = safeLabels.dataLogs || label;
  if (pathname.startsWith("/archive")) label = safeLabels.archive || "Loading archive";
  if (pathname.startsWith("/my-plan")) label = safeLabels.myPlan || label;
  if (pathname.startsWith("/admin/users")) label = safeLabels.userManagement || label;
  if (pathname.startsWith("/settings/change-password")) label = safeLabels.passwordSettings || label;
  if (pathname.startsWith("/settings")) label = safeLabels.settings || label;

  return <DashboardSkeleton label={label} lang={lang} />;
}

export function DashboardShell({
  children,
  compactSidebar = false,
  hideLanguage = false,
  isPageBuilderShell = false,
  lang,
  onLanguageChange,
  onLogout,
  onNavigate,
  onSidebarToggle,
  onThemeModeChange,
  open,
  openMenuLabel,
  closeMenuLabel,
  shellLang,
  themeMode,
  user,
}) {
  const activeLang = shellLang || lang;
  const isShellRtl = activeLang === "ar";
  const useCompactBuilderSidebar = isPageBuilderShell || compactSidebar;

  const shellRef = useAuthenticatedReferenceScale();
  return (
    <div
      ref={shellRef}
      className={[
        "admin-dashboard-layout",
        useCompactBuilderSidebar ? "admin-dashboard-layout-builder" : "",
        isShellRtl ? "is-rtl" : "is-ltr",
        open ? "sidebar-open" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      dir={isShellRtl ? "rtl" : "ltr"}
    >
      <button
        type="button"
        className="dashboard-mobile-menu-button"
        onClick={onSidebarToggle}
        aria-label={open ? closeMenuLabel : openMenuLabel}
        aria-expanded={open}
        aria-controls="dashboard-sidebar"
      >
        {open ? <X size={22} /> : <Menu size={22} />}
      </button>

      <button
        type="button"
        className="dashboard-sidebar-backdrop"
        onClick={onNavigate}
        aria-label={closeMenuLabel}
      />

      <DashboardSidebar
        id="dashboard-sidebar"
        lang={activeLang}
        user={user}
        onLogout={onLogout}
        onLanguageChange={hideLanguage ? undefined : onLanguageChange}
        hideLanguage={hideLanguage}
        themeMode={themeMode}
        onThemeModeChange={onThemeModeChange}
        compact={useCompactBuilderSidebar}
        onNavigate={onNavigate}
        showNotifications
      />

      <main
        className={[
          "admin-dashboard-page",
          isPageBuilderShell ? "page-builder-dashboard-page" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        dir={isShellRtl ? "rtl" : "ltr"}
      >
        {children}
      </main>
    </div>
  );
}

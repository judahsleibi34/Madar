const skeletonLines = (count, className = "page-skeleton-line") =>
  Array.from({ length: count }).map((_, index) => (
    <span className={className} key={index} />
  ));

function PublicPageSkeleton() {
  return (
    <>
      <section className="page-skeleton-hero">
        <div className="page-skeleton-copy">
          <span className="page-skeleton-kicker" />
          <span className="page-skeleton-title" />
          {skeletonLines(3)}
        </div>
        <div className="page-skeleton-visual" />
      </section>
      <section className="page-skeleton-card-grid">
        <span />
        <span />
        <span />
      </section>
    </>
  );
}

function AuthSkeleton() {
  return (
    <section className="page-skeleton-auth-card">
      <span className="page-skeleton-title compact" />
      {skeletonLines(2)}
      <span className="page-skeleton-input" />
      <span className="page-skeleton-input" />
      <span className="page-skeleton-button" />
    </section>
  );
}

function TenantRuntimeSkeleton() {
  return (
    <>
      <header className="page-skeleton-tenant-header">
        <span className="page-skeleton-logo" />
        <span className="page-skeleton-nav" />
        <span className="page-skeleton-pill" />
      </header>
      <section className="page-skeleton-tenant-main">
        <span className="page-skeleton-title" />
        {skeletonLines(3)}
        <div className="page-skeleton-card-grid">
          <span />
          <span />
        </div>
      </section>
    </>
  );
}

function DataAnalysisSkeleton() {
  return (
    <section className="page-skeleton-data-analysis">
      <div className="page-skeleton-data-header">
        <span className="page-skeleton-title compact" />
        <span className="page-skeleton-line" />
      </div>
      <div className="page-skeleton-data-grid">
        <aside>
          {skeletonLines(5)}
          <span className="page-skeleton-button" />
        </aside>
        <section>
          {skeletonLines(7, "page-skeleton-row")}
        </section>
      </div>
    </section>
  );
}

export default function PageSkeleton({
  label = "Loading page",
  lang = "en",
  variant = "public-page",
}) {
  const contentByVariant = {
    auth: <AuthSkeleton />,
    "data-analysis": <DataAnalysisSkeleton />,
    "tenant-runtime": <TenantRuntimeSkeleton />,
    default: <PublicPageSkeleton />,
    "public-page": <PublicPageSkeleton />,
  };

  return (
    <main
      className={`page-skeleton page-skeleton-${variant}`}
      dir={lang === "ar" ? "rtl" : "ltr"}
      aria-busy="true"
      aria-label={label}
    >
      <span className="page-skeleton-status" role="status" aria-live="polite">
        {label}
      </span>
      {contentByVariant[variant] || contentByVariant.default}
    </main>
  );
}


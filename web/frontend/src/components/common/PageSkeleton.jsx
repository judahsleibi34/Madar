import LoadingBar from "./LoadingBar";

export default function PageSkeleton({
  label = "Loading page",
  lang = "en",
  variant = "public-page",
  brand = "",
  imageUrl = "",
}) {
  const hasBrandVisual = Boolean(brand && imageUrl);
  const brandThemeStyle = hasBrandVisual ? {
    "--theme-bg": "#f3efe7",
    "--theme-surface": "#fffdf8",
    "--theme-text": "#21312a",
    "--theme-primary": "#365849",
    "--theme-primary-rgb": "54, 88, 73",
  } : undefined;

  return (
    <main
      className={`page-skeleton page-skeleton-${variant} ${hasBrandVisual ? "page-skeleton-brand-visual" : ""}`}
      dir={lang === "ar" ? "rtl" : "ltr"}
      aria-busy="true"
      aria-label={label}
      style={brandThemeStyle}
    >
      {hasBrandVisual ? (
        <div className="page-skeleton-site-shell">
          <header className="page-skeleton-site-header">
            <strong>{brand}</strong>
            <nav aria-hidden="true"><i /><i /><i /></nav>
            <i className="page-skeleton-site-action" aria-hidden="true" />
          </header>
          <section className="page-skeleton-site-hero">
            <div className="page-skeleton-site-copy" aria-hidden="true">
              <i className="is-title" />
              <i className="is-title is-short" />
              <i className="is-line" />
              <i className="is-line is-short" />
              <i className="is-button" />
              <LoadingBar label={label} mode="inline" />
            </div>
            <img src={imageUrl} alt="" loading="eager" decoding="async" fetchPriority="high" />
          </section>
          <section className="page-skeleton-site-cards" aria-hidden="true"><i /><i /><i /></section>
        </div>
      ) : <LoadingBar label={label} />}
    </main>
  );
}

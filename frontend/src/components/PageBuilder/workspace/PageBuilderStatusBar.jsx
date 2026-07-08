export default function PageBuilderStatusBar({ canonicalLiveSitePath, toast }) {
  return (
    <>
      {toast && (
        <div className="builder-toast" role="status" aria-live="polite">
          <span className="builder-toast-icon" aria-hidden="true">✓</span>
          <span className="builder-toast-message">
            <strong>Madar Builder</strong>
            <span>{toast}</span>
          </span>
        </div>
      )}
      {canonicalLiveSitePath && (
        <a
          className="builder-live-site-link"
          href={canonicalLiveSitePath}
          target="_blank"
          rel="noreferrer"
        >
          Open live site
        </a>
      )}
    </>
  );
}

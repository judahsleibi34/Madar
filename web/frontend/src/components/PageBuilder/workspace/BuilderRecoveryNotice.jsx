export default function BuilderRecoveryNotice({ decision, onDiscard, onExport, onKeepServer }) {
  if (!decision) return null;

  const copy = {
    restorable: {
      title: "Unsaved browser recovery found",
      message: "Madar loaded the server version first. Download this emergency copy if you need it, or discard it when it is no longer useful.",
    },
    stale_conflict: {
      title: "A stale browser recovery was found",
      message: "Madar has a newer cloud revision. The browser copy was not applied and cannot overwrite it automatically.",
    },
    invalid: {
      title: "The browser recovery is not valid",
      message: "Its revision is newer than the cloud record or its metadata is inconsistent. It was not applied.",
    },
    expired: {
      title: "An expired browser recovery was found",
      message: "The recovery is older than the retention window and was not applied.",
    },
    malformed: {
      title: "The browser recovery cannot be read",
      message: "The stored value was preserved and was not applied to the cloud project.",
    },
    identity_mismatch: {
      title: "A recovery copy belongs to another project",
      message: "The copy was ignored and cannot be attached to this project.",
    },
    legacy: {
      title: "A legacy browser draft was found",
      message: "Legacy drafts have no tenant, project, or revision identity. Export or discard it; Madar will never attach it automatically.",
    },
  }[decision.kind] || {
    title: "Browser recovery needs attention",
    message: "The browser copy was not applied automatically.",
  };

  return (
    <section className="builder-recovery-notice" role="alertdialog" aria-modal="false" aria-labelledby="builder-recovery-title">
      <div>
        <strong id="builder-recovery-title">{copy.title}</strong>
        <p>{copy.message}</p>
      </div>
      <div className="builder-recovery-actions">
        {(decision.envelope || decision.legacy?.raw) && (
          <button type="button" onClick={onExport}>Download recovery</button>
        )}
        <button type="button" onClick={onKeepServer}>Continue with server</button>
        <button type="button" onClick={onDiscard}>Discard recovery</button>
      </div>
    </section>
  );
}

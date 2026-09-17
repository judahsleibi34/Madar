import { Download, RefreshCw, TriangleAlert, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

const formatSafeTime = (value) => {
  const timestamp = value ? new Date(value) : null;
  return timestamp && Number.isFinite(timestamp.getTime())
    ? timestamp.toLocaleString([], { dateStyle: "medium", timeStyle: "short" })
    : "Not available";
};

export default function BuilderConflictResolution({
  conflict,
  onDownload,
  onLoadCandidate,
  onResolveConflicts,
  onUseServer,
}) {
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resolutions, setResolutions] = useState({});
  const primaryButtonRef = useRef(null);

  useEffect(() => {
    if (open) primaryButtonRef.current?.focus();
  }, [confirming, open]);

  if (!conflict) return null;
  const conflicts = Array.isArray(conflict.conflicts) ? conflict.conflicts : [];
  const hasReviewableConflicts = conflicts.length > 0;

  const displayValue = (value, missing) => {
    if (missing) return "Deleted";
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      const text = String(value);
      return text.length > 120 ? `${text.slice(0, 117)}…` : text || "Empty";
    }
    if (value === null) return "None";
    return "Changed content";
  };

  const conflictLabel = (item) => {
    const entityName = item?.entity?.name;
    const path = String(item?.path || "Project setting");
    return entityName ? `${entityName} — ${path.split(".").at(-1)}` : path;
  };

  const openResolution = async () => {
    setOpen(true);
    setLoading(true);
    try {
      await onLoadCandidate?.();
    } finally {
      setLoading(false);
    }
  };

  const useServer = async () => {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    setLoading(true);
    try {
      await onUseServer?.();
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <section className="builder-conflict-banner" role="alert" data-testid="builder-conflict-banner">
        <span className="builder-conflict-banner-icon" aria-hidden="true"><TriangleAlert size={20} /></span>
        <div className="builder-conflict-banner-copy">
          <strong>{hasReviewableConflicts ? "Some edits conflict with changes from another session" : "This project changed elsewhere"}</strong>
          <p>Saving and publishing are paused. No local edit was discarded or overwritten automatically.</p>
        </div>
        <div className="builder-conflict-banner-actions">
          <button type="button" className="builder-conflict-download" onClick={onDownload}>
            <Download size={16} aria-hidden="true" /> Download local copy
          </button>
          <button type="button" className="builder-conflict-resolve" onClick={openResolution}>
            {hasReviewableConflicts ? "Review conflicts" : "Resolve conflict"}
          </button>
        </div>
      </section>

      {open && (
        <div className="builder-modal-backdrop builder-conflict-backdrop" role="presentation">
          <section
            className="builder-modal builder-conflict-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="builder-conflict-dialog-title"
          >
            <div className="modal-header">
              <div>
                <h2 id="builder-conflict-dialog-title">Resolve editing conflict</h2>
                <p>
                  This browser has local edits based on an older project version. A newer version exists on Madar.
                  Automatic saving and publishing remain paused, and no work was overwritten automatically.
                </p>
              </div>
              <button type="button" aria-label="Close conflict dialog" onClick={() => setOpen(false)}><X size={20} /></button>
            </div>

            <dl className="builder-conflict-metadata">
              <div><dt>Local recovery saved</dt><dd>{formatSafeTime(conflict.localSavedAt)}</dd></div>
              <div><dt>Server updated</dt><dd>{formatSafeTime(conflict.serverUpdatedAt)}</dd></div>
              <div><dt>Local base revision</dt><dd>{conflict.localBaseRevision ?? "Unknown"}</dd></div>
              <div><dt>Current server revision</dt><dd>{conflict.serverRevision ?? "Checking…"}</dd></div>
            </dl>

            {hasReviewableConflicts && (
              <div className="builder-conflict-review" aria-label="Conflicting edits">
                {conflicts.map((item, index) => (
                  <fieldset className="builder-conflict-item" key={`${item.path}-${index}`}>
                    <legend>{conflictLabel(item)}</legend>
                    <label>
                      <input
                        type="radio"
                        name={`builder-conflict-${index}`}
                        checked={resolutions[index] === "local"}
                        onChange={() => setResolutions((current) => ({ ...current, [index]: "local" }))}
                      />
                      <span><strong>Keep my change</strong><small>{displayValue(item.localValue, item.localMissing)}</small></span>
                    </label>
                    <label>
                      <input
                        type="radio"
                        name={`builder-conflict-${index}`}
                        checked={resolutions[index] === "server"}
                        onChange={() => setResolutions((current) => ({ ...current, [index]: "server" }))}
                      />
                      <span><strong>Keep server change</strong><small>{displayValue(item.serverValue, item.serverMissing)}</small></span>
                    </label>
                  </fieldset>
                ))}
                <button
                  type="button"
                  className="builder-conflict-primary"
                  disabled={loading || conflicts.some((_, index) => !resolutions[index])}
                  onClick={async () => {
                    setLoading(true);
                    try {
                      await onResolveConflicts?.(resolutions);
                    } finally {
                      setLoading(false);
                    }
                  }}
                >
                  {loading ? "Saving resolution…" : "Save resolved changes"}
                </button>
              </div>
            )}

            {confirming && (
              <div className="builder-conflict-destructive-warning" role="alert">
                <TriangleAlert size={20} aria-hidden="true" />
                <p><strong>Discard local changes?</strong> The editor will replace this browser’s unsaved copy with the latest server version. Download it first if you may need it.</p>
              </div>
            )}

            <div className="builder-conflict-dialog-actions">
              <button type="button" className="builder-conflict-secondary" onClick={onDownload}>
                <Download size={16} aria-hidden="true" /> Download local changes
              </button>
              <button type="button" className="builder-conflict-secondary" onClick={() => setOpen(false)}>
                Keep viewing local copy
              </button>
              <button type="button" className="builder-conflict-secondary" onClick={() => { setConfirming(false); setOpen(false); }}>
                Cancel
              </button>
              <button
                ref={primaryButtonRef}
                type="button"
                className={confirming ? "builder-conflict-danger" : "builder-conflict-primary"}
                disabled={loading}
                onClick={useServer}
              >
                <RefreshCw size={16} aria-hidden="true" />
                {loading ? "Loading latest version…" : confirming ? "Discard my edits and use server version" : "Replace my local edits with the latest saved version"}
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  );
}

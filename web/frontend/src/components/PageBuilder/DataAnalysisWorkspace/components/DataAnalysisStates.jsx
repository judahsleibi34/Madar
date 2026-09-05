import { AlertTriangle, Check, X } from "lucide-react";

export function DataAnalysisFlowToast({ message, title, onDismiss }) {
  if (!message) return null;

  return (
    <div className="daw-flow-toast" role="alert" aria-live="assertive">
      <span>
        <AlertTriangle size={18} />
      </span>
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
      </div>
      <button type="button" aria-label="Dismiss message" onClick={onDismiss}>
        <X size={16} />
      </button>
    </div>
  );
}

export function VisualizationStatusMessage({
  error,
  success,
  notice,
  issueTitle,
  onDismiss,
}) {
  if (!error && !success && !notice) return null;

  const isSuccess = Boolean(success);
  const isNotice = !isSuccess && !error;
  const message = success || error || notice;

  return (
    <div
      className={`daw-modal-alert ${
        isSuccess ? "daw-modal-alert-success" : ""
      } ${isNotice ? "daw-modal-alert-info" : ""}`}
      role={isSuccess || isNotice ? "status" : "alert"}
      aria-live={isSuccess || isNotice ? "polite" : "assertive"}
    >
      <span>
        {isSuccess ? <Check size={18} /> : <AlertTriangle size={18} />}
      </span>
      <div>
        <strong>{isSuccess ? "Success" : isNotice ? "Color note" : issueTitle}</strong>
        <p>{message}</p>
      </div>
      <button type="button" aria-label="Dismiss message" onClick={onDismiss}>
        <X size={16} />
      </button>
    </div>
  );
}

export function VisualizationPreviewModal({ preview, onClose }) {
  if (!preview) return null;

  const title = preview.title || "Chart preview";

  return (
    <div className="daw-modal-backdrop" role="dialog" aria-modal="true">
      <section className="daw-modal daw-visualization-preview-modal">
        <div className="daw-modal-header">
          <div>
            <h3>{title}</h3>
          </div>
          <button
            type="button"
            className="daw-icon-button"
            aria-label="Close preview"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </div>

        <div className="daw-visualization-preview-stage">
          <img src={preview.url} alt={title} />
        </div>

        <div className="daw-modal-actions">
          <button type="button" className="daw-primary" onClick={onClose}>
            Done
          </button>
        </div>
      </section>
    </div>
  );
}


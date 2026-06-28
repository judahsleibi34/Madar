import { getPageDeleteConfirmContent } from "../../../content";

export default function PageDeleteConfirmModal({
  page,
  lang = "en",
  title,
  message,
  cancelLabel,
  confirmLabel,
  confirmDisabled = false,
  onCancel,
  onConfirm,
}) {
  const content = getPageDeleteConfirmContent(lang);
  const modalTitle = title || content.title;
  const modalMessage =
    message ||
    (page ? (
      <>
        <strong>"{page.name}"</strong> {content.messageSuffix}
      </>
    ) : null);
  const secondaryLabel = cancelLabel || (page ? content.keepPage : content.cancel);
  const dangerLabel = confirmLabel || (page ? content.deletePage : content.delete);

  if (!page && !title && !message) return null;

  return (
    <div className="page-delete-modal-backdrop" onClick={onCancel}>
      <section
        className="page-delete-modal"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="page-delete-modal-title"
      >
        <div className="page-delete-modal-icon">{content.icon}</div>

        <div className="page-delete-modal-copy">
          <h2 id="page-delete-modal-title">{modalTitle}</h2>
          {modalMessage && <p>{modalMessage}</p>}
        </div>

        <div className="page-delete-modal-actions">
          <button
            type="button"
            className="page-delete-modal-secondary"
            onClick={onCancel}
          >
            {secondaryLabel}
          </button>

          <button
            type="button"
            className="page-delete-modal-danger"
            onClick={onConfirm}
            disabled={confirmDisabled}
          >
            {dangerLabel}
          </button>
        </div>
      </section>
    </div>
  );
}

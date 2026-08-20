import "../../styles/public pages/subscription-modal.css";
import { getSubscriptionModalContent } from "../../content";

export default function SubscriptionStatusModal({
  open,
  type = "success",
  lang = "en",
  title,
  message,
  confirmLabel,
  onConfirm,
}) {
  if (!open) return null;

  const isArabic = lang === "ar";
  const t = getSubscriptionModalContent(lang);

  const modalTitle =
    title || (type === "success" ? t.successTitle : t.errorTitle);

  const modalMessage =
    message || (type === "success" ? t.successMessage : t.errorMessage);

  return (
    <div
      className="subscription-modal-backdrop"
      onClick={onConfirm}
      dir={isArabic ? "rtl" : "ltr"}
    >
      <section
        className={`subscription-modal subscription-modal-${type}`}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="subscription-modal-title"
      >
        <div className="subscription-modal-icon">
          {type === "success" ? "✓" : "!"}
        </div>

        <div className="subscription-modal-copy">
          <h2 id="subscription-modal-title">{modalTitle}</h2>
          <p>{modalMessage}</p>
        </div>

        <div className="subscription-modal-actions">
          <button
            type="button"
            className="subscription-modal-primary"
            onClick={onConfirm}
          >
            {confirmLabel || t.confirm}
          </button>
        </div>
      </section>
    </div>
  );
}

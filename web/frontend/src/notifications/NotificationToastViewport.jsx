import { useEffect } from "react";
import { createPortal } from "react-dom";
import { Bell, X } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { useLanguage } from "../i18n";
import { getSafeNotificationActionPath } from "./notificationActions";
import { useNotifications } from "./NotificationContext";

const MAX_VISIBLE_TOASTS = 3;
const TOAST_LIFETIME_MS = 7_000;

function NotificationToast({ dismissLabel, fallbackTitle, item, onDismiss, onOpen }) {
  useEffect(() => {
    const timer = window.setTimeout(() => onDismiss(item.key), TOAST_LIFETIME_MS);
    return () => window.clearTimeout(timer);
  }, [item.key, onDismiss]);

  return (
    <article className="notification-toast" role="status" data-notification-id={item.id}>
      <span className="notification-toast-icon" aria-hidden="true">
        <Bell size={18} />
      </span>
      <button
        type="button"
        className="notification-toast-content"
        onClick={() => onOpen(item)}
      >
        <strong>{item.title || fallbackTitle}</strong>
        {item.detail ? <span>{item.detail}</span> : null}
      </button>
      <button
        type="button"
        className="notification-toast-dismiss"
        onClick={() => onDismiss(item.key)}
        aria-label={dismissLabel}
      >
        <X size={17} aria-hidden="true" />
      </button>
    </article>
  );
}

export default function NotificationToastViewport() {
  const navigate = useNavigate();
  const { direction, t } = useLanguage();
  const { dismissToast, toastQueue, tenantId } = useNotifications();
  const visibleToasts = toastQueue.slice(0, MAX_VISIBLE_TOASTS);

  const openToast = (item) => {
    dismissToast(item.key);
    navigate(getSafeNotificationActionPath(item.data?.action, { tenantId }));
  };

  if (!visibleToasts.length || typeof document === "undefined") return null;

  return createPortal(
    <section
      className="notification-toast-viewport"
      aria-label={t("notifications.newToastRegion")}
      aria-live="polite"
      aria-relevant="additions"
      dir={direction}
    >
      {visibleToasts.map((item) => (
        <NotificationToast
          dismissLabel={t("notifications.dismissToast")}
          fallbackTitle={t("notifications.fallbackTitle")}
          item={item}
          key={item.key}
          onDismiss={dismissToast}
          onOpen={openToast}
        />
      ))}
    </section>,
    document.body,
  );
}

export { MAX_VISIBLE_TOASTS, TOAST_LIFETIME_MS };

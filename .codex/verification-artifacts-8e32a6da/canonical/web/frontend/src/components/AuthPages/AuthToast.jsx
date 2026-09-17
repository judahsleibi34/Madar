import { useEffect } from "react";

export default function AuthToast({
  title,
  message,
  type = "error",
  dir = "ltr",
  onDismiss,
  duration = 4200,
}) {
  useEffect(() => {
    if (!title && !message) return undefined;

    const timer = window.setTimeout(() => {
      onDismiss?.();
    }, duration);

    return () => window.clearTimeout(timer);
  }, [duration, message, onDismiss, title]);

  if (!title && !message) return null;

  return (
    <div className={`auth-toast auth-toast-${type}`} role="alert" aria-live="assertive" dir={dir}>
      <span className="auth-toast-icon" aria-hidden="true">
        {type === "error" ? "!" : "✓"}
      </span>
      <span className="auth-toast-message">
        {title && <strong>{title}</strong>}
        {message && <span>{message}</span>}
      </span>
    </div>
  );
}

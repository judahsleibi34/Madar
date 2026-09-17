import { useEffect } from "react";

export default function RuntimeFormToast({ toast, onDismiss }) {
  useEffect(() => {
    if (!toast) return undefined;
    const timer = window.setTimeout(() => onDismiss?.(), 4500);
    return () => window.clearTimeout(timer);
  }, [onDismiss, toast]);

  if (!toast) return null;

  return (
    <div className="runtime-form-toast" role="alert" aria-live="assertive">
      <span className="runtime-form-toast-icon" aria-hidden="true">!</span>
      <span className="runtime-form-toast-copy">
        <strong>{toast.title || "Please check the form"}</strong>
        <span>{toast.message}</span>
      </span>
      <button type="button" onClick={onDismiss} aria-label="Dismiss notification">×</button>
    </div>
  );
}


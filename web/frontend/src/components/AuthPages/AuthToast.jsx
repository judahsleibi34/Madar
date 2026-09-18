import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, X } from "lucide-react";

export default function AuthToast({
  title,
  message,
  type = "error",
  dir = "ltr",
  onDismiss,
  duration = 4200,
}) {
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    if ((!title && !message) || paused) return undefined;

    const timer = window.setTimeout(() => {
      onDismiss?.();
    }, duration);

    return () => window.clearTimeout(timer);
  }, [duration, message, onDismiss, title, paused]);

  if (!title && !message) return null;

  return (
    <div className={`auth-toast auth-toast-${type}`} role={type === "error" ? "alert" : "status"} aria-live={type === "error" ? "assertive" : "polite"} dir={dir} onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)} onFocus={() => setPaused(true)} onBlur={() => setPaused(false)}>
      <span className="auth-toast-icon" aria-hidden="true">
        {type === "error" ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
      </span>
      <span className="auth-toast-message">
        {title && <strong>{title}</strong>}
        {message && <span>{message}</span>}
      </span>
      {onDismiss && <button type="button" className="auth-toast-dismiss" onClick={onDismiss} aria-label={dir === "rtl" ? "\u0625\u063a\u0644\u0627\u0642" : "Dismiss notification"}><X size={18} aria-hidden="true" /></button>}
    </div>
  );
}

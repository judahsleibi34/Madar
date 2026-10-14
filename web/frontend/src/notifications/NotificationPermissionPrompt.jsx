import { useEffect, useMemo, useRef, useState } from "react";
import { BellRing, X } from "lucide-react";

import {
  enableBrowserPushNotifications,
  getBrowserPushStatus,
  getPushPublicKey,
} from "../services/notificationsApi";
import "../styles/admin/dashboard/notification-permission-prompt.css";

const DISMISSED_SESSION_KEY = "madar-notification-permission-prompt-dismissed-v1";

const COPY = {
  en: {
    title: "Enable notifications?",
    description: "Get important Madar updates on this device.",
    enable: "Enable notifications",
    enabling: "Enabling…",
    later: "Not now",
    close: "Close notification prompt",
    blockedTitle: "Notifications are blocked",
    blockedDescription: "Allow notifications for Madar in this browser's site settings, then reload the page.",
    iosTitle: "Add Madar to your Home Screen",
    iosDescription: "On iPhone or iPad, tap Share, choose Add to Home Screen, then open Madar from its icon to enable notifications.",
    understood: "Got it",
    failed: "Notifications could not be enabled. Please try again.",
  },
  ar: {
    title: "تفعيل الإشعارات؟",
    description: "احصل على تحديثات مدار المهمة على هذا الجهاز.",
    enable: "تفعيل الإشعارات",
    enabling: "جارٍ التفعيل…",
    later: "ليس الآن",
    close: "إغلاق نافذة الإشعارات",
    blockedTitle: "الإشعارات محظورة",
    blockedDescription: "اسمح بإشعارات مدار من إعدادات الموقع في المتصفح، ثم أعد تحميل الصفحة.",
    iosTitle: "أضف مدار إلى الشاشة الرئيسية",
    iosDescription: "على iPhone أو iPad، اضغط مشاركة ثم إضافة إلى الشاشة الرئيسية، وبعدها افتح مدار من الأيقونة لتفعيل الإشعارات.",
    understood: "حسناً",
    failed: "تعذر تفعيل الإشعارات. حاول مرة أخرى.",
  },
};

function readDismissed(identity) {
  try {
    return window.sessionStorage.getItem(`${DISMISSED_SESSION_KEY}:${identity}`) === "1";
  } catch {
    return false;
  }
}

function rememberDismissed(identity) {
  try {
    window.sessionStorage.setItem(`${DISMISSED_SESSION_KEY}:${identity}`, "1");
  } catch {
    // A blocked session store should not prevent the user from closing the dialog.
  }
}

export default function NotificationPermissionPrompt({ user, lang = "en" }) {
  const copy = COPY[lang === "ar" ? "ar" : "en"];
  const identity = useMemo(
    () => `${user?.tenant_id || "tenant"}:${user?.id || user?.auth_id || user?.email || "user"}`,
    [user?.auth_id, user?.email, user?.id, user?.tenant_id],
  );
  const previousFocusRef = useRef(null);
  const primaryButtonRef = useRef(null);
  const [prompt, setPrompt] = useState(null);
  const [pushConfig, setPushConfig] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    if (!identity || readDismissed(identity)) return undefined;

    const inspect = async () => {
      const status = await getBrowserPushStatus().catch(() => ({ enabled: false, reason: "unavailable" }));
      if (cancelled || status.enabled) return;

      if (status.reason === "permission_denied") {
        setPrompt("blocked");
        return;
      }
      if (status.reason === "ios_home_screen_required") {
        setPrompt("ios");
        return;
      }
      if (["unsupported", "android_browser_unsupported", "secure_context_required", "unavailable"].includes(status.reason)) {
        return;
      }

      const config = await getPushPublicKey().catch(() => null);
      if (cancelled || !config?.enabled || !config?.public_key) return;
      setPushConfig(config);
      setPrompt("enable");
    };

    void inspect();
    return () => { cancelled = true; };
  }, [identity]);

  useEffect(() => {
    if (!prompt) return undefined;
    previousFocusRef.current = document.activeElement;
    primaryButtonRef.current?.focus();
    const closeOnEscape = (event) => {
      if (event.key === "Escape") {
        rememberDismissed(identity);
        setPrompt(null);
      }
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      previousFocusRef.current?.focus?.();
    };
  }, [identity, prompt]);

  if (!prompt) return null;

  const dismiss = () => {
    rememberDismissed(identity);
    setPrompt(null);
  };

  const enable = async () => {
    if (busy || !pushConfig) return;
    setBusy(true);
    setError("");
    try {
      const result = await enableBrowserPushNotifications({
        tenantId: user?.tenant_id,
        pushConfig,
      });
      if (!result.enabled) {
        if (result.reason === "permission_denied") setPrompt("blocked");
        else setError(copy.failed);
        return;
      }
      setPrompt(null);
    } catch {
      setError(copy.failed);
    } finally {
      setBusy(false);
    }
  };

  const isEnablePrompt = prompt === "enable";
  const title = prompt === "blocked" ? copy.blockedTitle : prompt === "ios" ? copy.iosTitle : copy.title;
  const description = prompt === "blocked"
    ? copy.blockedDescription
    : prompt === "ios" ? copy.iosDescription : copy.description;

  return (
    <div className="notification-permission-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget) dismiss();
    }} dir={lang === "ar" ? "rtl" : "ltr"}>
      <section
        className="notification-permission-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="notification-permission-title"
        aria-describedby="notification-permission-description"
      >
        <button type="button" className="notification-permission-close" aria-label={copy.close} onClick={dismiss}>
          <X size={19} aria-hidden="true" />
        </button>
        <span className="notification-permission-icon" aria-hidden="true"><BellRing size={30} /></span>
        <div className="notification-permission-copy">
          <h2 id="notification-permission-title">{title}</h2>
          <p id="notification-permission-description">{description}</p>
        </div>
        {error && <p className="notification-permission-error" role="alert">{error}</p>}
        <div className="notification-permission-actions">
          {isEnablePrompt ? (
            <>
              <button ref={primaryButtonRef} type="button" className="notification-permission-primary" disabled={busy} onClick={enable}>
                <BellRing size={18} aria-hidden="true" /> {busy ? copy.enabling : copy.enable}
              </button>
              <button type="button" className="notification-permission-secondary" disabled={busy} onClick={dismiss}>{copy.later}</button>
            </>
          ) : (
            <button ref={primaryButtonRef} type="button" className="notification-permission-primary" onClick={dismiss}>{copy.understood}</button>
          )}
        </div>
      </section>
    </div>
  );
}

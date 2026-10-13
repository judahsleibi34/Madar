import { useCallback, useEffect, useId, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import EcommerceToast from "../DashboardBuilder/EcommerceToast";

// Only local copy goes into the toast. Contextual errors and recovery actions
// remain inline, announced once, and available after the toast is dismissed.
const activeNotices = new Set();
const listeners = new Set();
let revision = 0;
let dismissed = false;
const subscribe = listener => { listeners.add(listener); return () => listeners.delete(listener); };
const snapshot = () => revision;
function publish() { revision += 1; for (const listener of listeners) listener(); }

export function LearningErrorToast() {
  const { t, i18n } = useTranslation("dashboard");
  const id = useId();
  useSyncExternalStore(subscribe, snapshot, snapshot);
  useEffect(() => {
    activeNotices.add(id);
    dismissed = false;
    publish();
    return () => { activeNotices.delete(id); publish(); };
  }, [id]);
  const dismiss = useCallback(() => { dismissed = true; publish(); }, []);
  // Concurrent field/request errors share a single visual toast, while each
  // contextual inline message retains its own recovery action.
  return !dismissed && activeNotices.values().next().value === id && createPortal(<EcommerceToast
    type="error" announce={false} dir={i18n.dir?.() || (i18n.language?.startsWith("ar") ? "rtl" : "ltr")} onDismiss={dismiss}
    title={t("elearning.ui.error_toast_title")}
    message={t("elearning.ui.error_toast_help")}
  />, document.body);
}

export default function LearningErrorNotice({ as: Tag = "div", role = "alert", children, ...props }) {
  return <><Tag {...props} role={role}>{children}</Tag>{role === "alert" && <LearningErrorToast />}</>;
}

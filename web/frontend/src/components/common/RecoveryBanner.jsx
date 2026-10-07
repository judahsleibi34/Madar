import { useEffect, useState } from "react";
import { apiFetch } from "../../utils/apiClient";

export default function RecoveryBanner() {
  const [restricted, setRestricted] = useState(false);
  useEffect(() => {
    let active = true;
    const check = () => apiFetch(`${import.meta.env.VITE_API_URL || "/api"}/health/recovery`)
      .then((response) => response.ok ? response.json() : null)
      .then((data) => { if (active && data) setRestricted(data.restricted === true); })
      .catch(() => {});
    check();
    const timer = window.setInterval(check, 60000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  if (!restricted) return null;
  return <aside role="status" aria-live="polite" style={{ padding: "12px", background: "var(--color-surface-muted)", color: "var(--color-text)", borderBottom: "2px solid var(--color-border)", textAlign: "center" }}>
    Madar is temporarily in restricted, read-only recovery mode. Sign-in and account reads remain available. Business changes are paused.
    <span lang="ar" dir="rtl" style={{ display: "block" }}>مدار يعمل مؤقتاً في وضع الاستعادة للقراءة فقط. تسجيل الدخول متاح والتغييرات متوقفة.</span>
  </aside>;
}

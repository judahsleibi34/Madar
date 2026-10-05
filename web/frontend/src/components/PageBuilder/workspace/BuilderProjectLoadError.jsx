import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchELearningSettings } from "../../../services/elearningSettings";
import { initializeAcademyLanding } from "../../../services/elearningAcademy";

export default function BuilderProjectLoadError({ status, lang = "en" }) {
  const navigate = useNavigate();
  const [academyAvailable, setAcademyAvailable] = useState(false);
  const [busy, setBusy] = useState(false);
  const [recoveryError, setRecoveryError] = useState(false);
  const ar = lang === "ar";

  useEffect(() => {
    if (status !== 404) return;
    let active = true;
    // A missing UUID cannot identify its former profile. Offer an explicit,
    // owner-authorized recovery choice rather than redirecting website projects.
    fetchELearningSettings().then(data => {
      if (active) setAcademyAvailable(Boolean(data.available && data.academy_management?.full_builder_available));
    }).catch(() => {});
    return () => { active = false; };
  }, [status]);

  async function openAcademy() {
    setBusy(true);
    setRecoveryError(false);
    try {
      // The existing initializer enforces tenant, owner and Builder entitlement,
      // and atomically reuses the current durable Academy draft.
      const project = await initializeAcademyLanding();
      if (!project?.id || project.usage_profile !== "academy") throw new Error("Academy project unavailable");
      navigate(`/e-learning/landing-page/projects/${encodeURIComponent(project.id)}/pages`, { replace: true });
    } catch {
      setRecoveryError(true);
      setBusy(false);
    }
  }

  return <main className="builder-project-loading" dir={ar ? "rtl" : "ltr"}>
    <div className="builder-project-loading-card">
      <h2>{status === 404 ? (ar ? "رابط المشروع غير متاح" : "This project link is unavailable") : (ar ? "تعذر تحميل المشروع" : "Project could not be loaded")}</h2>
      <p>{status === 404
        ? (ar ? "قد يكون المشروع محذوفاً أو غير متاح لحسابك. افتح مشروعك الحالي من المنشئ." : "This project may have been removed or may not be available to your account. Open your current project from the Builder.")
        : status === 403
          ? (ar ? "ليس لديك صلاحية لفتح هذا المشروع." : "You do not have permission to open this project.")
          : (ar ? "تعذر الاتصال بالمشروع المحفوظ. أعد المحاولة." : "The saved project could not be reached. Please retry.")}</p>
      {academyAvailable && <button type="button" className="page-primary-action" disabled={busy} onClick={openAcademy}>
        {busy ? (ar ? "جارٍ فتح الأكاديمية…" : "Opening Academy…") : (ar ? "فتح منشئ الأكاديمية" : "Open Academy Builder")}
      </button>}
      {recoveryError && <p role="alert">{ar ? "تعذر فتح الأكاديمية. تحقق من صلاحيات المنشئ من إعدادات الأكاديمية ثم أعد المحاولة." : "Academy could not be opened. Check your Builder access in Academy settings and try again."}</p>}
      <Link className="page-secondary-action" to="/page-builder">{ar ? "العودة إلى المشاريع" : "Back to Projects"}</Link>
      <button type="button" className="page-secondary-action" disabled={busy} onClick={() => window.location.reload()}>{ar ? "إعادة المحاولة" : "Retry"}</button>
    </div>
  </main>;
}

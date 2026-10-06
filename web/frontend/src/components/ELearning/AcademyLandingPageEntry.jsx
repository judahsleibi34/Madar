import { lazy, useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { initializeAcademyLanding } from "../../services/elearningAcademy";
import ELearningSkeleton from "./ELearningSkeleton";
const PageBuilder = lazy(() => import("../PageBuilder"));
const TenantSiteRuntime = lazy(() => import("../PageBuilder/runtime/TenantSiteRuntime"));

// The server selects or creates the current owner's dedicated Academy project.
// Never resolve this entry through the generic website project chooser.
export default function AcademyLandingPageEntry(editorProps) {
  const navigate = useNavigate();
  const { projectId = "" } = useParams();
  const location = useLocation();
  const { t, i18n } = useTranslation("dashboard");
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState(null);
  useEffect(() => {
    let active = true;
    initializeAcademyLanding().then(project => {
      if (!active) return;
      if (project.usage_profile !== "academy" || (projectId && projectId !== project.id)) {
        setResult({ projectId, error: "elearning.academy.editorMissingError" });
        return;
      }
      if (projectId) setResult({ projectId, authorized: true });
      else navigate(`/e-learning/landing-page/projects/${encodeURIComponent(project.id)}/pages`, { replace: true });
    }).catch(error => {
      if (!active) return;
      const key = !error.status ? "editorNetworkError" : error.status === 402 ? "editorPlanError" : error.status === 403 ? "editorPermissionError" : "editorOpenError";
      setResult({ projectId, error: `elearning.academy.${key}` });
    });
    return () => { active = false; };
  }, [navigate, attempt, projectId]);
  const current = result?.projectId === projectId ? result : null;
  if (current?.authorized) return location.pathname.includes(`/projects/${projectId}/preview`)
    ? <TenantSiteRuntime draftPreview user={editorProps.user} />
    : <PageBuilder key={projectId} {...editorProps} />;
  if (!current?.error) return <ELearningSkeleton variant="settings" label={t("elearning.loading")} direction={i18n.dir()} lang={i18n.language} />;
  return <main className="ecommerce-page" dir={i18n.dir()} lang={i18n.language}>
    <h1>{t("elearning.academy.landingPage")}</h1>
    <p role="alert">{t(current.error)}</p>
    {current.error === "elearning.academy.editorPlanError" && <Link className="ecommerce-secondary-button" to="/my-plan">{t("elearning.academy.reviewPlan")}</Link>}
    <button className="ecommerce-primary-button" onClick={() => { setResult(null); setAttempt(value => value + 1); }}>{t("elearning.retry")}</button>
    <Link className="ecommerce-secondary-button" to="/e-learning/academy-access">{t("elearning.academy.accessSettings")}</Link>
  </main>;
}

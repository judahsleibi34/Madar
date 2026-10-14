import { useTranslation } from "react-i18next";
import { Clock } from "lucide-react";
import "../styles/enrollment-checkout.css";

// Mirrors the Plans notice an opt-in academy shows in production (ELearningAcademy.jsx).
export function EnrollmentClosedSample() {
  const { t } = useTranslation("dashboard");
  return <div style={{ display: "grid", gap: 12, maxWidth: 640 }}>
    <div className="enrollment-closed" role="status"><Clock size={20} aria-hidden="true" /><p><strong>{t("elearning.enrollment.opensSoon")}</strong> {t("elearning.enrollment.opensSoonHelp")}</p></div>
    <button className="academy-button ecommerce-primary-button" disabled>{t("elearning.enrollment.opensSoon")}</button>
  </div>;
}

import { ChevronDown, ClipboardList } from "lucide-react";
import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
export default function LearningFormsNavigation({ forms, onNavigate, discover = false, open: controlledOpen, onToggle }) {
  const { t } = useTranslation("dashboard");
  const [localOpen, setLocalOpen] = useState(true);
  const open = controlledOpen ?? localOpen;
  const location = useLocation();
  const responses = location.pathname.startsWith("/e-learning/forms/responses");
  const activeProps = active => ({className:active?"active":"", "aria-current":active?"page":undefined});
  if (!discover && !forms?.visible) return null;
  return <div className="dashboard-sidebar-subsection">
    <button type="button" className="admin-sidebar-row" aria-expanded={open} aria-controls="academy-forms-navigation" onClick={onToggle || (() => setLocalOpen(!localOpen))}>
      <ClipboardList className="admin-sidebar-row-icon" size={18} aria-hidden="true" />
      <span className="admin-sidebar-row-label">{t("elearning.forms.title")}</span>
      <ChevronDown className="admin-sidebar-chevron" size={17} aria-hidden="true" />
    </button>
    {open && <div className="admin-sidebar-subnav" id="academy-forms-navigation">
      <Link {...activeProps(!responses&&location.pathname.startsWith('/e-learning/forms'))} to="/e-learning/forms" onClick={onNavigate}>{t("elearning.forms.manage")}</Link>
      <Link {...activeProps(responses)} to="/e-learning/forms/responses" onClick={onNavigate}>{t("elearning.forms.all_responses")}</Link>
    </div>}
  </div>;
}

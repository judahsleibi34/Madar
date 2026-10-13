import { ChevronDown } from "lucide-react";

export default function LearningSettingsAccordion({ title, description, icon: Icon, children, group, defaultOpen = false, className = "" }) {
  function collapseOthers(event) {
    const current=event.currentTarget;
    if(!current.open)return;
    for(const section of current.closest('form')?.querySelectorAll('details[data-settings-accordion]') || []) {
      if(section!==current && section.name===group)section.open=false;
    }
  }
  return <details className={`settings-card elearning-settings-accordion ${className}`} name={group} open={defaultOpen} data-settings-accordion onToggle={collapseOthers}>
    <summary>
      {Icon && <span className="elearning-card-icon"><Icon size={20} aria-hidden="true" /></span>}
      <span className="elearning-settings-accordion-copy"><h3>{title}</h3>{description && <span>{description}</span>}</span>
      <ChevronDown size={18} className="elearning-settings-chevron" aria-hidden="true" />
    </summary>
    <div className="elearning-settings-accordion-body">{children}</div>
  </details>;
}

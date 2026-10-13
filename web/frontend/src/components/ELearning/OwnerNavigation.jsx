import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronDown, LayoutDashboard, BookOpen, Users, ClipboardList, CreditCard, BarChart3, Globe, Settings, BadgeDollarSign } from "lucide-react";
import { apiFetch, getApiUrl } from "../../utils/apiClient";
import LearningFormsNavigation from "./LearningFormsNavigation";
const matchesPath = (pathname,path) => pathname === path || path !== '/e-learning/forms' && pathname.startsWith(path + '/') || path === '/e-learning/exchange-opportunities' && (pathname === '/e-learning/programmes/exchange' || pathname.startsWith('/e-learning/programmes/exchange/'));
function Group({
  label,
  items,
  onNavigate,
  open,
  onToggle,
  icon: Icon
}) {
  const location = useLocation();
  const id = `academy-nav-${items[0][1].replaceAll('/', '-')}`;
  return <div><button type="button" className="admin-sidebar-row" aria-expanded={open} aria-controls={id} onClick={onToggle}>{Icon&&<Icon className="admin-sidebar-row-icon" size={18} aria-hidden="true"/>}<span className="admin-sidebar-row-label">{label}</span><ChevronDown className="admin-sidebar-chevron" size={17} aria-hidden="true" /></button>{open && <div className="admin-sidebar-subnav" id={id}>{items.map(([name, path]) => {
        const active = matchesPath(location.pathname,path);
        return <Link key={path} className={active ? 'active' : ''} aria-current={active ? 'page' : undefined} to={path} onClick={onNavigate}>{name}</Link>;
      })}</div>}</div>;
}
export default function OwnerNavigation({
  capabilities = {},
  programmeFlags = {},
  forms,
  onNavigate,
  supportName,
  exchangeName
}) {
  const location = useLocation();
  const [reviewAvailable,setReviewAvailable]=useState(false);
  useEffect(() => {
    let active=true;
    Promise.resolve().then(() => apiFetch(getApiUrl("/elearning/assessment-capabilities"),{cache:"no-store"})).then(response => response?.ok ? response.json() : null).then(value => {if(active) setReviewAvailable(Boolean(value?.available && value?.can_review));}).catch(() => {});
    return () => {active=false;};
  }, []);
  const [expanded, setExpanded] = useState(null);
  const {
      t
    } = useTranslation('dashboard'),
    ui = k => t(`elearning.ui.${k}`),
    p = k => t(`elearning.programmes.${k}`);
  const icons={learning_group:BookOpen,engagement_group:Users,applications_group:ClipboardList,finance_group:CreditCard,insights_group:BarChart3,website_group:Globe,configuration_group:Settings};
  const groups = [['learning_group', [[t('sidebar.elearningCourses'), '/e-learning/courses'], [reviewAvailable && t('elearning.assessment.reviews'), '/e-learning/assessment-reviews'], [p('students'), '/e-learning/students'], [t('sidebar.elearningGroups'), '/e-learning/groups'], [t('sidebar.elearningInstructors'), '/e-learning/instructors']]], ['engagement_group', [[capabilities.affiliate && programmeFlags.affiliate === true && p('affiliate'), '/e-learning/programmes/affiliate'], [capabilities.referrals && p('referrals'), '/e-learning/finance/referrals'], [capabilities.rewards && p('rewards'), '/e-learning/finance/rewards']]], ['applications_group', [[capabilities.tuition && programmeFlags.tuition === true && (supportName || p('support')), '/e-learning/programmes/tuition'], [capabilities.exchange && programmeFlags.exchange === true && (exchangeName || p('exchange')), '/e-learning/exchange-opportunities']]], ['finance_group', [[capabilities.transactions && p('transactions'), '/e-learning/finance/transactions'], [capabilities.withdrawal && p('withdrawal'), '/e-learning/finance/withdrawals']]], ['insights_group', [[capabilities.reports && p('reports'), '/e-learning/reports'], [capabilities.reports && t('elearning.adminControls.auditTitle'), '/e-learning/audit-log']]], ['website_group', [[capabilities.contact && ui('edit_website'), '/e-learning/landing-page'], [capabilities.contact && t('elearning.theme.title'), '/e-learning/theme'], [capabilities.contact && t('elearning.owner.contacts'), '/e-learning/contacts']]], ['configuration_group', [[t('elearning.academy.academyAccess'), '/e-learning/academy-access'], [t('sidebar.settings'), '/e-learning/settings']]]];
  const activeGroup = location.pathname.startsWith('/e-learning/forms') && capabilities.forms
    ? 'forms'
    : groups.find(([, items]) => items.some(([name, path]) => name && (matchesPath(location.pathname,path))))?.[0] || null;
  const openGroup = expanded?.path === location.pathname ? expanded.key : activeGroup;
  const toggle = key => setExpanded({path: location.pathname, key: openGroup === key ? null : key});
  const overviewActive = matchesPath(location.pathname, '/e-learning/dashboard');
  const plansActive = matchesPath(location.pathname, '/e-learning/plans');
  return <><Link className={`admin-sidebar-row${overviewActive ? ' active' : ''}`} aria-current={overviewActive ? 'page' : undefined} to="/e-learning/dashboard" onClick={onNavigate}><LayoutDashboard className="admin-sidebar-row-icon" size={18} aria-hidden="true" /><span className="admin-sidebar-row-label">{t('elearning.owner.overview')}</span></Link><Link className={`admin-sidebar-row${plansActive ? ' active' : ''}`} aria-current={plansActive ? 'page' : undefined} to="/e-learning/plans" onClick={onNavigate}><BadgeDollarSign className="admin-sidebar-row-icon" size={18} aria-hidden="true" /><span className="admin-sidebar-row-label">{t('elearning.academy.learningPlans')}</span></Link>{groups.slice(0, 3).map(([key, items]) => {
      const allowed = items.filter(([name]) => name);
      return allowed.length > 0 && <Group open={openGroup === key} onToggle={() => toggle(key)} icon={icons[key]} key={key} label={ui(key)} items={allowed} onNavigate={onNavigate} />;
    })}{capabilities.forms && <LearningFormsNavigation forms={forms || {
      visible: true,
      items: []
    }} open={openGroup === 'forms'} onToggle={() => toggle('forms')} onNavigate={onNavigate} discover />}{groups.slice(3).map(([key, items]) => {
      const allowed = items.filter(([name]) => name);
      return allowed.length > 0 && <Group open={openGroup === key} onToggle={() => toggle(key)} icon={icons[key]} key={key} label={key === 'finance_group' ? p('finance') : ui(key)} items={allowed} onNavigate={onNavigate} />;
    })}</>;
}

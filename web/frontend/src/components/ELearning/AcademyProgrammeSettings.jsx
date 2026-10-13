import { Settings2, Handshake, GraduationCap, Globe, Wallet } from "lucide-react";
import LearningSettingsAccordion from "./LearningSettingsAccordion";
import { useTranslation } from "react-i18next";
const programmeIcons = { commerce_settings: Settings2, affiliate_settings: Handshake, support_settings: GraduationCap, exchange_settings: Globe, withdrawal_settings: Wallet };

export default function AcademyProgrammeSettings({
  settings,
  capabilities,
  visibleGroups,
  compact = false,
  expandedGroup,
  update
}) {
  const {
      t
    } = useTranslation('dashboard'),
    label = k => t(`elearning.programmes.${k}`);
  const groups = [['commerce_settings', capabilities.affiliate || capabilities.tuition || capabilities.exchange, ['programmes_enabled']], ['affiliate_settings', capabilities.affiliate, ['affiliates_enabled', 'affiliate_applications_enabled', 'affiliate_terms']], ['support_settings', capabilities.tuition, ['support_programme_name', 'tuition_support_enabled', 'tuition_applications_enabled', 'tuition_support_information_required', 'support_eligibility', 'tuition_sales_threshold', 'tuition_terms']], ['exchange_settings', capabilities.exchange, ['exchange_programme_name', 'exchange_programme_enabled', 'exchange_applications_enabled', 'exchange_opportunities_enabled', 'exchange_terms']], ['withdrawal_settings', capabilities.withdrawal, ['withdrawals_enabled', 'minimum_withdrawal_amount', 'withdrawal_methods']], ['notifications', true, ['learning_notifications_enabled']]];
  return <>{groups.filter(([group, visible]) => visible && (!visibleGroups || visibleGroups.includes(group))).map(([group,, keys]) => {
    const content = <div className="settings-form-grid">{keys.map(key => key.endsWith('_enabled') || key === 'tuition_support_information_required' ? <label key={key} className="elearning-toggle"><span>{label(key)}</span><input type="checkbox" role="switch" checked={key === 'learning_notifications_enabled' ? settings[key] ?? true : Boolean(settings[key])} onChange={e => update(key, e.target.checked)} /></label> : key.endsWith('_terms') || key === 'withdrawal_methods' ? <label className="elearning-field" key={key}>{label(key)}<textarea dir="auto" maxLength={12000} value={key === 'withdrawal_methods' ? (settings[key] || []).join('\n') : settings[key] || ''} onChange={e => update(key, key === 'withdrawal_methods' ? e.target.value.split('\n').filter(Boolean) : e.target.value)} /></label> : key === 'support_eligibility' ? <label className="elearning-field" key={key}>{label(key)}<select value={settings[key] || 'verified_referral_sales'} onChange={e => update(key, e.target.value)}>{['verified_referral_sales', 'active_learner'].map(v => <option key={v} value={v}>{label(v)}</option>)}</select></label> : ['tuition_sales_threshold', 'minimum_withdrawal_amount'].includes(key) ? <label className="elearning-field" key={key}>{label(key)}<input type="number" min={key === 'tuition_sales_threshold' ? 1 : 0.01} step={key === 'tuition_sales_threshold' ? 1 : 0.01} required={key === 'tuition_sales_threshold' ? settings.tuition_support_enabled && settings.support_eligibility === 'verified_referral_sales' : settings.withdrawals_enabled} value={settings[key] ?? ''} onChange={e => update(key, e.target.value ? key === 'tuition_sales_threshold' ? Number(e.target.value) : e.target.value : null)} /></label> : <label className="elearning-field" key={key}>{label(key)}<input required maxLength={120} value={settings[key] || ''} onChange={e => update(key, e.target.value)} /></label>)}</div>;
    return compact ? <LearningSettingsAccordion key={group} title={t(`elearning.ui.${group}`)} icon={programmeIcons[group]} description={t(`elearning.programmes.section_help.${group}`)} group="elearning-programme-settings" defaultOpen={expandedGroup ? group === expandedGroup : group === 'commerce_settings'}>{content}</LearningSettingsAccordion>
      : <section className="settings-card" key={group}><h3>{t(`elearning.ui.${group}`)}</h3>{content}{group === 'notifications' && <p>{t("elearning.settings_nav.notifications_help")} <a href="/notifications">{t("elearning.settings_nav.web_notifications")}</a></p>}</section>;
  })}</>;
}

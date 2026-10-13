import { AcademyLearningPerformance, AcademyFinanceSummary, AcademyRecentActivity } from "./AcademyOverviewSections";
import { EduHopeAdminCharts, EduHopeSettingsSummary } from "./EduHopeAdminPanels";
import { useLearningExperience } from "./LearningExperienceContext";
import { Users, UserCheck, BookOpen, Award, Handshake, GraduationCap, ShoppingBag, Plus, FilePlus2, PanelsTopLeft, ChartNoAxesCombined, Gift, Settings2, Globe, Wallet, ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import useAcademyCapabilities from "../../hooks/useAcademyCapabilities";
import { academyOwnerApi } from "./academyOwnerApi";
import { OwnerHeader, OwnerPage, OwnerState } from "./OwnerUI";
const metricIcons = {
  total_learners: Users,
  active_learners: UserCheck,
  enrollments: BookOpen,
  certificates: Award,
  affiliates: Handshake,
  support_eligible: GraduationCap,
  purchases: ShoppingBag,
};

export default function AcademyOwnerOverview({
  user
}) {
  const {
      t,
      i18n
    } = useTranslation('dashboard'),
    label = k => t(`elearning.owner.${k}`),
    access = useAcademyCapabilities(user),
    // EduHope admin additions are opt-in per academy (academyExperience.studentDashboard).
    enhanced = useLearningExperience()?.studentDashboard === true;
  const caps = access?.capabilities || {};
  const flags = access?.programme_flags || {};
  const programmeSettings = section => `/e-learning/settings?tab=programmes&section=${section}`;
  const actionGroups = [
    ['learning', t('elearning.ui.learning_group'), [
      [true, t('elearning.ui.create_course'), Plus, '/e-learning/courses?create=true'],
      [caps.forms, t('elearning.forms.create'), FilePlus2, '/e-learning/forms/new'],
      [caps.reports, t('elearning.programmes.reports'), ChartNoAxesCombined, '/e-learning/reports'],
    ]],
    ['website', t('elearning.ui.website_group'), [
      [caps.contact, t('elearning.ui.edit_website'), PanelsTopLeft, '/e-learning/landing-page'],
      [access?.academy?.subdomain, t('elearning.ui.view_academy_website'), ExternalLink, `/academy/${encodeURIComponent(access?.academy?.subdomain || '')}`, true],
    ]],
    ['programmes', t('elearning.settings_nav.programmes'), [
      [caps.affiliate || caps.tuition || caps.exchange, t('elearning.ui.commerce_settings'), Settings2, programmeSettings('commerce_settings')],
      [caps.affiliate, t('elearning.ui.affiliate_settings'), Handshake, flags.affiliate ? '/e-learning/programmes/affiliate' : programmeSettings('affiliate_settings')],
      [caps.tuition, access?.support_programme_name || t('elearning.ui.support_settings'), GraduationCap, flags.tuition ? '/e-learning/programmes/tuition' : programmeSettings('support_settings')],
      [caps.exchange, access?.exchange_programme_name || t('elearning.ui.exchange_settings'), Globe, flags.exchange ? '/e-learning/exchange-opportunities' : programmeSettings('exchange_settings')],
    ]],
    ['finance', t('elearning.programmes.finance'), [
      [caps.rewards, t('elearning.referrals.settings'), Gift, '/e-learning/finance/rewards'],
      [caps.withdrawal, t('elearning.ui.withdrawal_settings'), Wallet, '/e-learning/finance/withdrawals'],
    ]],
  ];
  const [data, setData] = useState(null),
    [error, setError] = useState(false),
    [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    academyOwnerApi('/dashboard').then(v => {
      if (active) {
        setData(v);
        setError(false);
      }
    }).catch(() => {
      if (active) setError(true);
    });
    return () => {
      active = false;
    };
  }, [attempt]);
  return <OwnerPage><OwnerHeader showBreadcrumb={false} title={label('overview')} description={t('elearning.ui.overview_help')} /><OwnerState error={error} retry={() => { setError(false); setAttempt(v => v + 1); }} loading={!data && !error} />{data && <><nav className="user-dashboard-quick-actions academy-overview-shortcuts" aria-label={t('elearning.ui.quick_actions')}>
      {actionGroups.map(([key, title, items]) => {
        const visible = items.filter(([allowed]) => allowed);
        return visible.length > 0 && <div className="academy-overview-action-group" role="group" aria-labelledby={`academy-actions-${key}`} key={key}>
          <h2 id={`academy-actions-${key}`}>{title}</h2>
          <div className="academy-overview-action-links">{visible.map(([, name, Icon, path, external]) => <Link key={path} to={path} target={external ? '_blank' : undefined} rel={external ? 'noopener noreferrer' : undefined}><Icon size={18} aria-hidden="true" /><span>{name}</span></Link>)}</div>
        </div>;
      })}
    </nav><section className="user-dashboard-metrics-grid" aria-label={t('elearning.ui.learning_summary')}>
      {Object.entries(metricIcons).filter(([key]) => data[key] != null).map(([key, Icon]) => <article className="user-dashboard-metric-card" key={key}>
        <div className="user-dashboard-metric-heading">
          <span className="user-dashboard-metric-icon" aria-hidden="true"><Icon size={21} /></span>
          <span className="user-dashboard-metric-label">{label(key)}</span>
        </div>
        <div><strong className="user-dashboard-metric-value">{Number(data[key]).toLocaleString(i18n.language)}</strong>
          <p className="user-dashboard-metric-note">{t(`elearning.owner.metric_notes.${key}`)}</p>
        </div>
      </article>)}
    </section>{enhanced && <EduHopeAdminCharts data={data} />}{enhanced && <EduHopeSettingsSummary />}{data.progress && <AcademyLearningPerformance progress={data.progress} />}
    <AcademyFinanceSummary data={data} capabilities={access?.capabilities} />
    <AcademyRecentActivity events={data.recent_activity} canReport={Boolean(data.progress)} />
    {data.applications?.length > 0 && <section className="elearning-owner-section"><h2>{t('elearning.owner.applications')}</h2>{data.applications.map(row => <p key={`${row.kind}:${row.status}`}>{t(`elearning.programmes.${row.kind}`)} · {t(`elearning.programmes.${row.status}`)}: {row.count}</p>)}</section>}</>}</OwnerPage>;
}

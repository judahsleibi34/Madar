import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import useAcademyCapabilities from "../../hooks/useAcademyCapabilities";
import { academyOwnerApi } from "./academyOwnerApi";
import { OwnerHeader, OwnerPage, OwnerState } from "./OwnerUI";
export default function AcademyOwnerOverview({
  user
}) {
  const {
      t,
      i18n
    } = useTranslation('dashboard'),
    label = k => t(`elearning.owner.${k}`),
    access = useAcademyCapabilities(user);
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
  return <OwnerPage><OwnerHeader title={label('overview')} description={t('elearning.ui.overview_help')} /><OwnerState error={error} retry={() => setAttempt(v => v + 1)} loading={!data && !error} />{data && <><div className="elearning-owner-metrics">{['total_learners', 'active_learners', 'enrollments', 'certificates', 'affiliates', 'support_eligible', 'purchases'].filter(k => data[k] != null).map(k => <article className="ecommerce-list-card" key={k}><h3>{label(k)}</h3><strong>{data[k]}</strong></article>)}</div><section className="elearning-owner-section"><h2>{t('elearning.ui.quick_actions')}</h2><div className="elearning-course-actions"><Link className="ecommerce-primary-button" to="/e-learning/courses?create=true">{t('elearning.ui.create_course')}</Link>{access?.capabilities.forms && <Link className="ecommerce-secondary-button" to="/e-learning/forms/new">{t('elearning.forms.create')}</Link>}{access?.capabilities.contact && <Link className="ecommerce-secondary-button" to="/e-learning/landing-page">{t('elearning.ui.edit_website')}</Link>}{access?.capabilities.reports && <Link className="ecommerce-secondary-button" to="/e-learning/reports">{t('elearning.programmes.reports')}</Link>}</div></section>{data.progress && <section className="elearning-owner-section"><h2>{t('elearning.ui.learning_summary')}</h2><p>{label('completed_courses')}: {data.progress.completed_courses}</p><label>{label('pass_rate')}: {data.progress.pass_rate}%<progress max={100} value={data.progress.pass_rate} /></label></section>}<div className="elearning-course-grid">{['revenue', 'rewards', 'wallets', 'withdrawals'].filter(k => data[k]?.length).map(k => <section className="ecommerce-list-card" key={k}><h2>{label(k)}</h2>{data[k].map((row, index) => <p key={index}>{row.currency} · {t(`elearning.programmes.${row.status}`, {
              defaultValue: ''
            })} · {row.amount ?? row.available}{row.pending != null && ` (${label('pending')}: ${row.pending})`}</p>)}</section>)}</div><section className="elearning-owner-section"><h2>{label('recent_activity')}</h2>{!data.recent_activity?.length && <p>{t('elearning.ui.no_activity')}</p>}<ul className="elearning-owner-activity">{data.recent_activity?.map((row, index) => <li key={index}><span>{t(`elearning.ui.events.${row.event_type}`, {
                defaultValue: t('elearning.ui.academy_activity')
              })}</span><time dateTime={row.created_at}>{new Date(row.created_at).toLocaleString(i18n.language)}</time></li>)}</ul></section>{data.applications?.length > 0 && <section className="elearning-owner-section"><h2>{t('elearning.owner.applications')}</h2>{data.applications.map(row => <p key={`${row.kind}:${row.status}`}>{t(`elearning.programmes.${row.kind}`)} · {t(`elearning.programmes.${row.status}`)}: {row.count}</p>)}</section>}</>}</OwnerPage>;
}

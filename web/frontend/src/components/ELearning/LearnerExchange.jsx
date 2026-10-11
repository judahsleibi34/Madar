import {useEffect, useState} from "react";
import {Link, useParams} from "react-router-dom";
import {useTranslation} from "react-i18next";
import {academyOwnerApi} from "./academyOwnerApi";
import LearningFormRenderer from "./LearningFormRenderer";

export default function LearnerExchange({detail = false}) {
  const {opportunityId} = useParams(), {t, i18n} = useTranslation('dashboard');
  const label = key => t(`elearning.exchange.${key}`);
  const [data, setData] = useState(null), [error, setError] = useState(false), [attempt, setAttempt] = useState(0), [applying, setApplying] = useState(false);
  useEffect(() => {
    let active = true;
    academyOwnerApi(detail ? `/exchange/opportunities/${opportunityId}` : '/exchange/available/for-me').then(value => {if (active) {setData(value);setError(false);}}).catch(() => {if (active) setError(true);});
    return () => {active = false;};
  }, [detail, opportunityId, attempt]);
  const row = data?.opportunity;
  return <section dir={i18n.dir()} className="elearning-learner-dashboard">
    <header className="ecommerce-page-header"><h1>{row?.title || label('opportunities')}</h1>{detail && <Link to="/my-learning/exchange">{label('opportunities')}</Link>}</header>
    {error && <div role="alert"><p>{label('unavailable')}</p><button className="ecommerce-secondary-button" onClick={() => setAttempt(value => value + 1)}>{t('elearning.retry')}</button></div>}
    {!data && !error && <p role="status">{t('elearning.loading')}</p>}
    {!detail && data && <div className="elearning-course-grid">{data.items.map(item => <article className="ecommerce-list-card" key={item.id}><h2>{item.title}</h2><p>{item.short_description}</p><p>{item.host_institution} · {item.location}</p><Link className="ecommerce-primary-button" to={`/my-learning/exchange/${item.id}`}>{label('view_opportunity')}</Link></article>)}{!data.items.length && <p>{label('empty')}</p>}</div>}
    {row && <><article className="ecommerce-list-card"><p style={{whiteSpace:'pre-wrap'}}>{row.description}</p><dl>{['host_institution','location','start_date','end_date','deadline','requirements','capacity'].filter(key => row[key] != null && row[key] !== '').map(key => <div key={key}><dt>{t(`elearning.owner.${key}`)}</dt><dd dir="auto" style={{whiteSpace:'pre-wrap'}}>{key === 'deadline' ? new Date(row[key]).toLocaleString(i18n.language) : row[key]}</dd></div>)}</dl><p>{label('capacity_help')}</p>{data.application && <p role="status">{t(`elearning.programmes.${data.application.decision?.status || 'submitted'}`)}</p>}{data.can_apply && !applying && <button className="ecommerce-primary-button" onClick={() => setApplying(true)}>{label('apply')}</button>}</article>
    {applying && data.form && <div className="ecommerce-list-card"><LearningFormRenderer key={row.id} form={data.form} submissionPath={`/elearning/owner/exchange/opportunities/${row.id}/responses`} /></div>}</>}
  </section>;
}

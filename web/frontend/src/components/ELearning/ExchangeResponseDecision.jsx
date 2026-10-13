import LearningErrorNotice from "./LearningErrorNotice";
import {useState} from "react";
import {useTranslation} from "react-i18next";
import {academyOwnerApi} from "./academyOwnerApi";
import {OwnerStatus, OwnerTable} from "./OwnerUI";
export default function ExchangeResponseDecision({context, responseId, onChanged}) {
  const {t, i18n} = useTranslation('dashboard');
  const [status,setStatus] = useState(context.decision?.status === 'under_review' ? 'approved' : 'under_review'), [note,setNote] = useState(''), [busy,setBusy] = useState(false), [error,setError] = useState(false);
  const decision = context.decision;
  async function save(event) {
    event.preventDefault();setBusy(true);setError(false);
    try {await academyOwnerApi(`/exchange/responses/${responseId}/decision`,{method:'PUT',body:{status,note,revision:decision.revision}});setNote('');onChanged();} catch {setError(true);} finally {setBusy(false);}
  }
  return <section className="elearning-owner-section"><h2>{context.title}</h2><p>{t('elearning.exchange.capacity_help')}</p>{decision && <OwnerStatus value={decision.status}>{t(`elearning.programmes.${decision.status}`)}</OwnerStatus>}{error && <LearningErrorNotice as="p">{t('elearning.exchange.review_error')}</LearningErrorNotice>}{decision && ['submitted','under_review'].includes(decision.status) && <form className="elearning-course-form" onSubmit={save}><label>{t('elearning.owner.status')}<select value={status} onChange={event => setStatus(event.target.value)}>{['under_review','approved','not_approved'].filter(value => value !== decision.status).map(value => <option key={value} value={value}>{t(`elearning.programmes.${value}`)}</option>)}</select></label><label>{t('elearning.programmes.note')}<textarea required maxLength={4000} dir="auto" value={note} onChange={event => setNote(event.target.value)}/></label><button className="ecommerce-primary-button" disabled={busy}>{t('elearning.save')}</button></form>}<OwnerTable caption={t('elearning.programmes.history')} columns={[t('elearning.owner.status'),t('elearning.programmes.note'),t('elearning.ui.submitted')]}>{context.history.map((entry,index) => <tr key={index}><td>{t(`elearning.programmes.${entry.new_status}`)}</td><td dir="auto">{entry.note}</td><td>{new Date(entry.created_at).toLocaleString(i18n.language)}</td></tr>)}</OwnerTable></section>;
}

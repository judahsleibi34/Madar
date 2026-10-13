import {useEffect, useState} from 'react';
import LearningFormDecision from './LearningFormDecision';
import {useTranslation} from 'react-i18next';
import {learningFormsApi} from './learningFormsApi';
import {OwnerState} from './OwnerUI';

// Keyed by tenant and selected response by the caller; metadata is never inferred from answers.
export default function LearningSubmissionReview({responseId, onSaved}) {
  const {t} = useTranslation('dashboard'), label = key => t(`elearning.forms.${key}`);
  const [data,setData] = useState(null), [notes,setNotes] = useState(''), [error,setError] = useState(false), [busy,setBusy] = useState(false), [attempt,setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    learningFormsApi(`/responses/${responseId}`).then(value => {if(active){setData(value);setNotes(value.owner_notes || '');setError(false);}}).catch(() => {if(active)setError(true);});
    return () => {active = false;};
  },[responseId,attempt]);
  async function save(read) {
    setBusy(true);setError(false);
    try {
      await learningFormsApi(`/responses/${responseId}`,{method:'PUT',body:{read,owner_notes:notes}});
      window.dispatchEvent(new Event('learning-forms-changed'));
      onSaved();
    } catch {setError(true);} finally {setBusy(false);}
  }
  return <section className="learning-response-review"><OwnerState loading={!data && !error} error={error} retry={() => { setError(false); setAttempt(value => value+1); }}/>{data?.review && <LearningFormDecision key={`${responseId}:${data.review.revision}`} response={data} onChanged={()=>{setAttempt(value=>value+1);onSaved();}} />}{data && <form onSubmit={event => {event.preventDefault();void save(Boolean(data.read_at));}}><label>{label('notes')}<textarea dir="auto" maxLength={4000} value={notes} onChange={event => setNotes(event.target.value)} /></label><div className="responses-browser-actions"><button type="submit" disabled={busy}>{t('elearning.save')}</button><button type="button" disabled={busy} onClick={() => save(!data.read_at)}>{label(data.read_at ? 'mark_unread' : 'mark_read')}</button></div></form>}</section>;
}

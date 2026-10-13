import LearningFormDecision from "./LearningFormDecision";
import ExchangeResponseDecision from "./ExchangeResponseDecision";
import { useEffect, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { learningFormsApi } from "./learningFormsApi";
import { OwnerHeader, OwnerPage, OwnerState, OwnerStatus, OwnerTable } from "./OwnerUI";
import {SubmissionAnswer} from "./LearningFormSubmissionTables";
import {submissionFields} from "./learningFormSubmissionData";
export default function LearningFormResponseDetail() {
  const {
      responseId
    } = useParams(),
    location = useLocation(),
    {
      t,
      i18n
    } = useTranslation('dashboard'),
    label = k => t(`elearning.forms.${k}`);
  const [data, setData] = useState(null),
    [notes, setNotes] = useState(''),
    [error, setError] = useState(false),
    [busy, setBusy] = useState(false),
    [attempt, setAttempt] = useState(0),
    [saved, setSaved] = useState(false);
  useEffect(() => {
    let active = true;
    learningFormsApi(`/responses/${responseId}`).then(v => {
      if (active) {
        setData(v);
        setNotes(v.owner_notes || '');
        setError(false);
      }
    }).catch(() => {
      if (active) setError(true);
    });
    return () => {
      active = false;
    };
  }, [responseId, attempt]);
  async function save(read) {
    setBusy(true);
    setError(false);
    try {
      await learningFormsApi(`/responses/${responseId}`, {
        method: 'PUT',
        body: {
          read,
          owner_notes: notes
        }
      });
      setSaved(true);
      setData({
        ...data,
        owner_notes: notes,
        read_at: read ? new Date().toISOString() : null
      });
      window.dispatchEvent(new Event('learning-forms-changed'));
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }
  const fields = submissionFields(data?.definition?.schema);
  const answers = fields.filter(field => field.type !== 'file' && Object.hasOwn(data?.answers || {}, field.id));
  const files = data?.files || [];
  return <OwnerPage><OwnerHeader title={t('elearning.ui.response')} description={data?.definition.schema.title} back={{to: `/e-learning/forms/responses${location.search}`, label: label('all_responses')}} actions={data && <button className="ecommerce-secondary-button" disabled={busy} onClick={() => save(!data.read_at)}>{label(data.read_at ? 'mark_unread' : 'mark_read')}</button>}/>
    <OwnerState error={error} retry={() => { setError(false); setAttempt(value => value + 1); }} loading={!data && !error}/>{saved && <p role="status">{t('elearning.saved')}</p>}
    {data && <div className="elearning-owner-detail elearning-submission-detail">
      {data.review && <LearningFormDecision key={`${data.id}:${data.review.revision}`} response={data} onChanged={() => setAttempt(value => value + 1)} />}
      {data.exchange && <ExchangeResponseDecision key={`${data.id}:${data.exchange.decision?.revision}`} context={data.exchange} responseId={data.id} onChanged={() => setAttempt(value => value + 1)} />}
      <section className="elearning-submission-table-section"><h2>{t('elearning.ui.submitter')}</h2>
        <OwnerTable caption={t('elearning.ui.submitter')} columns={[label('identity'), t('elearning.ui.submitted'), label('version'), label('status')]}><tr><td>{data.user_id ? t('elearning.ui.member') : label('guest')}</td><td>{new Date(data.submitted_at).toLocaleString(i18n.language)}</td><td>{label('version')} {data.version}</td><td><OwnerStatus value={data.read_at ? 'read' : 'unread'}>{label(data.read_at ? 'read' : 'unread')}</OwnerStatus></td></tr></OwnerTable>
      </section>
      <section className="elearning-submission-table-section"><h2>{t('elearning.ui.answers')}</h2>
        <OwnerTable caption={t('elearning.ui.answers')} columns={[label('answer_field'),label('answer_value')]}>{answers.map(field => <tr key={field.id}><th scope="row">{field.label}</th><td><SubmissionAnswer field={field} value={data.answers[field.id]} responseId={data.id} onError={() => setError(true)}/></td></tr>)}{!answers.length && <tr><td colSpan={2}>{label('no_answers')}</td></tr>}</OwnerTable>
      </section>
      <section className="elearning-submission-table-section"><h2>{t('elearning.owner.documents')}</h2>
        <OwnerTable caption={t('elearning.owner.documents')} columns={[label('answer_field'),label('file'),label('file_size'),t('elearning.ui.actions')]}>{files.map(file => <tr key={file.id}><th scope="row">{fields.find(field => field.id === file.field_id)?.label || label('file')}</th><td dir="auto">{file.filename}</td><td>{Math.ceil(file.size_bytes / 1024)} KB</td><td><button type="button" className="ecommerce-secondary-button elearning-submission-download" aria-label={`${label('download_file')}: ${file.filename}`} onClick={() => learningFormsApi(`/responses/${data.id}/files/${file.id}`, {download:file.filename}).catch(() => setError(true))}>{label('download_file')}</button></td></tr>)}{!files.length && <tr><td colSpan={4}>{t('elearning.ui.no_documents')}</td></tr>}</OwnerTable>
      </section>
      <form className="elearning-owner-section elearning-course-form" onSubmit={event => {event.preventDefault(); void save(Boolean(data.read_at));}}><h2>{label('notes')}</h2><label>{label('notes')}<textarea dir="auto" maxLength={4000} value={notes} onChange={event => {setNotes(event.target.value); setSaved(false);}}/></label><button className="ecommerce-primary-button" disabled={busy}>{t('elearning.save')}</button></form>
    </div>}
  </OwnerPage>;
}

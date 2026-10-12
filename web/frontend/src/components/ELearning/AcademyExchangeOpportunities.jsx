import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { academyOwnerApi } from "./academyOwnerApi";
import { OwnerHeader, OwnerPage, OwnerState, OwnerStatus, OwnerTable, OwnerPagination } from "./OwnerUI";
import { learningFormsApi } from "./learningFormsApi";
const initial = {
  application_form_id: "",
  title: '',
  short_description: '',
  description: '',
  host_institution: '',
  location: '',
  start_date: '',
  end_date: '',
  deadline: '',
  requirements: '',
  capacity: '',
  status: 'draft'
};
export default function AcademyExchangeOpportunities({
  editing = false
}) {
  const {
      id
    } = useParams(),
    navigate = useNavigate(),
    {
      t,
      i18n
    } = useTranslation('dashboard'),
    label = k => t(`elearning.owner.${k}`);
  const location = useLocation();
  const formReturn = id ? `/e-learning/exchange-opportunities/${id}/edit` : '/e-learning/exchange-opportunities/new';
  const [forms, setForms] = useState(null);
  const [formsError, setFormsError] = useState(false);
  const [items, setItems] = useState(null),
    [draft, setDraft] = useState(() => ({...initial,...location.state?.exchangeDraft, ...(location.state?.selectedForm ? {application_form_id:location.state.selectedForm} : {})})),
    [error, setError] = useState(false),
    [busy, setBusy] = useState(false),
    [attempt, setAttempt] = useState(0),
    [page, setPage] = useState(0),
    [loaded, setLoaded] = useState(!id);
  useEffect(() => {
    if (!editing) return;
    let active = true;
    learningFormsApi('').then(value => {if (active) {setForms(value.items.filter(form => form.status !== 'archived'));setFormsError(false);}}).catch(() => {if (active) setFormsError(true);});
    return () => {active = false;};
  }, [editing, attempt]);
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        let offset = id ? 0 : page * 50,
          value,
          row;
        do {
          value = await academyOwnerApi(`/exchange?offset=${offset}`);
          if (!active) return;
          row = value.items.find(r => r.id === id);
          offset += 50;
        } while (id && !row && value.items.length === 50);
        if (id && !row) throw new Error();
        if (row) setDraft({
          ...initial,
          ...row,
          ...location.state?.exchangeDraft,
          ...(location.state?.selectedForm ? {application_form_id:location.state.selectedForm} : {}),
          deadline: location.state?.exchangeDraft?.deadline ?? (row.deadline ? new Date(new Date(row.deadline).getTime() - new Date(row.deadline).getTimezoneOffset() * 60000).toISOString().slice(0, 16) : '')
        });
        setLoaded(true);
        setItems(value.items);
        setError(false);
      } catch {
        if (active) setError(true);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [id, attempt, page, location.state]);
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const body = {
        ...Object.fromEntries(Object.keys(initial).map(k => [k, draft[k] ?? initial[k]])),
        application_form_id: draft.application_form_id || null,
        start_date: draft.start_date || null,
        end_date: draft.end_date || null,
        deadline: draft.deadline ? new Date(draft.deadline).toISOString() : null,
        capacity: draft.capacity ? Number(draft.capacity) : null,
        expected_revision: draft.revision || 1
      };
      await academyOwnerApi(`/exchange${id ? `/${id}` : ''}`, {
        method: id ? 'PUT' : 'POST',
        body
      });
      navigate('/e-learning/exchange-opportunities');
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }
  const create = <Link className="ecommerce-primary-button" to="/e-learning/exchange-opportunities/new">{t('elearning.ui.create_opportunity')}</Link>;
  return <OwnerPage><OwnerHeader title={editing ? t(`elearning.ui.${id ? 'edit_opportunity' : 'create_opportunity'}`) : label('opportunities')} description={t('elearning.ui.opportunities_help')} back={editing ? {
      to: '/e-learning/exchange-opportunities',
      label: label('opportunities')
    } : null} actions={!editing && <>{create}<Link className="ecommerce-secondary-button" to="/e-learning/programmes/exchange">{t('elearning.exchange.legacy')}</Link></>} /><OwnerState error={error} retry={() => setAttempt(v => v + 1)} loading={(!items || !loaded) && !error} empty={!editing && items && !items.length && t('elearning.ui.no_opportunities')} action={create} />
 {!editing && items?.length > 0 && <OwnerTable caption={label('opportunities')} columns={[label('title'), label('status'), label('start_date'), label('deadline'), label('capacity'), t('elearning.ui.actions')]}>{items.map(row => <tr key={row.id}><td>{row.title}<p>{row.host_institution} · {row.location}</p></td><td><OwnerStatus value={row.status}>{label(row.status)}</OwnerStatus></td><td>{row.start_date || '—'}{row.end_date && ` – ${row.end_date}`}</td><td>{row.deadline ? new Date(row.deadline).toLocaleDateString(i18n.language) : '—'}</td><td>{row.capacity ?? '—'}</td><td><div className="elearning-course-actions"><Link className="ecommerce-secondary-button" to={`/e-learning/exchange-opportunities/${row.id}/edit`}>{label('edit')}</Link><Link className="ecommerce-secondary-button" to={row.application_form_id ? `/e-learning/forms/responses?form_id=${row.application_form_id}&opportunity_id=${row.id}` : `/e-learning/programmes/exchange?opportunity_id=${row.id}`}>{row.application_form_id ? label('applications') : t('elearning.exchange.legacy')}</Link></div></td></tr>)}</OwnerTable>}{!editing && items && <OwnerPagination page={page} setPage={setPage} more={items.length === 50} />}
 {editing && loaded && <form className="elearning-course-form" onSubmit={save}><fieldset disabled={busy} className="elearning-course-form"><div className="settings-form-grid">{Object.keys(initial).filter(k => !['status','application_form_id'].includes(k)).map(k => <label key={k}>{label(k)}{['description', 'requirements', 'short_description'].includes(k) ? <textarea dir="auto" maxLength={k === 'description' ? 12000 : k === 'short_description' ? 1200 : 8000} value={draft[k] || ''} onChange={e => setDraft({
              ...draft,
              [k]: e.target.value
            })} /> : <input required={k === 'title'} maxLength={k === 'title' ? 160 : 200} type={k === 'capacity' ? 'number' : k === 'deadline' ? 'datetime-local' : k.endsWith('date') ? 'date' : 'text'} min={k === 'capacity' ? 1 : undefined} value={draft[k] || ''} onChange={e => setDraft({
              ...draft,
              [k]: e.target.value
            })} />}</label>)}</div><section className="elearning-owner-section"><h2>{t('elearning.exchange.application_form')}</h2>{formsError && <p role="alert">{t('elearning.exchange.forms_unavailable')}</p>}{forms && !forms.length && <p>{t('elearning.exchange.no_forms')}</p>}<label>{t('elearning.exchange.application_form')}<select required={draft.status === 'published'} value={draft.application_form_id || ''} onChange={event => setDraft({...draft,application_form_id:event.target.value})}><option value="">{t('elearning.forms.select')}</option>{forms?.map(form => <option key={form.id} value={form.id}>{form.name} · {t(`elearning.forms.${form.status}`)}</option>)}</select></label><div className="elearning-course-actions"><Link className="ecommerce-secondary-button" to={`/e-learning/forms/new?returnTo=${encodeURIComponent(formReturn)}`} state={{exchangeDraft:draft}}>{t('elearning.forms.create')}</Link>{draft.application_form_id && <Link className="ecommerce-secondary-button" to={`/e-learning/forms/${draft.application_form_id}/edit?returnTo=${encodeURIComponent(formReturn)}`} state={{exchangeDraft:draft}}>{t('elearning.exchange.edit_form')}</Link>}</div><p>{t('elearning.exchange.capacity_help')}</p></section><label>{label('status')}<select value={draft.status} onChange={e => setDraft({
            ...draft,
            status: e.target.value
          })}>{['draft', 'published', 'closed', 'archived'].map(v => <option key={v} value={v}>{label(v)}</option>)}</select></label><div className="elearning-course-actions"><button className="ecommerce-primary-button">{t('elearning.save')}</button><Link className="ecommerce-secondary-button" to="/e-learning/exchange-opportunities">{t('elearning.ui.cancel')}</Link></div></fieldset></form>}</OwnerPage>;
}

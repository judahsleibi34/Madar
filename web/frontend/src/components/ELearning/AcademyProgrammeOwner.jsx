import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { request } from "./academyProgrammeApi";
import AcademySupportDocuments from "./AcademySupportDocuments";
import { OwnerHeader, OwnerPage, OwnerState, OwnerStatus, OwnerTable, OwnerPagination } from "./OwnerUI";
const transitions = row => row.payment_method ? {
  pending: ['approved', 'rejected'],
  approved: ['processing', 'rejected'],
  processing: ['paid', 'rejected']
}[row.status] || [] : {
  submitted: ['under_review', 'approved', 'not_approved'],
  under_review: ['approved', 'not_approved'],
  approved: row.kind === 'affiliate' ? ['suspended'] : [],
  suspended: row.kind === 'affiliate' ? ['approved'] : []
}[row.status] || [];
export default function AcademyProgrammeOwner({
  kind = 'affiliate',
  responseId,
  directory = false,
  memberId
}) {
  const params = useParams(),
    identifier = responseId || params.applicationId,
    {
      t,
      i18n
    } = useTranslation('dashboard'),
    label = k => t(`elearning.programmes.${k}`),
    location = useLocation();
  const [data, setData] = useState(null),
    [selected, setSelected] = useState(null),
    [profile, setProfile] = useState(null),
    [error, setError] = useState(false),
    [busy, setBusy] = useState(false),
    [revision, setRevision] = useState(0),
    [status, setStatus] = useState(directory ? 'approved' : ''),
    [query, setQuery] = useState(''),
    [page, setPage] = useState(0),
    [saved, setSaved] = useState(false);
  const base = kind === 'withdrawal' ? '/e-learning/finance/withdrawals' : `/e-learning/programmes/${kind}`;
  useEffect(() => {
    let active = true;
    const type = kind === 'withdrawal' ? 'withdrawal' : 'application';
    const opportunity = new URLSearchParams(location.search).get('opportunity_id');
    const filters = `${kind === 'withdrawal' ? '' : `&kind=${kind}`}${status ? `&status=${status}` : ''}${opportunity ? `&opportunity_id=${encodeURIComponent(opportunity)}` : ''}`;
    async function load() {
      try {
        if (memberId) {
          const value = await request(`/management/members/${memberId}`);
          if (active) {
            setProfile(value);
            setData({
              items: []
            });
            setError(false);
          }
          return;
        }
        let result;
        let row;
        let offset = identifier ? 0 : page * 50;
        do {
          result = await request(`/management/${type}?limit=50&offset=${offset}${filters}`);
          if (!active) return;
          row = result.items.find(r => r.id === identifier);
          offset += 50;
        } while (identifier && !row && result.items.length === 50);
        if (identifier && !row) throw new Error();
        setData(result);
        setSelected(row || null);
        setError(false);
        if (row && result.capabilities?.wallet) {
          try {
            const member = await request(`/management/members/${row.user_id}`);
            if (active) setProfile(member);
          } catch {/* Optional wallet detail does not block application review. */}
        }
      } catch (failure) {
        if (active) setError(failure.code || true);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [kind, identifier, memberId, status, page, location.search, revision]);
  async function review(e) {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    try {
      await request(`/management/${kind === 'withdrawal' ? 'withdrawal' : 'application'}/${selected.id}/review`, {
        status: values.status,
        revision: selected.revision,
        note: values.note
      });
      setSaved(true);
      setRevision(v => v + 1);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }
  const title = kind === 'tuition' ? data?.settings?.support_programme_name || label('support') : kind === 'exchange' ? data?.settings?.exchange_programme_name || label('exchange') : label(kind);
  const rows = (data?.items || []).filter(r => !query || `${r.details?.full_name || ''} ${r.details?.email || ''}`.toLowerCase().includes(query.toLowerCase()));
  return <OwnerPage><OwnerHeader title={memberId ? t('elearning.ui.affiliate_detail') : identifier ? label('review') : title} description={kind === 'exchange' ? t('elearning.exchange.legacy_help') : t(`elearning.ui.${identifier ? 'application_detail_help' : kind === 'withdrawal' ? 'withdrawals_help' : 'applications_help'}`)} back={identifier || memberId ? {
      to: memberId ? '/e-learning/affiliates' : base,
      label: title
    } : null} actions={!identifier && !memberId && kind === 'exchange' && <Link className="ecommerce-secondary-button" to="/e-learning/exchange-opportunities">{t('elearning.owner.opportunities')}</Link>} />
 {kind === 'affiliate' && !identifier && !memberId && <nav className="elearning-course-tabs"><Link to="/e-learning/programmes/affiliate" className={`ecommerce-secondary-button ${!directory ? 'active' : ''}`}>{t('elearning.owner.applications')}</Link><Link to="/e-learning/affiliates" className={`ecommerce-secondary-button ${directory ? 'active' : ''}`}>{label('affiliate')}</Link></nav>}
 <OwnerState message={error==='academy_programmes_disabled'?t('elearning.ui.programme_disabled'):undefined} error={error} retry={() => setRevision(v => v + 1)} loading={!data && !error} />{error && <Link className="ecommerce-secondary-button" to="/e-learning/settings">{label("settings")}</Link>}{saved && <p role="status">{label('saved')}</p>}
 {!identifier && !memberId && <><div className="elearning-owner-filters"><label>{label('search')}<input value={query} onChange={e => setQuery(e.target.value)} /></label>{<label>{label('status')}<select value={status} onChange={e => {
            setStatus(e.target.value);
            setPage(0);
          }}>{!directory&&<option value="">{label('all')}</option>}{(directory?['approved','suspended']:kind === 'withdrawal' ? ['pending', 'approved', 'processing', 'paid', 'rejected'] : ['submitted', 'under_review', 'approved', 'not_approved', 'suspended']).map(v => <option value={v} key={v}>{label(v)}</option>)}</select></label>}</div><OwnerState empty={data && !rows.length && t('elearning.ui.no_applications')} />{rows.length > 0 && <OwnerTable caption={title} columns={[t('elearning.ui.applicant'), label('status'), t('elearning.ui.submitted'), t('elearning.ui.actions')]}>{rows.map(row => <tr key={row.id}><td>{row.details?.full_name || t('elearning.ui.member')}{row.amount && <p>{row.amount} {row.currency}</p>}</td><td><OwnerStatus value={row.status}>{label(row.status)}</OwnerStatus></td><td>{new Date(row.created_at).toLocaleString(i18n.language)}</td><td><Link className="ecommerce-secondary-button" to={directory ? `/e-learning/affiliates/members/${row.user_id}` : row.learning_form_response_id ? `/e-learning/forms/responses/${row.learning_form_response_id}` : `${base}/${row.id}${location.search}`}>{directory ? t('elearning.ui.open') : label('review')}</Link></td></tr>)}</OwnerTable>}{data && <OwnerPagination page={page} setPage={setPage} more={data.items.length === 50} />}</>}
 {identifier && selected?.learning_form_response_id && <Link className="ecommerce-primary-button" to={`/e-learning/forms/responses/${selected.learning_form_response_id}`}>{t("elearning.forms_review.open_submission")}</Link>}
 {identifier && selected && !selected.learning_form_response_id && <div className="elearning-owner-detail"><section className="elearning-owner-section"><h2>{t('elearning.ui.applicant')}</h2><p>{selected.details?.full_name || profile?.user?.name || t('elearning.ui.member')}</p><p>{selected.details?.email || profile?.user?.email}</p><OwnerStatus value={selected.status}>{label(selected.status)}</OwnerStatus>{selected.amount && <p>{selected.amount} {selected.currency} · {selected.payment_method}</p>}</section><section className="elearning-owner-section"><h2>{t('elearning.ui.submitted_information')}</h2><dl>{Object.entries(selected.details || {}).filter(([k]) => k !== 'terms_accepted' && !k.endsWith('_id')).map(([k, v]) => <div key={k}><dt>{t(`elearning.programmes.${k}`,{defaultValue:k.replaceAll('_',' ')})}</dt><dd dir="auto">{String(v)}</dd></div>)}</dl>{selected.payment_information && <p>{selected.payment_information}</p>}</section>{profile?.wallet && <section className="elearning-owner-section"><h2>{t('elearning.ui.eligibility')}</h2><p>{label('sales')}: {profile.wallet.verified_sales}{profile.wallet.threshold != null && ` / ${profile.wallet.threshold}`}</p><p>{label('available')}: {profile.wallet.available} {profile.wallet.currency}</p></section>}{kind === 'tuition' && <AcademySupportDocuments application={selected} />}<section className="elearning-owner-section"><h2>{label('terms_accepted')}</h2><p className="elearning-owner-preserve">{selected.terms_snapshot}</p></section><section className="elearning-owner-section"><h2>{label('history')}</h2>{(profile?.history || []).filter(r => r.entity_id === selected.id).map(row => <p key={row.id}>{label(row.new_status)} · {row.note} · {new Date(row.created_at).toLocaleString(i18n.language)}</p>)}{!profile && <p>{t('elearning.ui.history_unavailable')}</p>}</section><form onSubmit={review} className="elearning-course-form elearning-owner-section"><h2>{label('review')}</h2><label>{label('status')}<select name="status" required disabled={!transitions(selected).length}>{transitions(selected).map(v => <option key={v} value={v}>{label(v)}</option>)}</select></label><label>{label('note')}<textarea dir="auto" name="note" required maxLength={4000} /></label><button className="ecommerce-primary-button" disabled={busy || !transitions(selected).length}>{label(busy ? 'saving' : 'submit')}</button></form></div>}
 {memberId && profile && <div className="elearning-owner-detail"><h2>{profile.user.name}</h2><p>{profile.user.email}</p><div className="elearning-owner-metrics">{['available', 'pending', 'total_earned', 'total_withdrawn'].filter(k => profile.wallet?.[k] != null).map(k => <article className="ecommerce-list-card" key={k}><h3>{label(k)}</h3><strong>{profile.wallet[k]} {profile.wallet.currency}</strong></article>)}</div>{['referrals', 'transactions', 'withdrawals'].map(k => <section className="elearning-owner-section" key={k}><h2>{label(k)}</h2><OwnerState empty={!profile[k]?.length && label('empty')} />{profile[k]?.length > 0 && <OwnerTable caption={label(k)} columns={[label('amount'), label('status'), t('elearning.ui.submitted')]}>{profile[k].map((row, index) => <tr key={row.id || row.event_id || index}><td>{row.amount} {row.currency}</td><td><OwnerStatus value={row.status || row.state}>{label(row.status || row.state || 'pending')}</OwnerStatus></td><td>{new Date(row.created_at).toLocaleString(i18n.language)}</td></tr>)}</OwnerTable>}<Link className="ecommerce-secondary-button" to={k === 'withdrawals' ? '/e-learning/finance/withdrawals' : `/e-learning/finance/${k}`}>{t('elearning.ui.view_all')}</Link></section>)}</div>}
 </OwnerPage>;
}

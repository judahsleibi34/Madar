import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { apiFetch, getApiUrl } from "../../utils/apiClient";
import { OwnerHeader, OwnerPage, OwnerState, OwnerStatus, OwnerTable, OwnerPagination } from "./OwnerUI";
export default function AcademyFinancePage({
  kind
}) {
  const {
      t,
      i18n
    } = useTranslation('dashboard'),
    label = k => t(`elearning.programmes.${k}`);
  const [data, setData] = useState(null),
    [error, setError] = useState(false),
    [page, setPage] = useState(0),
    [query, setQuery] = useState(''),
    [attempt, setAttempt] = useState(0),
    [names, setNames] = useState({}),
    [wallets, setWallets] = useState([]);
  const reference = new URLSearchParams(useLocation().search).get('reference');
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        let offset = reference ? 0 : page * 50;
        let result;
        const matches = [];
        do {
          const response = await apiFetch(getApiUrl(`/elearning/programmes/finance/${kind}?limit=50&offset=${offset}`));
          if (!response.ok) { const body = await response.json(); const failure = new Error(); failure.code = body.detail?.code; throw failure; }
          result = await response.json();
          if (!active) return;
          if (reference) matches.push(...result.items.filter(row => row.reference === reference));
          offset += 50;
        } while (reference && result.items.length === 50);
        setData(reference ? {items:matches} : result);
        setError(false);
      } catch (failure) { if (active) setError(failure.code || true); }
    }
    load();
    return () => { active = false; };
  }, [kind, page, attempt, reference]);
  useEffect(() => {
    if (!data) return;
    let active = true;
    if (kind === 'rewards') {
      apiFetch(getApiUrl('/elearning/owner/dashboard')).then(response=>response.ok?response.json():null).then(value=>{if(active)setWallets(value?.wallets||[]);}).catch(()=>{});
    }
    if (kind === 'referrals') {
      const missing = new Set(data.items.map(row=>row.referred_id).filter(Boolean));
      async function resolveNames() {
        const labels = {};
        let offset = 0;
        let more = true;
        while (active && more && missing.size) {
          const response = await apiFetch(getApiUrl(`/elearning/owner/students?limit=100&offset=${offset}`));
          if (!response.ok) return;
          const value = await response.json();
          if (!active) return;
          for (const learner of value.learners) {
            if (missing.has(learner.user_id)) { labels[learner.user_id]=learner.name;missing.delete(learner.user_id); }
          }
          more = value.has_more;
          offset += 100;
        }
        if(active)setNames(labels);
      }
      resolveNames().catch(()=>{});
    }
    return ()=>{active=false;};
  },[data,kind]);
  const rows = data?.items.filter(r => (!reference || r.reference === reference) && (!query || `${r.type || ''} ${r.status || ''} ${r.code || ''} ${r.amount || ''} ${r.currency || ''} ${names[r.referred_id] || ''}`.toLowerCase().includes(query.toLowerCase()))) || [];
  return <OwnerPage><OwnerHeader title={label(kind)} description={t(`elearning.ui.${kind}_help`)} />{reference&&<Link className="ecommerce-secondary-button" to="/e-learning/finance/transactions">{t('elearning.ui.view_all')}</Link>}<div className="elearning-owner-filters"><label>{label('search')}<input value={query} onChange={e => setQuery(e.target.value)} /></label></div><OwnerState message={error==='academy_programmes_disabled'?t('elearning.ui.programme_disabled'):undefined} error={error} retry={() => { setError(false); setAttempt(v => v + 1); }} loading={!data && !error} empty={data && !rows.length && label('empty')} />{wallets.length>0&&<div className="elearning-owner-metrics">{wallets.map(row=><article className="ecommerce-list-card" key={row.currency}><h3>{row.currency}</h3><p>{label('available')}: {row.available}</p><p>{label('pending')}: {row.pending}</p></article>)}</div>}{error==='academy_programmes_disabled'&&<Link className="ecommerce-secondary-button" to="/e-learning/settings">{label('settings')}</Link>}{rows.length > 0 && <OwnerTable caption={label(kind)} columns={kind === 'referrals' ? [t('elearning.ui.referral_code'), label('referredUser'), label('clicks'), label('amount'), label('status'), t('elearning.ui.submitted')] : [t('elearning.ui.entry'), label('amount'), label('status'), t('elearning.ui.submitted'), t('elearning.ui.source')]}>{rows.map(row => <tr key={row.id}><td>{kind === 'referrals' ? row.code || row.referral_code || t('elearning.ui.referral') : row.type ? label(row.type) : label(kind)}</td>{kind === 'referrals' ? <><td>{row.referred_id ? names[row.referred_id] || t('elearning.ui.member') : t('elearning.forms.guest')}</td><td>{row.clicks || 0}</td><td>{row.amount} {row.currency}</td></> : <td>{row.amount} {row.currency}</td>}<td><OwnerStatus value={row.status}>{label(row.status)}{row.simulated && ` · ${label('simulated')}`}</OwnerStatus></td><td>{new Date(row.created_at).toLocaleString(i18n.language)}</td>{kind !== 'referrals' && <td>{row.type?.startsWith('withdrawal_') && row.reference ? <Link to={`/e-learning/finance/withdrawals/${row.reference}`}>{t('elearning.programmes.withdrawal')}</Link> : row.checkout_id ? <Link to={`/e-learning/finance/transactions?reference=${encodeURIComponent(row.checkout_id)}`}>{t('elearning.ui.recorded_transaction')}</Link> : row.reference ? t('elearning.ui.recorded_transaction') : t('elearning.ui.accounting_entry')}</td>}</tr>)}</OwnerTable>}{data && !reference && <OwnerPagination page={page} setPage={setPage} more={data.items.length === 50} />}</OwnerPage>;
}

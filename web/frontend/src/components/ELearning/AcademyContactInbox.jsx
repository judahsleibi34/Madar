import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { academyOwnerApi } from "./academyOwnerApi";
import { OwnerHeader, OwnerPage, OwnerState, OwnerStatus, OwnerTable, OwnerPagination } from "./OwnerUI";
export default function AcademyContactInbox({
  detail = false
}) {
  const {
      contactId
    } = useParams(),
    {
      t,
      i18n
    } = useTranslation('dashboard'),
    label = k => t(`elearning.owner.${k}`);
  const [items, setItems] = useState(null),
    [search, setSearch] = useState(''),
    [unread, setUnread] = useState(false),
    [page, setPage] = useState(0),
    [attempt, setAttempt] = useState(0),
    [error, setError] = useState(false),
    [selected, setSelected] = useState(null);
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        let offset = detail ? 0 : page * 50,
          value,
          row;
        do {
          value = await academyOwnerApi(`/contacts?${new URLSearchParams({
            search: detail ? '' : search,
            unread: detail ? false : unread,
            offset
          })}`);
          if (!active) return;
          row = value.items.find(r => String(r.id) === contactId);
          offset += 50;
        } while (detail && !row && value.items.length === 50);
        if (detail && !row) throw new Error();
        setItems(value.items);
        setSelected(row || null);
        setError(false);
      } catch {
        if (active) setError(true);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [detail, contactId, search, unread, page, attempt]);
  async function mark(row) {
    try {
      await academyOwnerApi(`/contacts/${row.id}/read`, {
        method: 'PUT',
        body: {
          read: !row.read_at
        }
      });
      setAttempt(v => v + 1);
    } catch {
      setError(true);
    }
  }
  return <OwnerPage><OwnerHeader title={detail ? selected?.subject || label('contacts') : label('contacts')} description={t('elearning.ui.contacts_help')} back={detail ? {
      to: '/e-learning/contacts',
      label: label('contacts')
    } : null} /><OwnerState error={error} retry={() => setAttempt(v => v + 1)} loading={!items && !error} empty={!detail && items && !items.length && t('elearning.ui.no_messages')} />{!detail && <><div className="elearning-owner-filters"><label>{t('elearning.programmes.search')}<input value={search} onChange={e => {
            setSearch(e.target.value);
            setPage(0);
          }} /></label><label><input type="checkbox" checked={unread} onChange={e => {
            setUnread(e.target.checked);
            setPage(0);
          }} />{label('unread')}</label></div>{items?.length > 0 && <OwnerTable caption={label('contacts')} columns={[t('elearning.ui.submitter'), t('elearning.ui.subject'), t('elearning.ui.submitted'), t('elearning.forms.status'), t('elearning.ui.actions')]}>{items.map(row => <tr key={row.id}><td>{row.name}<p>{row.email}</p></td><td>{row.subject}</td><td>{new Date(row.created_at).toLocaleString(i18n.language)}</td><td><OwnerStatus value={row.read_at ? 'read' : 'unread'}>{t(`elearning.forms.${row.read_at ? 'read' : 'unread'}`)}</OwnerStatus></td><td><Link className="ecommerce-secondary-button" to={`/e-learning/contacts/${row.id}`}>{label('open')}</Link></td></tr>)}</OwnerTable>}{items && <OwnerPagination page={page} setPage={setPage} more={items.length === 50} />}</>}{detail && selected && <div className="elearning-owner-detail"><h2>{selected.name}</h2><p>{selected.email} · {new Date(selected.created_at).toLocaleString(i18n.language)}</p><p className="elearning-owner-preserve">{selected.message}</p><button className="ecommerce-secondary-button" onClick={() => mark(selected)}>{label(selected.read_at ? 'mark_unread' : 'mark_read')}</button></div>}</OwnerPage>;
}

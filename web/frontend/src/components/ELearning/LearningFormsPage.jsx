import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import ELearningDialog from "./ELearningDialog";
import { learningFormsApi } from "./learningFormsApi";
import { OwnerHeader, OwnerPage, OwnerState, OwnerStatus, OwnerTable } from "./OwnerUI";
export default function LearningFormsPage() {
  const {
      t,
      i18n
    } = useTranslation('dashboard'),
    label = key => t(`elearning.forms.${key}`);
  const [data, setData] = useState(null),
    [error, setError] = useState(false),
    [revision, setRevision] = useState(0),
    [busy, setBusy] = useState(false),
    [archive, setArchive] = useState(null);
  useEffect(() => {
    let active = true;
    learningFormsApi().then(value => {
      if (active) {
        setData(value);
        setError(false);
      }
    }).catch(() => {
      if (active) setError(true);
    });
    return () => {
      active = false;
    };
  }, [revision]);
  async function change(row, status) {
    setBusy(true);
    try {
      const original = await learningFormsApi(`/${row.id}`);
      await learningFormsApi(`/${row.id}`, {
        method: 'PUT',
        body: {
          name: original.name,
          status,
          expected_version: original.version,
          schema: original.schema
        }
      });
      setRevision(v => v + 1);
      setArchive(null);
      window.dispatchEvent(new Event('learning-forms-changed'));
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }
  async function duplicate(row) {
    setBusy(true);
    try {
      await learningFormsApi(`/${row.id}/duplicate`, {
        method: 'POST'
      });
      setRevision(v => v + 1);
      window.dispatchEvent(new Event('learning-forms-changed'));
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }
  const create = <Link className="ecommerce-primary-button" to="/e-learning/forms/new">{label('create')}</Link>;
  return <OwnerPage><OwnerHeader title={label('title')} description={t('elearning.ui.forms_help')} actions={create} /><OwnerState loading={!data && !error} error={error} retry={() => { setError(false); setRevision(v => v + 1); }} empty={data && !data.items.length && t('elearning.ui.no_forms')} action={create} />{data?.items.length > 0 && <OwnerTable caption={label('manage')} columns={[label('name'), label('status'), label('responses'), label('unread'), t('elearning.ui.updated'), t('elearning.ui.actions')]}>{data.items.map(row => <tr key={row.id}><td>{row.name}</td><td><OwnerStatus value={row.status}>{label(row.status)}</OwnerStatus></td><td>{row.responses}</td><td>{row.unread}</td><td>{row.updated_at ? new Date(row.updated_at).toLocaleDateString(i18n.language) : '—'}</td><td><div className="elearning-course-actions"><Link className="ecommerce-secondary-button" to={`/e-learning/forms/${row.id}/edit`}>{label('edit')}</Link><Link className="ecommerce-secondary-button" to={`/e-learning/forms/responses?form_id=${row.id}`}>{label('responses')}</Link><details><summary>{t('elearning.ui.more')}</summary><button disabled={busy} onClick={() => duplicate(row)}>{label('duplicate')}</button><button disabled={busy} onClick={() => change(row, row.status === 'active' ? 'inactive' : 'active')}>{t(`elearning.ui.${row.status === 'active' ? 'deactivate' : row.status === 'archived' ? 'restore' : 'activate'}`)}</button>{row.status !== 'archived' && <button disabled={busy} onClick={() => setArchive(row)}>{t('elearning.ui.archive')}</button>}</details></div></td></tr>)}</OwnerTable>}{archive && <ELearningDialog title={t("elearning.ui.archive")} onClose={() => setArchive(null)} busy={busy} closeLabel={t("elearning.ui.cancel")}><p>{t('elearning.ui.archive_help', {
          name: archive.name
        })}</p><footer><button className="ecommerce-secondary-button" onClick={() => setArchive(null)}>{t('elearning.ui.cancel')}</button><button className="ecommerce-primary-button" disabled={busy} onClick={() => change(archive, 'archived')}>{t('elearning.ui.archive')}</button></footer></ELearningDialog>}</OwnerPage>;
}

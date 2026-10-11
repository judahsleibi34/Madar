import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import LoadingBar from "../common/LoadingBar";
export function OwnerHeader({
  title,
  description,
  actions,
  back
}) {
  const {
    t
  } = useTranslation('dashboard');
  return <><nav className="elearning-owner-breadcrumb" aria-label={t('elearning.ui.breadcrumbs')}><Link to="/e-learning/dashboard">{t('sidebar.elearning')}</Link>{back && <><span aria-hidden="true"> / </span><Link to={back.to}>{back.label}</Link></>}</nav><header className="ecommerce-page-header app-page-intro"><div><h1>{title}</h1>{description && <p>{description}</p>}</div>{actions && <div className="elearning-course-actions">{actions}</div>}</header></>;
}
export function OwnerPage({
  children
}) {
  const {
    i18n
  } = useTranslation('dashboard');
  return <main className="ecommerce-page elearning-management elearning-owner-page" dir={i18n.dir()} lang={i18n.language}>{children}</main>;
}
export function OwnerState({
  loading,
  error,
  message,
  retry,
  empty,
  action
}) {
  const {
    t
  } = useTranslation('dashboard');
  if (error) return <div className="ecommerce-list-card" role="alert"><p>{message || t('elearning.ui.load_error')}</p>{retry && <button className="ecommerce-secondary-button" onClick={retry}>{t('elearning.retry')}</button>}</div>;
  if (loading) return <LoadingBar label={t('elearning.loading')} mode="inline" />;
  if (empty) return <section className="ecommerce-list-card ecommerce-empty-state"><h2>{empty}</h2>{action}</section>;
  return null;
}
export function OwnerStatus({
  value,
  children
}) {
  return <span className={`elearning-course-status is-${['active', 'approved', 'paid', 'published', 'read'].includes(value) ? 'published' : ['draft', 'pending', 'submitted', 'under_review', 'unread', 'processing'].includes(value) ? 'draft' : 'inactive'}`}>{children}</span>;
}
export function OwnerTable({
  columns,
  children,
  caption
}) {
  return <div className="elearning-owner-table-wrap"><table className="elearning-owner-table"><caption className="sr-only">{caption}</caption><thead><tr>{columns.map((column, index) => <th scope="col" key={`${index}:${column}`}>{column}</th>)}</tr></thead><tbody>{children}</tbody></table></div>;
}
export function OwnerPagination({
  page,
  setPage,
  more
}) {
  const {
    t
  } = useTranslation('dashboard');
  return <nav className="elearning-course-actions" aria-label={t('elearning.ui.pagination')}><button className="ecommerce-secondary-button" disabled={!page} onClick={() => setPage(page - 1)}>{t('elearning.programmes.previous')}</button><span>{t('elearning.ui.page_number', {
        number: page + 1
      })}</span><button className="ecommerce-secondary-button" disabled={!more} onClick={() => setPage(page + 1)}>{t('elearning.programmes.next')}</button></nav>;
}

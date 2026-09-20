export default function PageHeaderSkeleton({ className = "", actions = false }) {
  return (
    <header className={`page-header-skeleton ecommerce-route-skeleton-header ${className}`} aria-hidden="true">
      <div className="page-header-skeleton-copy"><i /><i /></div>
      {actions && <span className="page-header-skeleton-actions"><i /><i /></span>}
    </header>
  );
}

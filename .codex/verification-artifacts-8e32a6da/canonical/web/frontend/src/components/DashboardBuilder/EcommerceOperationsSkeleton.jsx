const placeholders = (count, className = "") => Array.from({ length: count }, (_, index) => (
  <i key={index} className={className} aria-hidden="true" />
));

export default function EcommerceOperationsSkeleton({ variant = "orders", label = "Loading" }) {
  return (
    <div className={`ecommerce-operations-skeleton is-${variant}`} role="status" aria-label={label} aria-live="polite">
      {variant === "delivery" && (
        <div className="ecommerce-skeleton-delivery-grid">
          {placeholders(8, "ecommerce-skeleton-delivery-card")}
        </div>
      )}
      {variant === "loyalty" && (
        <div className="ecommerce-skeleton-field-grid">
          {Array.from({ length: 8 }, (_, index) => <div key={index} aria-hidden="true"><i /><i /></div>)}
        </div>
      )}
      {variant === "orders" && (
        <div className="ecommerce-skeleton-order-list">
          {Array.from({ length: 5 }, (_, row) => (
            <div key={row} className="ecommerce-skeleton-order-row" aria-hidden="true">{placeholders(6)}</div>
          ))}
        </div>
      )}
      {variant === "order-detail" && (
        <>
          <div className="ecommerce-skeleton-detail-header" aria-hidden="true"><i /><i /><i /></div>
          <div className="ecommerce-skeleton-detail-grid">
            {Array.from({ length: 4 }, (_, index) => <div key={index} aria-hidden="true"><i /><i /><i /></div>)}
          </div>
          <div className="ecommerce-skeleton-detail-panel" aria-hidden="true"><i />{placeholders(3)}</div>
        </>
      )}
    </div>
  );
}

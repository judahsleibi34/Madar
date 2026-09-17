import EcommerceOperationsSkeleton from "./EcommerceOperationsSkeleton";

function HeaderSkeleton() {
  return <header className="ecommerce-route-skeleton-header" aria-hidden="true"><div><i /><i /></div><i /></header>;
}

function CatalogSkeleton({ label }) {
  return (
    <main className="ecommerce-page" role="status" aria-label={label}>
      <div className="ecommerce-page-skeleton">
        <header><div><i /><i /><i /></div><i /></header>
        <section>{Array.from({ length: 3 }, (_, index) => <i key={index} />)}</section>
        <article><header><div><i /><i /></div><i /></header>{Array.from({ length: 5 }, (_, index) => <i key={index} />)}</article>
      </div>
    </main>
  );
}

export default function EcommerceRouteSkeleton({ pathname = "", label = "Loading Online Store" }) {
  if (pathname.startsWith("/ecommerce/store")) {
    return (
      <main className="ecommerce-store-admin" role="status" aria-label={label}>
        <HeaderSkeleton />
        <div className="ecommerce-store-page-skeleton"><i /><i /><i /></div>
      </main>
    );
  }

  if (pathname.startsWith("/ecommerce/theme")) {
    return (
      <main className="ecommerce-page ecommerce-operations-page" role="status" aria-label={label}>
        <HeaderSkeleton />
        <div className="ecommerce-theme-skeleton"><i /><i /><i /><i /><i /><i /></div>
      </main>
    );
  }

  if (/^\/ecommerce\/orders\/[^/]+/.test(pathname)) {
    return <main className="ecommerce-page ecommerce-operations-page"><EcommerceOperationsSkeleton variant="order-detail" label={label} /></main>;
  }

  if (pathname.startsWith("/ecommerce/delivery") || pathname.startsWith("/ecommerce/orders") || pathname.startsWith("/ecommerce/loyalty")) {
    const variant = pathname.startsWith("/ecommerce/delivery")
      ? "delivery"
      : pathname.startsWith("/ecommerce/loyalty")
        ? "loyalty"
        : "orders";
    return (
      <main className="ecommerce-page ecommerce-operations-page">
        <HeaderSkeleton />
        <section className="ecommerce-operations-card">
          {variant !== "loyalty" && <div className="ecommerce-route-skeleton-filters" aria-hidden="true"><i /><i /><i /></div>}
          <EcommerceOperationsSkeleton variant={variant} label={label} />
        </section>
      </main>
    );
  }

  return <CatalogSkeleton label={label} />;
}

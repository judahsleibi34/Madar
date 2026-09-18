import { StorePreviewSkeleton, ProductEditorSkeleton, ThemeSkeleton, CatalogSkeleton } from "./CommerceLoadingLayouts";
import EcommerceOperationsSkeleton from "./EcommerceOperationsSkeleton";

function HeaderSkeleton() {
  return <header className="ecommerce-route-skeleton-header" aria-hidden="true"><div><i /><i /></div><i /></header>;
}

export default function EcommerceRouteSkeleton({ pathname = "", label = "Loading Online Store", lang = "en", direction = lang === "ar" ? "rtl" : "ltr" }) {
  if (/^\/ecommerce\/products\/(?:new|[^/]+\/edit)/.test(pathname)) return <ProductEditorSkeleton label={label} direction={direction} lang={lang} />;

  if (pathname.startsWith("/ecommerce/store")) {
    return (
      <main className="ecommerce-store-admin" dir={direction} lang={lang} aria-busy="true">
        <HeaderSkeleton />
        <StorePreviewSkeleton label={label} />
      </main>
    );
  }

  if (pathname.startsWith("/ecommerce/theme")) {
    return (
      <main dir={direction} lang={lang} className="ecommerce-page ecommerce-operations-page" aria-busy="true">
        <HeaderSkeleton />
        <ThemeSkeleton label={label} />
      </main>
    );
  }

  if (/^\/ecommerce\/orders\/[^/]+/.test(pathname)) {
    return <main dir={direction} lang={lang} className="ecommerce-page ecommerce-operations-page"><EcommerceOperationsSkeleton variant="order-detail" label={label} /></main>;
  }

  if (pathname.startsWith("/ecommerce/orders")) return <main className="ecommerce-page ecommerce-operations-page ecommerce-orders-page" dir={direction} lang={lang}>
    <HeaderSkeleton />
    <div className="ecommerce-orders-workspace">
      <aside className="ecommerce-operations-card ecommerce-orders-sidebar" aria-hidden="true"><div className="commerce-skeleton-fields commerce-skeleton-sidebar-fields">{Array.from({ length: 6 }, (_, index) => <div key={index}><i /><i /></div>)}</div></aside>
      <div><section className="ecommerce-operations-card ecommerce-orders-search-card"><div className="ecommerce-route-skeleton-filters" aria-hidden="true"><i /><i /><i /></div></section><section className="ecommerce-operations-card ecommerce-orders-results"><EcommerceOperationsSkeleton variant="orders" label={label} /></section></div>
    </div>
  </main>;

  if (pathname.startsWith("/ecommerce/delivery") || pathname.startsWith("/ecommerce/orders") || pathname.startsWith("/ecommerce/loyalty")) {
    const variant = pathname.startsWith("/ecommerce/delivery")
      ? "delivery"
      : pathname.startsWith("/ecommerce/loyalty")
        ? "loyalty"
        : "orders";
    return (
      <main dir={direction} lang={lang} className="ecommerce-page ecommerce-operations-page">
        <HeaderSkeleton />
        <section className="ecommerce-operations-card">
          {variant !== "loyalty" && <div className="ecommerce-route-skeleton-filters" aria-hidden="true"><i /><i /><i /></div>}
          <EcommerceOperationsSkeleton variant={variant} label={label} />
        </section>
      </main>
    );
  }

  return <main className="ecommerce-page" dir={direction} lang={lang}><CatalogSkeleton label={label} section={pathname.startsWith("/ecommerce/tags") ? "tags" : pathname.startsWith("/ecommerce/categories") ? "categories" : "products"} /></main>;
}

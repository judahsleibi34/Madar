const bars = (count) => Array.from({ length: count }, (_, index) => <i key={index} />);

export function StorePreviewSkeleton({ label = "Loading store", className = "ecommerce-store-page-skeleton", announce = true }) {
  return <div className={`${className} commerce-preview-skeleton`} role={announce ? "status" : undefined} aria-label={announce ? label : undefined} aria-busy="true" aria-hidden={announce ? undefined : true}>
    <div className="commerce-preview-header" aria-hidden="true"><div><i /><i /></div><nav>{bars(3)}</nav><i /></div>
    <div className="commerce-preview-hero" aria-hidden="true"><div><i /><i /><i /><i /><i /></div><i /></div>
    <div className="commerce-preview-products" aria-hidden="true">{Array.from({ length: 3 }, (_, index) => <div key={index}><i /><i /><i /></div>)}</div>
  </div>;
}

export function ProductEditorSkeleton({ label = "Loading product", direction = "ltr", lang = "en" }) {
  return <section className="ecommerce-product-editor commerce-editor-skeleton" dir={direction} lang={lang} role="status" aria-label={label} aria-busy="true">
    <header aria-hidden="true"><div><i /><i /></div></header>
    <section aria-hidden="true"><i className="commerce-skeleton-section-title" /><div className="commerce-skeleton-language-grid">{Array.from({ length: 2 }, (_, index) => <div key={index}><i /><i /><i /><i /></div>)}</div><div className="commerce-skeleton-fields">{Array.from({ length: 4 }, (_, index) => <div key={index}><i /><i /></div>)}</div></section>
    <section aria-hidden="true"><i className="commerce-skeleton-section-title" /><div className="commerce-skeleton-media">{bars(3)}</div></section>
    <section aria-hidden="true"><i className="commerce-skeleton-section-title" /><div className="commerce-skeleton-fields">{Array.from({ length: 4 }, (_, index) => <div key={index}><i /><i /></div>)}</div></section>
  </section>;
}

export function ThemeSkeleton({ label = "Loading store design" }) {
  return <div className="ecommerce-theme-skeleton commerce-theme-skeleton" role="status" aria-label={label} aria-busy="true">
    <div className="commerce-theme-fields" aria-hidden="true"><i className="commerce-skeleton-section-title" />{Array.from({ length: 6 }, (_, index) => <div key={index}><i /><div><i /><i /></div><i /></div>)}<i className="commerce-skeleton-button" /></div>
    <StorePreviewSkeleton label={label} className="commerce-theme-preview-skeleton" announce={false} />
  </div>;
}

export function CatalogSkeleton({ label = "Loading catalog", section = "products", summaryCount }) {
  return <div className="ecommerce-page-skeleton commerce-catalog-skeleton" role="status" aria-label={label} aria-busy="true">
    <header aria-hidden="true"><div><i /><i /><i /></div><i /></header>
    <section aria-hidden="true">{Array.from({ length: summaryCount ?? (section === "products" ? 7 : 5) }, (_, index) => <div key={index}><i /><div><i /><i /></div></div>)}</section>
    <article aria-hidden="true"><header><div><i /><i /></div><i /></header>{Array.from({ length: 5 }, (_, index) => <div className="commerce-catalog-row" key={index}><i /><div><i /><i /></div><i /><i /></div>)}</article>
  </div>;
}

export function SettingsSkeleton({ label = "Loading settings" }) {
  return <div className="settings-card commerce-settings-skeleton" role="status" aria-label={label} aria-busy="true">
    <div className="commerce-settings-cover" aria-hidden="true"><i /><i /></div>
    <div className="commerce-settings-heading" aria-hidden="true"><i /><div><i /><i /></div><i /></div>
    <div className="commerce-skeleton-fields" aria-hidden="true">{Array.from({ length: 6 }, (_, index) => <div key={index}><i /><i /></div>)}</div>
    <i className="commerce-skeleton-button" aria-hidden="true" />
  </div>;
}

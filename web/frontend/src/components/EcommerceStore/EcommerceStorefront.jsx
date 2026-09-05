import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, CheckCircle2, ChevronRight, Mail, Menu, Minus, Phone, Plus, Search, ShieldCheck, ShoppingBag, ShoppingCart, Trash2, X } from "lucide-react";

import {
  fetchPublicEcommerceCatalog,
  fetchPublicEcommerceProduct,
  fetchPublicEcommerceProfile,
  createPublicEcommerceOrder,
} from "../../services/ecommerceApi";
import { getResponsiveMediaProps } from "../../utils/media";
import { normalizeStoreTheme } from "../../utils/ecommerceTheme";
import "../../styles/public/ecommerce-storefront.css";

const EMPTY_CATALOG = {
  categories: [],
  tags: [],
  products: [],
  pagination: { page: 1, pages: 1, total: 0, limit: 12 },
};

const formatPrice = (value, currency, locale) => {
  const amount = Number(value || 0);
  try {
    return new Intl.NumberFormat(locale || "en", {
      style: "currency",
      currency: currency || "USD",
    }).format(Number.isFinite(amount) ? amount : 0);
  } catch {
    return `${currency || "USD"} ${amount.toFixed(2)}`;
  }
};

const readCart = (key) => {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
};

const readThemePreview = () => {
  try {
    const value = JSON.parse(localStorage.getItem("madar-online-store-theme-preview") || "null");
    return value && typeof value === "object" ? value : null;
  } catch {
    return null;
  }
};

function ProductImage({ product, className = "", eager = false }) {
  const [failedSource, setFailedSource] = useState("");
  const source = product?.images?.[0];
  const mediaProps = getResponsiveMediaProps(source, { sizes: "(max-width: 700px) 100vw, 33vw" });
  if (source && mediaProps.src && failedSource !== mediaProps.src) {
    return <img className={className} {...mediaProps} alt={product.name} loading={eager ? "eager" : "lazy"} decoding="async" fetchPriority={eager ? "high" : "auto"} onError={() => setFailedSource(mediaProps.src)} />;
  }
  return (
    <div className={`${className} live-store-image-placeholder`.trim()} aria-label="No product image">
      <ShoppingBag size={34} aria-hidden="true" />
    </div>
  );
}

function StoreHeader({ brand, logoUrl, cartCount, shopPath, homePath, categoriesPath, contactPath, onCartOpen }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const navigate = useNavigate();
  const searchStore = (event) => {
    event.preventDefault();
    const query = searchQuery.trim();
    navigate(query ? `${shopPath}?search=${encodeURIComponent(query)}` : shopPath);
    setMenuOpen(false);
  };
  return (
    <header className="live-store-header">
      <div className="live-store-header-inner">
        <Link className="live-store-brand" to={homePath}>{logoUrl && <img {...getResponsiveMediaProps(logoUrl, { fallbackWidth: 160, sizes: "48px" })} alt="" />}<span>{brand}</span></Link>
        <button
          type="button"
          className="live-store-mobile-menu"
          onClick={() => setMenuOpen((value) => !value)}
          aria-label="Toggle navigation"
        >
          {menuOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
        <nav className={menuOpen ? "is-open" : ""} aria-label="Store navigation">
          <Link to={homePath}>Home</Link>
          <Link to={shopPath}>Products</Link>
          <Link to={categoriesPath}>Categories</Link>
          <Link to={contactPath}>Contact us</Link>
        </nav>
        <form className="live-store-header-search" role="search" onSubmit={searchStore}>
          <input type="search" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search the store" aria-label="Search store" />
          <button type="submit" aria-label="Submit store search"><Search size={18} aria-hidden="true" /></button>
        </form>
        <button type="button" className="live-store-cart" onClick={onCartOpen} aria-label={`Open cart, ${cartCount} ${cartCount === 1 ? "item" : "items"}`}>
          <ShoppingCart size={21} strokeWidth={1.8} aria-hidden="true" />
          {cartCount > 0 && <b>{cartCount > 99 ? "99+" : cartCount}</b>}
        </button>
      </div>
    </header>
  );
}

function StoreCart({ open, items, homePath, checkoutPath, onClose, onQuantityChange, onRemove }) {
  const currency = items[0]?.currency || "USD";
  const subtotal = items.reduce((total, item) => total + Number(item.price || 0) * Number(item.quantity || 0), 0);
  if (!open) return null;
  return (
    <div className="live-store-cart-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className="live-store-cart-drawer" role="dialog" aria-modal="true" aria-labelledby="live-store-cart-title">
        <header>
          <div><span>Your selection</span><h2 id="live-store-cart-title">Shopping cart</h2></div>
          <button type="button" onClick={onClose} aria-label="Close cart"><X size={21} /></button>
        </header>
        {items.length === 0 ? (
          <div className="live-store-cart-empty"><ShoppingBag size={34} aria-hidden="true" /><h3>Your cart is empty</h3><p>Add something you love and it will appear here.</p></div>
        ) : (
          <div className="live-store-cart-items">
            {items.map((item) => (
              <article key={item.id}>
                <Link className="live-store-cart-item-image" to={`${homePath}/product/${encodeURIComponent(item.slug)}`} onClick={onClose}><ProductImage product={item} /></Link>
                <div className="live-store-cart-item-copy">
                  <Link to={`${homePath}/product/${encodeURIComponent(item.slug)}`} onClick={onClose}>{item.name}</Link>
                  {item.price != null && <span>{formatPrice(item.price, item.currency, "en")}</span>}
                  <div className="live-store-cart-item-actions">
                    <div aria-label={`Quantity for ${item.name}`}>
                      <button type="button" onClick={() => onQuantityChange(item.id, item.quantity - 1)} aria-label={`Decrease ${item.name} quantity`}><Minus size={14} /></button>
                      <span>{item.quantity}</span>
                      <button type="button" onClick={() => onQuantityChange(item.id, item.quantity + 1)} aria-label={`Increase ${item.name} quantity`}><Plus size={14} /></button>
                    </div>
                    <button type="button" className="live-store-cart-remove" onClick={() => onRemove(item.id)} aria-label={`Remove ${item.name}`}><Trash2 size={16} /></button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
        <footer>
          {items.length > 0 && (
            <>
              <div className="live-store-cart-subtotal"><span>Subtotal</span><strong>{formatPrice(subtotal, currency, "en")}</strong></div>
              <Link className="live-store-cart-checkout" to={checkoutPath} onClick={onClose}>Proceed to checkout <ArrowRight size={17} aria-hidden="true" /></Link>
              <Link className="live-store-cart-continue" to={`${homePath}/catalog`} onClick={onClose}>Continue shopping</Link>
            </>
          )}
          {items.length === 0 && <Link className="live-store-cart-checkout" to={`${homePath}/catalog`} onClick={onClose}>Browse products</Link>}
        </footer>
      </aside>
    </div>
  );
}

function StoreCheckout({ items, shopPath, onPlaceOrder }) {
  const [status, setStatus] = useState({ saving: false, error: "", order: null });
  const currency = items[0]?.currency || "USD";
  const subtotal = items.reduce((total, item) => total + Number(item.price || 0) * Number(item.quantity || 0), 0);

  if (status.order) {
    return (
      <section className="live-store-checkout-success">
        <CheckCircle2 size={44} aria-hidden="true" />
        <p>Order received</p>
        <h1>Thank you for your order.</h1>
        <span>Your order number is <strong>{status.order.order_number}</strong>. The store will contact you to confirm delivery.</span>
        <Link to={shopPath}>Continue shopping</Link>
      </section>
    );
  }

  if (!items.length) {
    return (
      <section className="live-store-checkout-empty">
        <ShoppingBag size={38} aria-hidden="true" />
        <h1>Your cart is empty</h1>
        <p>Add products before continuing to checkout.</p>
        <Link to={shopPath}>Browse products</Link>
      </section>
    );
  }

  const submit = async (event) => {
    event.preventDefault();
    setStatus({ saving: true, error: "", order: null });
    const form = new FormData(event.currentTarget);
    try {
      const result = await onPlaceOrder({
        customer_name: String(form.get("customer_name") || ""),
        email: String(form.get("email") || ""),
        phone: String(form.get("phone") || ""),
        address_line_1: String(form.get("address_line_1") || ""),
        address_line_2: String(form.get("address_line_2") || ""),
        city: String(form.get("city") || ""),
        postal_code: String(form.get("postal_code") || ""),
        country: String(form.get("country") || ""),
        notes: String(form.get("notes") || ""),
        payment_method: "cash_on_delivery",
        items: items.map((item) => ({ product_id: item.id, quantity: item.quantity })),
      });
      setStatus({ saving: false, error: "", order: result?.order || null });
    } catch (error) {
      setStatus({ saving: false, error: error?.message || "Could not place your order.", order: null });
    }
  };

  return (
    <section className="live-store-checkout">
      <header className="live-store-page-heading">
        <Link className="live-store-back" to={shopPath}><ArrowLeft size={15} aria-hidden="true" />Back to shop</Link>
        <h1>Checkout</h1>
        <p>Enter your delivery details and review your order.</p>
      </header>
      <form onSubmit={submit}>
        <div className="live-store-checkout-form">
          <section>
            <h2>Contact information</h2>
            <div className="live-store-checkout-fields">
              <label className="is-wide"><span>Full name</span><input name="customer_name" autoComplete="name" required maxLength={160} /></label>
              <label><span>Email</span><input name="email" type="email" autoComplete="email" required maxLength={254} /></label>
              <label><span>Phone</span><input name="phone" type="tel" autoComplete="tel" required maxLength={50} /></label>
            </div>
          </section>
          <section>
            <h2>Delivery address</h2>
            <div className="live-store-checkout-fields">
              <label className="is-wide"><span>Address</span><input name="address_line_1" autoComplete="address-line1" required maxLength={240} /></label>
              <label className="is-wide"><span>Apartment, suite, etc. (optional)</span><input name="address_line_2" autoComplete="address-line2" maxLength={240} /></label>
              <label><span>City</span><input name="city" autoComplete="address-level2" required maxLength={120} /></label>
              <label><span>Postal code</span><input name="postal_code" autoComplete="postal-code" maxLength={30} /></label>
              <label className="is-wide"><span>Country</span><input name="country" autoComplete="country-name" required maxLength={120} /></label>
              <label className="is-wide"><span>Delivery notes (optional)</span><textarea name="notes" rows={3} maxLength={1000} /></label>
            </div>
          </section>
          <section className="live-store-payment-method">
            <h2>Payment</h2>
            <div><ShieldCheck size={21} aria-hidden="true" /><span><strong>Pay on delivery</strong><small>Payment is collected when your order arrives.</small></span></div>
          </section>
        </div>
        <aside className="live-store-checkout-summary">
          <h2>Order summary</h2>
          <div className="live-store-checkout-items">
            {items.map((item) => <article key={item.id}><ProductImage product={item} /><div><strong>{item.name}</strong><span>Quantity {item.quantity}</span></div><b>{formatPrice(Number(item.price || 0) * item.quantity, item.currency, "en")}</b></article>)}
          </div>
          <div className="live-store-checkout-total"><span>Subtotal</span><strong>{formatPrice(subtotal, currency, "en")}</strong></div>
          <p>Delivery fees, if any, will be confirmed by the store.</p>
          {status.error && <div className="live-store-checkout-error" role="alert">{status.error}</div>}
          <button type="submit" disabled={status.saving}>{status.saving ? "Placing order..." : "Place order"}</button>
        </aside>
      </form>
    </section>
  );
}

function SkeletonBlock({ className = "" }) {
  return <span className={`live-store-skeleton-block ${className}`.trim()} aria-hidden="true" />;
}

function StoreSkeleton({ view }) {
  const label = view === "product" ? "product details" : view === "catalog" ? "products" : view;
  if (view === "landing") {
    return (
      <div className="live-store-skeleton is-landing" role="status" aria-label="Loading home page">
        <section className="live-store-skeleton-landing-hero">
          <div className="live-store-skeleton-copy">
            <SkeletonBlock className="is-title" />
            <SkeletonBlock className="is-subtitle" />
            <SkeletonBlock className="is-line" />
            <SkeletonBlock className="is-line is-short" />
            <SkeletonBlock className="is-button" />
          </div>
          <SkeletonBlock className="is-media" />
        </section>
        <section className="live-store-skeleton-products">
          <SkeletonBlock className="is-section-title" />
          <div>{Array.from({ length: 4 }, (_, index) => <SkeletonBlock className="is-card" key={index} />)}</div>
        </section>
      </div>
    );
  }

  if (view === "categories") {
    return (
      <section className="live-store-skeleton is-categories" role="status" aria-label="Loading categories page">
        <div className="live-store-skeleton-copy"><SkeletonBlock className="is-title" /><SkeletonBlock className="is-line" /></div>
        <div className="live-store-skeleton-category-grid">{Array.from({ length: 6 }, (_, index) => <SkeletonBlock className="is-category" key={index} />)}</div>
      </section>
    );
  }

  if (view === "contact") {
    return (
      <section className="live-store-skeleton is-contact" role="status" aria-label="Loading contact page">
        <div className="live-store-skeleton-copy"><SkeletonBlock className="is-title" /><SkeletonBlock className="is-line" /><SkeletonBlock className="is-line is-short" /></div>
        <SkeletonBlock className="is-contact-card" />
      </section>
    );
  }

  if (view === "product") {
    return (
      <section className="live-store-skeleton is-product" role="status" aria-label="Loading product details page">
        <SkeletonBlock className="is-product-image" />
        <div className="live-store-skeleton-copy"><SkeletonBlock className="is-subtitle" /><SkeletonBlock className="is-title" /><SkeletonBlock className="is-price" /><SkeletonBlock className="is-line" /><SkeletonBlock className="is-line is-short" /><SkeletonBlock className="is-button" /></div>
      </section>
    );
  }

  return (
    <section className="live-store-skeleton is-catalog" role="status" aria-label={`Loading ${label} page`}>
      <div className="live-store-skeleton-copy is-page-heading">
        <SkeletonBlock className="is-title" />
        <SkeletonBlock className="is-subtitle" />
        <SkeletonBlock className="is-line" />
      </div>
      <aside><SkeletonBlock className="is-search" />{Array.from({ length: 5 }, (_, index) => <SkeletonBlock className="is-filter" key={index} />)}</aside>
      <div className="live-store-skeleton-catalog-main"><SkeletonBlock className="is-toolbar" /><div>{Array.from({ length: 6 }, (_, index) => <SkeletonBlock className="is-card" key={index} />)}</div></div>
    </section>
  );
}
function StoreCategories({ categories, shopPath }) {
  return (
    <section className="live-store-directory">
      <header className="live-store-page-heading">
        <h1>Categories</h1>
        <p className="live-store-page-subtitle">Browse the store</p>
        <p>Choose a category to see the products available in it.</p>
      </header>
      {categories.length > 0 ? (
        <div className="live-store-directory-grid">
          {categories.map((category) => (
            <Link key={category.id} to={`${shopPath}?category=${encodeURIComponent(category.slug)}`}>
              <div>
                <h2>{category.name}</h2>
                {category.description && <p>{category.description}</p>}
              </div>
              <ArrowRight size={21} aria-hidden="true" />
            </Link>
          ))}
        </div>
      ) : (
        <div className="live-store-landing-empty">
          <ShoppingBag size={30} aria-hidden="true" />
          <h2>No categories yet</h2>
          <p>New categories will appear here when they are published.</p>
        </div>
      )}
    </section>
  );
}

function StoreContact({ brand, site }) {
  const hasEmail = Boolean(site?.contact_email);
  const hasPhone = Boolean(site?.phone);
  return (
    <section className="live-store-contact-page">
      <div className="live-store-contact-intro live-store-page-heading">
        <h1>How can we help?</h1>
        <p className="live-store-page-subtitle">Contact us</p>
        <p>{site?.description || `Get in touch with ${brand}. We will be happy to hear from you.`}</p>
      </div>
      <div className="live-store-contact-panel">
        <h2>{brand}</h2>
        {(hasEmail || hasPhone) ? (
          <div className="live-store-contact-links">
            {hasEmail && <a href={`mailto:${site.contact_email}`}><Mail size={21} aria-hidden="true" /><span><small>Email</small>{site.contact_email}</span></a>}
            {hasPhone && <a href={`tel:${site.phone}`}><Phone size={21} aria-hidden="true" /><span><small>Phone</small>{site.phone}</span></a>}
          </div>
        ) : (
          <p className="live-store-contact-empty">Contact details will appear here when the store owner publishes them.</p>
        )}
      </div>
    </section>
  );
}
function CategoryList({ categories, activeSlug, onSelect }) {
  const childrenByParent = useMemo(() => {
    const map = new Map();
    categories.forEach((item) => {
      const key = item.parent_id || "root";
      map.set(key, [...(map.get(key) || []), item]);
    });
    return map;
  }, [categories]);

  const renderBranch = (parentId = "root", depth = 0) =>
    (childrenByParent.get(parentId) || []).map((item) => (
      <li key={item.id}>
        <button
          type="button"
          className={activeSlug === item.slug ? "is-active" : ""}
          style={{ paddingInlineStart: `${depth * 14 + 2}px` }}
          onClick={() => onSelect(item.slug)}
        >
          <span>{item.name}</span>
          <ChevronRight size={15} aria-hidden="true" />
        </button>
        {(childrenByParent.get(item.id) || []).length > 0 && (
          <ul>{renderBranch(item.id, depth + 1)}</ul>
        )}
      </li>
    ));

  return (
    <ul className="live-store-category-list">
      <li>
        <button
          type="button"
          className={!activeSlug ? "is-active" : ""}
          onClick={() => onSelect("")}
        >
          <span>View all</span>
        </button>
      </li>
      {renderBranch()}
    </ul>
  );
}

function ProductGallery({ product }) {
  const images = Array.isArray(product?.images) ? product.images.slice(0, 4) : [];
  const [selectedImage, setSelectedImage] = useState("");

  if (!images.length) {
    return <div className="live-store-detail-gallery"><div className="live-store-detail-main-image"><ProductImage product={product} /></div></div>;
  }

  const activeImage = images.includes(selectedImage) ? selectedImage : images[0];
  const selectedIndex = images.indexOf(activeImage);
  return (
    <div className="live-store-detail-gallery">
      <div className="live-store-detail-main-image">
        <img {...getResponsiveMediaProps(activeImage, { sizes: "(max-width: 760px) 100vw, 58vw" })} alt={`${product.name} ${selectedIndex + 1}`} />
      </div>
      {images.length > 1 && <div className="live-store-detail-thumbnails">{images.map((image, index) => <button type="button" className={index === selectedIndex ? "is-active" : ""} key={image} onClick={() => setSelectedImage(image)} aria-label={`Show product image ${index + 1}`}><img {...getResponsiveMediaProps(image, { fallbackWidth: 320, sizes: "120px" })} alt="" /></button>)}</div>}
    </div>
  );
}


function ProductCard({ product, category, locale, productPath, onAdd, eager = false }) {
  return (
    <article className="live-store-product-card">
      <Link className="live-store-product-image" to={productPath}>
        <ProductImage product={product} eager={eager} />
        <span className="live-store-product-view">View product</span>
      </Link>
      <div className="live-store-product-body">
        <p className="live-store-product-category">
          {[product.brand, category?.name].filter(Boolean).join(" / ") || "Product"}
        </p>
        <h2><Link to={productPath}>{product.name}</Link></h2>
        <div className="live-store-product-bottom">
          <div className="live-store-price-row">
            <strong>{formatPrice(product.price, product.currency, locale)}</strong>
            {product.compare_at_price && (
              <del>{formatPrice(product.compare_at_price, product.currency, locale)}</del>
            )}
          </div>
          <button type="button" disabled={!product.in_stock} onClick={() => onAdd(product)}>
            <ShoppingBag size={16} aria-hidden="true" />
            {product.in_stock ? "Add to cart" : "Out of stock"}
          </button>
        </div>
      </div>
    </article>
  );
}


function StoreLanding({ brand, site, catalog, categoryById, locale, shopPath, productBasePath, onAdd }) {
  const featuredProducts = catalog.products.slice(0, 4);
  const featuredCategories = catalog.categories.filter((item) => !item.parent_id).slice(0, 3);
  const leadProduct = featuredProducts[0];
  const productTotal = Number(catalog.pagination?.total || catalog.products.length || 0);

  return (
    <div className="live-store-landing">
      <section className="live-store-landing-hero">
        <div className="live-store-landing-copy">
          <h1 className="live-store-welcome-title">{brand}</h1>
          {site?.description && <p>{site.description}</p>}
          <div className="live-store-landing-actions">
            <Link className="live-store-primary-link" to={shopPath}>Browse products <ArrowRight size={18} /></Link>
            {featuredCategories[0] && <Link className="live-store-text-link" to={`${shopPath}?category=${encodeURIComponent(featuredCategories[0].slug)}`}>Shop {featuredCategories[0].name}</Link>}
          </div>
          {(productTotal > 0 || catalog.categories.length > 0) && (
            <dl className="live-store-landing-facts">
              {productTotal > 0 && <div><dt>{productTotal}</dt><dd>Products</dd></div>}
              {catalog.categories.length > 0 && <div><dt>{catalog.categories.length}</dt><dd>Collections</dd></div>}
            </dl>
          )}
        </div>
        <div className="live-store-landing-visual">
          {leadProduct ? (
            <Link to={`${productBasePath}/product/${encodeURIComponent(leadProduct.slug)}`}>
              <ProductImage product={leadProduct} eager />
              <span><small>Featured now</small><strong>{leadProduct.name}</strong><b>{formatPrice(leadProduct.price, leadProduct.currency, locale)}</b></span>
            </Link>
          ) : (
            <div className="live-store-landing-placeholder"><ShoppingBag size={42} aria-label="No featured product" /></div>
          )}
        </div>
      </section>

      {featuredCategories.length > 0 && (
        <section className="live-store-landing-section">
          <header><div><h2>Categories</h2></div><Link to={shopPath}>View all <ArrowRight size={17} /></Link></header>
          <div className="live-store-category-grid">
            {featuredCategories.map((category, index) => (
              <Link key={category.id} to={`${shopPath}?category=${encodeURIComponent(category.slug)}`}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div><h3>{category.name}</h3>{category.description && <p>{category.description}</p>}</div>
                <ArrowRight size={20} />
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="live-store-landing-section live-store-featured-section">
        <header><div><h2>Products</h2></div><Link to={shopPath}>View all <ArrowRight size={17} /></Link></header>
        {featuredProducts.length > 0 ? (
          <div className="live-store-grid">
            {featuredProducts.map((product, index) => (
              <ProductCard key={product.id} product={product} category={categoryById.get(product.category_id)} locale={locale} productPath={`${productBasePath}/product/${encodeURIComponent(product.slug)}`} onAdd={onAdd} eager={index < 3} />
            ))}
          </div>
        ) : (
          <div className="live-store-landing-empty"><ShoppingBag size={30} /><h3>No published products</h3></div>
        )}
      </section>

    </div>
  );
}
export default function EcommerceStorefront({ subdomain: suppliedSubdomain = "", basePath: suppliedBasePath = "" }) {
  const params = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const subdomain = suppliedSubdomain || params.subdomain || "";
  const storePath = suppliedBasePath || `/store/${encodeURIComponent(subdomain)}`;
  const shopPath = `${storePath}/catalog`;
  const categoriesPath = `${storePath}/categories`;
  const contactPath = `${storePath}/contact`;
  const checkoutPath = `${storePath}/checkout`;
  const homePath = storePath;
  const routeTail = String(params["*"] || "");
  const productSlug = routeTail.match(/^(?:catalog\/)?product\/([^/]+)\/?$/)?.[1] || "";
  const catalogRoute = /^catalog\/?$/.test(routeTail);
  const categoriesRoute = /^categories\/?$/.test(routeTail);
  const contactRoute = /^contact\/?$/.test(routeTail);
  const checkoutRoute = /^checkout\/?$/.test(routeTail);
  const urlFilters = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const [draftPreviewMode] = useState(() => new URLSearchParams(window.location.search).get("preview") === "draft");
  const [draftTheme, setDraftTheme] = useState(() => draftPreviewMode ? readThemePreview() : null);
  // Public stores are independent of the dashboard shell language. Without an
  // explicit locale, catalog content is English and must stay LTR.
  const locale = "en";
  const [catalog, setCatalog] = useState(EMPTY_CATALOG);
  const [site, setSite] = useState(null);
  const siteRef = useRef(null);
  const [productDetail, setProductDetail] = useState(null);
  const [requestStatus, setRequestStatus] = useState({
    key: "",
    loading: true,
    error: "",
  });
  const cartKey = `madar-store-cart:${subdomain}`;
  const [cart, setCart] = useState(() => readCart(cartKey));
  const [cartOpen, setCartOpen] = useState(false);

  const filters = {
    search: urlFilters.get("search") || "",
    category: urlFilters.get("category") || "",
    tag: urlFilters.get("tag") || "",
    sort: urlFilters.get("sort") || "latest",
    page: urlFilters.get("page") || "1",
    locale,
  };

  const hasCatalogFilters = Boolean(filters.search || filters.category || filters.tag || filters.page !== "1" || filters.sort !== "latest");
  const landingRoute = routeTail === "";
  const isLanding = landingRoute && !hasCatalogFilters;
  const isCatalogView = catalogRoute || (landingRoute && hasCatalogFilters);

  const requestKey = JSON.stringify([
    subdomain,
    productSlug,
    filters.search,
    filters.category,
    filters.tag,
    filters.sort,
    filters.page,
    locale,
    contactRoute,
    checkoutRoute,
  ]);
  const loading = requestStatus.key !== requestKey || requestStatus.loading;
  const error = requestStatus.key === requestKey ? requestStatus.error : "";

  useEffect(() => {
    let cancelled = false;
    const request = productSlug
      ? fetchPublicEcommerceProduct(subdomain, productSlug, locale)
      : contactRoute || checkoutRoute
        ? fetchPublicEcommerceProfile(subdomain)
        : fetchPublicEcommerceCatalog(subdomain, {
          search: filters.search,
          category: filters.category,
          tag: filters.tag,
          sort: filters.sort,
          page: filters.page,
          locale,
          limit: "12",
        });
    request
      .then((result) => {
        if (cancelled) return;
        const nextSite = result?.site || siteRef.current || null;
        siteRef.current = nextSite;
        setSite(nextSite);
        if (productSlug) {
          setProductDetail(result || null);
        } else {
          setCatalog(result?.catalog || EMPTY_CATALOG);
          setProductDetail(null);
        }
        setRequestStatus({ key: requestKey, loading: false, error: "" });
      })
      .catch((requestError) => {
        if (!cancelled) {
          setRequestStatus({
            key: requestKey,
            loading: false,
            error: requestError?.message || "Could not load the live store",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [
    subdomain,
    productSlug,
    locale,
    filters.search,
    filters.category,
    filters.tag,
    filters.sort,
    filters.page,
    requestKey,
    contactRoute,
    checkoutRoute,
  ]);

  useEffect(() => {
    if (!draftPreviewMode) return undefined;
    const receiveTheme = (event) => {
      if (event.origin !== window.location.origin || event.data?.type !== "madar-online-store-theme-preview") return;
      const nextTheme = event.data?.theme;
      if (nextTheme && typeof nextTheme === "object") setDraftTheme(nextTheme);
    };
    window.addEventListener("message", receiveTheme);
    return () => window.removeEventListener("message", receiveTheme);
  }, [draftPreviewMode]);

  const setFilter = (key, value, resetPage = true) => {
    const next = new URLSearchParams(location.search);
    if (value) next.set(key, value);
    else next.delete(key);
    if (resetPage && key !== "page") next.delete("page");
    navigate(`${shopPath}${next.toString() ? `?${next}` : ""}`);
  };

  const cartItems = useMemo(() => Array.from(cart.reduce((items, item) => {
    const current = items.get(item.id);
    items.set(item.id, { ...current, ...item, quantity: (current?.quantity || 0) + Number(item.quantity || 1) });
    return items;
  }, new Map()).values()), [cart]);
  const cartCount = cartItems.reduce((total, item) => total + item.quantity, 0);

  const saveCart = (next) => {
    setCart(next);
    localStorage.setItem(cartKey, JSON.stringify(next));
  };

  const addToCart = (product) => {
    const existing = cartItems.find((item) => item.id === product.id);
    const nextItem = {
      id: product.id,
      slug: product.slug,
      name: product.name,
      quantity: (existing?.quantity || 0) + 1,
      price: product.price,
      currency: product.currency,
      images: product.images || [],
    };
    saveCart([...cartItems.filter((item) => item.id !== product.id), nextItem]);
  };

  const changeCartQuantity = (id, quantity) => {
    if (quantity < 1) {
      saveCart(cartItems.filter((item) => item.id !== id));
      return;
    }
    saveCart(cartItems.map((item) => item.id === id ? { ...item, quantity } : item));
  };

  const placeOrder = async (payload) => {
    const result = await createPublicEcommerceOrder(subdomain, payload);
    saveCart([]);
    return result;
  };

  const categoryById = useMemo(
    () => new Map(catalog.categories.map((item) => [item.id, item])),
    [catalog.categories]
  );
  const brand = site?.brand || site?.footer_store_name || "";
  const savedTheme = normalizeStoreTheme(draftTheme || site?.store_theme || site?.theme);
  const storeStyle = {
    "--store-accent": savedTheme.accent,
    "--store-paper": savedTheme.background,
    "--store-soft": savedTheme.softSurface || savedTheme.surface,
    "--store-ink": savedTheme.text,
    "--store-muted": savedTheme.muted,
    "--store-night": savedTheme.accentDark || savedTheme.text,
  };

  useLayoutEffect(() => {
    const root = document.documentElement;
    const body = document.body;
    const previous = { rootDir: root.getAttribute("dir"), rootLang: root.getAttribute("lang"), bodyDir: body?.getAttribute("dir") };
    root.setAttribute("dir", "ltr");
    root.setAttribute("lang", "en");
    body?.setAttribute("dir", "ltr");
    return () => {
      if (previous.rootDir === null) root.removeAttribute("dir"); else root.setAttribute("dir", previous.rootDir);
      if (previous.rootLang === null) root.removeAttribute("lang"); else root.setAttribute("lang", previous.rootLang);
      if (body) { if (previous.bodyDir === null) body.removeAttribute("dir"); else body.setAttribute("dir", previous.bodyDir); }
    };
  }, []);

  return (
    <div className="live-store" style={storeStyle} dir="ltr" lang="en">
      <StoreHeader brand={brand} logoUrl={site?.logo_url} cartCount={cartCount} shopPath={shopPath} homePath={homePath} categoriesPath={categoriesPath} contactPath={contactPath} onCartOpen={() => setCartOpen(true)} />
      <StoreCart open={cartOpen} items={cartItems} homePath={homePath} checkoutPath={checkoutPath} onClose={() => setCartOpen(false)} onQuantityChange={changeCartQuantity} onRemove={(id) => saveCart(cartItems.filter((item) => item.id !== id))} />
      <main>

        {loading && <StoreSkeleton view={productSlug ? "product" : categoriesRoute ? "categories" : contactRoute ? "contact" : checkoutRoute ? "catalog" : isLanding ? "landing" : "catalog"} />}
        {!loading && error && <div className="live-store-state is-error"><h2>Store unavailable</h2><p>{error}</p></div>}

        {!loading && !error && isLanding && (
          <StoreLanding brand={brand} site={site} catalog={catalog} categoryById={categoryById} locale={locale} shopPath={shopPath} productBasePath={homePath} onAdd={addToCart} />
        )}

        {!loading && !error && categoriesRoute && (
          <StoreCategories categories={catalog.categories} shopPath={shopPath} />
        )}

        {!loading && !error && contactRoute && (
          <StoreContact brand={brand} site={site} />
        )}

        {!loading && !error && checkoutRoute && (
          <StoreCheckout items={cartItems} shopPath={shopPath} onPlaceOrder={placeOrder} />
        )}

        {!loading && !error && productSlug && productDetail?.product && (
          <section className="live-store-detail">
            <ProductGallery product={productDetail.product} />
            <div className="live-store-detail-copy">
              <Link className="live-store-back" to={shopPath}><ArrowLeft size={15} aria-hidden="true" />Back to shop</Link>
              <p className="live-store-product-category">{[productDetail.product.brand, productDetail.category?.name].filter(Boolean).join(" / ")}</p>
              <h1>{productDetail.product.name}</h1>
              <div className="live-store-detail-price">{formatPrice(productDetail.product.price, productDetail.product.currency, locale)}</div>
              {productDetail.product.compare_at_price && <del className="live-store-detail-compare-price">{formatPrice(productDetail.product.compare_at_price, productDetail.product.currency, locale)}</del>}
              {productDetail.product.description && <p>{productDetail.product.description}</p>}
              <button type="button" disabled={!productDetail.product.in_stock} onClick={() => addToCart(productDetail.product)}><ShoppingBag size={18} />{productDetail.product.in_stock ? "Add to cart" : "Out of stock"}</button>
              {productDetail.tags?.length > 0 && <div className="live-store-detail-tags">{productDetail.tags.map((item) => <span key={item.id}>{item.name}</span>)}</div>}
            </div>
          </section>
        )}

        {!loading && !error && !productSlug && !checkoutRoute && isCatalogView && (
          <section className="live-store-catalog-page">
            <header className="live-store-page-heading">
              <h1>Products</h1>
            </header>
            <div className="live-store-shell">
              <aside>
              <form className="live-store-search" onSubmit={(event) => { event.preventDefault(); const value = new FormData(event.currentTarget).get("search"); setFilter("search", typeof value === "string" ? value : ""); }}>
                <input key={filters.search} name="search" defaultValue={filters.search} placeholder="Search for products..." aria-label="Search products" />
                <button type="submit" aria-label="Search"><Search size={18} /></button>
              </form>
              <div className="live-store-filter-card"><h2>Categories</h2><CategoryList categories={catalog.categories} activeSlug={filters.category} onSelect={(value) => setFilter("category", value)} /></div>
              {catalog.tags.length > 0 && <div className="live-store-filter-card"><h2>Tags</h2><div className="live-store-tags">{catalog.tags.map((item) => <button type="button" key={item.id} className={filters.tag === item.slug ? "is-active" : ""} onClick={() => setFilter("tag", filters.tag === item.slug ? "" : item.slug)}>{item.name}</button>)}</div></div>}
            </aside>
            <div className="live-store-results">
              <div className="live-store-toolbar"><p>Showing <strong>{catalog.pagination.total}</strong> results</p><select value={filters.sort} onChange={(event) => setFilter("sort", event.target.value)} aria-label="Sort products"><option value="latest">Latest products</option><option value="price_low">Price: Low to high</option><option value="price_high">Price: High to low</option><option value="name">Name</option></select></div>
              {catalog.products.length > 0 ? <div className="live-store-grid">{catalog.products.map((product, index) => <ProductCard key={product.id} product={product} category={categoryById.get(product.category_id)} locale={locale} productPath={`${homePath}/product/${encodeURIComponent(product.slug)}`} onAdd={addToCart} eager={index < 3} />)}</div> : <div className="live-store-empty"><ShoppingBag size={38} /><h2>No products found</h2><p>Try another category, tag, or search term.</p></div>}
              {catalog.pagination.pages > 1 && <nav className="live-store-pagination" aria-label="Product pages">{Array.from({ length: catalog.pagination.pages }, (_, index) => index + 1).map((page) => <button type="button" key={page} className={Number(filters.page) === page ? "is-active" : ""} onClick={() => setFilter("page", String(page), false)}>{page}</button>)}</nav>}
              </div>
            </div>
          </section>
        )}
      </main>
      <footer className="live-store-footer">
        <div>{brand && <strong>{brand}</strong>}{site?.description && <p>{site.description}</p>}</div>
        <div><strong>Shop</strong><Link to={shopPath}>Products</Link><Link to={categoriesPath}>Categories</Link></div>
        <div><strong>Contact</strong>{site?.contact_email && <a href={`mailto:${site.contact_email}`}>{site.contact_email}</a>}{site?.phone && <a href={`tel:${site.phone}`}>{site.phone}</a>}</div>
      </footer>
    </div>
  );
}

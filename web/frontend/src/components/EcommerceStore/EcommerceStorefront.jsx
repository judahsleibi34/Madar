import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { Menu, Search, ShoppingBag, X } from "lucide-react";

import {
  fetchPublicEcommerceCatalog,
  fetchPublicEcommerceProduct,
} from "../../services/ecommerceApi";
import { getPageBuilderThemeVars } from "../PageBuilder/core/PageBuilder.theme";
import {
  getPilatesDemoCatalog,
  getPilatesDemoProduct,
  isPilatesDemoSite,
} from "./pilatesDemoCatalog";
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

function ProductImage({ product, className = "" }) {
  const source = product?.images?.[0];
  if (source) {
    return <img className={className} src={source} alt={product.name} loading="lazy" />;
  }
  return (
    <div className={`${className} live-store-image-placeholder`.trim()} aria-label="No product image">
      <ShoppingBag size={34} aria-hidden="true" />
    </div>
  );
}

function StoreHeader({ brand, cartCount, shopPath, homePath }) {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <header className="live-store-header">
      <div className="live-store-header-inner">
        <Link className="live-store-brand" to={homePath}>{brand}</Link>
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
          <Link to={shopPath}>Shop</Link>
        </nav>
        <span className="live-store-cart" aria-label={`${cartCount} items in cart`}>
          <ShoppingBag size={20} aria-hidden="true" />
          <b>{cartCount}</b>
        </span>
      </div>
    </header>
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
          <span aria-hidden="true">›</span>
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

function ProductCard({ product, category, locale, productPath, onAdd }) {
  return (
    <article className="live-store-product-card">
      <Link className="live-store-product-image" to={productPath}>
        <ProductImage product={product} />
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

export default function EcommerceStorefront({ subdomain: suppliedSubdomain = "" }) {
  const params = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const subdomain = suppliedSubdomain || params.subdomain || "";
  const shopPath = `/site/${encodeURIComponent(subdomain)}/shop`;
  const homePath = `/site/${encodeURIComponent(subdomain)}/`;
  const productSlug = String(params["*"] || "").match(/^product\/([^/]+)\/?$/)?.[1] || "";
  const urlFilters = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const locale = urlFilters.get("locale") || document.documentElement.lang || "en";
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

  const filters = {
    search: urlFilters.get("search") || "",
    category: urlFilters.get("category") || "",
    tag: urlFilters.get("tag") || "",
    sort: urlFilters.get("sort") || "latest",
    page: urlFilters.get("page") || "1",
    locale,
  };

  const requestKey = JSON.stringify([
    subdomain,
    productSlug,
    filters.search,
    filters.category,
    filters.tag,
    filters.sort,
    filters.page,
    locale,
  ]);
  const loading = requestStatus.key !== requestKey || requestStatus.loading;
  const error = requestStatus.key === requestKey ? requestStatus.error : "";

  useEffect(() => {
    let cancelled = false;
    const demoProduct = getPilatesDemoProduct(productSlug);
    const request = productSlug && demoProduct && isPilatesDemoSite(siteRef.current)
      ? Promise.resolve({ ...demoProduct, site: siteRef.current })
      : productSlug
      ? fetchPublicEcommerceProduct(subdomain, productSlug, locale)
      : fetchPublicEcommerceCatalog(subdomain, {
          search: filters.search,
          category: filters.category,
          tag: filters.tag,
          sort: filters.sort,
          page: filters.page,
          locale,
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
          const remoteCatalog = result?.catalog || EMPTY_CATALOG;
          setCatalog(
            isPilatesDemoSite(nextSite) && remoteCatalog.products.length === 0
              ? getPilatesDemoCatalog({
                  search: filters.search,
                  category: filters.category,
                  tag: filters.tag,
                  sort: filters.sort,
                  page: filters.page,
                })
              : remoteCatalog
          );
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
  ]);

  const setFilter = (key, value, resetPage = true) => {
    const next = new URLSearchParams(location.search);
    if (value) next.set(key, value);
    else next.delete(key);
    if (resetPage && key !== "page") next.delete("page");
    navigate(`${shopPath}${next.toString() ? `?${next}` : ""}`);
  };

  const addToCart = (product) => {
    const next = [...cart, { id: product.id, slug: product.slug, name: product.name, quantity: 1 }];
    setCart(next);
    localStorage.setItem(cartKey, JSON.stringify(next));
  };

  const categoryById = useMemo(
    () => new Map(catalog.categories.map((item) => [item.id, item])),
    [catalog.categories]
  );
  const brand = site?.brand || site?.footer_store_name || "Madar Store";

  return (
    <div
      className="live-store"
      dir={String(locale).startsWith("ar") ? "rtl" : "ltr"}
      style={getPageBuilderThemeVars(site?.theme)}
    >
      <StoreHeader brand={brand} cartCount={cart.length} shopPath={shopPath} homePath={homePath} />
      <main>
        <section className="live-store-hero">
          <h1>{productSlug ? "Product" : "Shop"}</h1>
          <p><Link to={homePath}>Home</Link> / <Link to={shopPath}>Shop</Link></p>
        </section>

        {loading && <div className="live-store-state">Loading the live store…</div>}
        {!loading && error && (
          <div className="live-store-state is-error">
            <h2>Store unavailable</h2>
            <p>{error}</p>
          </div>
        )}

        {!loading && !error && productSlug && productDetail?.product && (
          <section className="live-store-detail">
            <div className="live-store-detail-gallery">
              <ProductImage product={productDetail.product} />
            </div>
            <div className="live-store-detail-copy">
              <Link className="live-store-back" to={shopPath}>← Back to shop</Link>
              <p className="live-store-product-category">
                {[productDetail.product.brand, productDetail.category?.name].filter(Boolean).join(" / ")}
              </p>
              <h1>{productDetail.product.name}</h1>
              <div className="live-store-detail-price">
                {formatPrice(productDetail.product.price, productDetail.product.currency, locale)}
              </div>
              <p>{productDetail.product.description || "Product details will appear here."}</p>
              <button
                type="button"
                disabled={!productDetail.product.in_stock}
                onClick={() => addToCart(productDetail.product)}
              >
                <ShoppingBag size={18} />
                {productDetail.product.in_stock ? "Add to cart" : "Out of stock"}
              </button>
              {productDetail.tags?.length > 0 && (
                <div className="live-store-detail-tags">
                  {productDetail.tags.map((item) => <span key={item.id}>{item.name}</span>)}
                </div>
              )}
            </div>
          </section>
        )}

        {!loading && !error && !productSlug && (
          <section className="live-store-shell">
            <aside>
              <form
                className="live-store-search"
                onSubmit={(event) => {
                  event.preventDefault();
                  const value = new FormData(event.currentTarget).get("search");
                  setFilter("search", typeof value === "string" ? value : "");
                }}
              >
                <input
                  key={filters.search}
                  name="search"
                  defaultValue={filters.search}
                  placeholder="Search for products…"
                  aria-label="Search products"
                />
                <button type="submit" aria-label="Search"><Search size={18} /></button>
              </form>
              <div className="live-store-filter-card">
                <h2>Categories</h2>
                <CategoryList
                  categories={catalog.categories}
                  activeSlug={filters.category}
                  onSelect={(value) => setFilter("category", value)}
                />
              </div>
              {catalog.tags.length > 0 && (
                <div className="live-store-filter-card">
                  <h2>Tags</h2>
                  <div className="live-store-tags">
                    {catalog.tags.map((item) => (
                      <button
                        type="button"
                        key={item.id}
                        className={filters.tag === item.slug ? "is-active" : ""}
                        onClick={() => setFilter("tag", filters.tag === item.slug ? "" : item.slug)}
                      >
                        {item.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </aside>
            <div className="live-store-results">
              <div className="live-store-toolbar">
                <p>Showing <strong>{catalog.pagination.total}</strong> results</p>
                <select
                  value={filters.sort}
                  onChange={(event) => setFilter("sort", event.target.value)}
                  aria-label="Sort products"
                >
                  <option value="latest">Latest products</option>
                  <option value="price_low">Price: Low to high</option>
                  <option value="price_high">Price: High to low</option>
                  <option value="name">Name</option>
                </select>
              </div>
              {catalog.products.length > 0 ? (
                <div className="live-store-grid">
                  {catalog.products.map((product) => (
                    <ProductCard
                      key={product.id}
                      product={product}
                      category={categoryById.get(product.category_id)}
                      locale={locale}
                      productPath={`${shopPath}/product/${encodeURIComponent(product.slug)}`}
                      onAdd={addToCart}
                    />
                  ))}
                </div>
              ) : (
                <div className="live-store-empty">
                  <ShoppingBag size={38} />
                  <h2>No products found</h2>
                  <p>Try another category, tag, or search term.</p>
                </div>
              )}
              {catalog.pagination.pages > 1 && (
                <nav className="live-store-pagination" aria-label="Product pages">
                  {Array.from({ length: catalog.pagination.pages }, (_, index) => index + 1).map((page) => (
                    <button
                      type="button"
                      key={page}
                      className={Number(filters.page) === page ? "is-active" : ""}
                      onClick={() => setFilter("page", String(page), false)}
                    >
                      {page}
                    </button>
                  ))}
                </nav>
              )}
            </div>
          </section>
        )}
      </main>
      <footer className="live-store-footer">
        <div>
          <strong>{brand}</strong>
          <p>{site?.description || "Explore our latest products and collections."}</p>
        </div>
        <div>
          <strong>Shop</strong>
          <Link to={shopPath}>All products</Link>
        </div>
        <div>
          <strong>Contact</strong>
          {site?.contact_email && <a href={`mailto:${site.contact_email}`}>{site.contact_email}</a>}
          {site?.phone && <a href={`tel:${site.phone}`}>{site.phone}</a>}
        </div>
      </footer>
    </div>
  );
}

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, AlertCircle, CheckCircle2, ChevronLeft, ChevronRight, Globe2, Gift, Mail, Menu, MessageCircle, Minus, Phone, Plus, Search, ShieldCheck, ShoppingBag, ShoppingCart, Trash2, X, ZoomIn } from "lucide-react";
import { useTranslation } from "react-i18next";
import i18n from "../../i18n";

import {
  fetchPublicEcommerceCatalog,
  fetchPublicEcommerceProduct,
  fetchPublicEcommerceProfile,
  createPublicEcommerceOrder,
  reconcilePublicEcommerceCart,
  fetchPublicEcommerceDeliveryAreas,
  fetchPublicEcommerceOrderConfirmation,
  fetchPublicEcommerceLoyalty,
  fetchPublicEcommerceDiscounts,
} from "../../services/ecommerceApi";
import StorefrontSeo, { safePublicUrl } from "./StorefrontSeo";
import { getResponsiveMediaProps, isVideoMediaUrl, resolveMediaUrl } from "../../utils/media";
import { normalizeStoreTheme } from "../../utils/ecommerceTheme";
import { formatCommerceMoney, normalizeCommerceLocale } from "../../utils/commerceI18n";
import { estimateCartDiscount } from "../../utils/ecommerceDiscounts";
import { normalizeWhatsAppNumber } from "../../utils/whatsapp";
import { trackCommerceEvent, trackPurchaseOnce } from "../../services/commerceAnalytics";
import { recordPublicSiteVisit } from "../../services/siteVisitApi";
import "../../styles/public/ecommerce-storefront.css";

const EMPTY_CATALOG = {
  categories: [],
  brands: [],
  tags: [],
  products: [],
  featured_products: [],
  featured_categories: [],
  price_bounds: { min: null, max: null, currency: "" },
  pagination: { page: 1, pages: 1, total: 0, limit: 12 },
};

const formatPrice = formatCommerceMoney;
const c = (key, values) => i18n.t(`commerce:${key}`, values);

const STORE_SOCIAL_NETWORKS = [
  ["facebook", "Facebook"],
  ["instagram", "Instagram"],
  ["tiktok", "TikTok"],
  ["snapchat", "Snapchat"],
];

function SocialIcon({ network }) {
  if (network === "instagram") return <svg data-social-icon={network} viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="3.5" width="17" height="17" rx="5" /><circle cx="12" cy="12" r="4" /><circle className="is-filled" cx="17.5" cy="6.5" r="1" /></svg>;
  if (network === "tiktok") return <svg data-social-icon={network} viewBox="0 0 24 24" aria-hidden="true"><path d="M14.2 3h3.4c.3 2.1 1.5 3.4 3.4 3.8v3.5a8.2 8.2 0 0 1-3.4-1v6.1A6.4 6.4 0 1 1 12 9v3.6a2.9 2.9 0 1 0 2.2 2.8V3Z" /></svg>;
  if (network === "snapchat") return <svg data-social-icon={network} viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.2c3 0 4.8 2.3 4.8 5.2 0 1 .1 1.8.4 2.5.4.9 1.1 1.2 2.1 1.6.7.3.8 1.2.1 1.6-.8.4-1.5.7-2.1 1.1-.4.3-.3 1 .1 1.3.4.3.9.5 1.4.7-.8.8-1.8 1.1-2.9 1.1-.7 0-1.4.8-1.9 1.4-.5.6-1.2 1.1-2 1.1s-1.5-.5-2-1.1c-.5-.6-1.2-1.4-1.9-1.4-1.1 0-2.1-.3-2.9-1.1.5-.2 1-.4 1.4-.7.4-.3.5-1 .1-1.3-.6-.4-1.3-.7-2.1-1.1-.7-.4-.6-1.3.1-1.6 1-.4 1.7-.7 2.1-1.6.3-.7.4-1.5.4-2.5C7.2 5.5 9 3.2 12 3.2Z" /></svg>;
  return <svg data-social-icon="facebook" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 8h3V4h-3c-3.3 0-5 2-5 5v3H6v4h3v8h4v-8h3l1-4h-4V9c0-.7.3-1 1-1Z" /></svg>;
}

const activeLocale = () => normalizeCommerceLocale(i18n.resolvedLanguage || i18n.language);

class StorefrontActionError extends Error {
  constructor(messageKey) {
    super("Storefront action could not complete");
    this.messageKey = messageKey;
  }
}

function StoreWhatsAppLink({ phone, brand }) {
  const number = normalizeWhatsAppNumber(phone);
  if (!number) return null;
  const message = c("contact.whatsappMessage", { brand: brand || c("nav.shop") });
  const href = `https://wa.me/${number}?text=${encodeURIComponent(message)}`;
  return (
    <a
      className="live-store-whatsapp"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={c("contact.whatsappAria", { brand: brand || c("nav.shop") })}
      onClick={() => trackCommerceEvent("contact_click", { channel: "whatsapp", locale: activeLocale() })}
    >
      <span className="live-store-whatsapp-mark" aria-hidden="true"><MessageCircle size={28} /><Phone size={14} /></span>
    </a>
  );
}

function StoreActionToast({ notification, onDismiss, locale }) {
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    if (!notification || paused) return undefined;
    const timer = window.setTimeout(onDismiss, notification.type === "error" ? 6500 : 4200);
    return () => window.clearTimeout(timer);
  }, [notification, onDismiss, paused]);
  if (!notification) return null;
  return <div className={`live-store-action-toast is-${notification.type}`} role={notification.type === "error" ? "alert" : "status"} aria-live={notification.type === "error" ? "assertive" : "polite"} dir={locale === "ar" ? "rtl" : "ltr"} onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)} onFocus={() => setPaused(true)} onBlur={() => setPaused(false)}>
    <span aria-hidden="true">{notification.type === "error" ? <AlertCircle size={20} /> : <CheckCircle2 size={20} />}</span>
    <div><strong>{notification.title}</strong>{notification.message && <p>{notification.message}</p>}</div>
    <button type="button" onClick={onDismiss} aria-label={c("admin.close")}><X size={16} /></button>
  </div>;
}

const readCart = (key) => {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
};
const cartLineKey = (item) => `${item.id}:${item.variant_id || "simple"}`;
const optionSnapshotText = (options = []) => options.map((item) => `${item.option_name || item.option_code}: ${item.value || item.value_code}`).join(" · ");


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
  const source = product?.images?.find((item) => !isVideoMediaUrl(item));
  const mediaProps = getResponsiveMediaProps(source, { sizes: "(max-width: 700px) 100vw, 33vw" });
  if (source && mediaProps.src && failedSource !== mediaProps.src) {
    return <img className={className} {...mediaProps} alt={product.name} loading={eager ? "eager" : "lazy"} decoding="async" fetchPriority={eager ? "high" : "auto"} onError={() => setFailedSource(mediaProps.src)} />;
  }
  return (
    <div className={`${className} live-store-image-placeholder`.trim()} aria-label={c("product.noImage")}>
      <ShoppingBag size={34} aria-hidden="true" />
    </div>
  );
}

function StoreHeader({ brand, logoUrl, cartCount, shopPath, homePath, categoriesPath, contactPath, onCartOpen }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const toggleRef = useRef(null);
  const panelRef = useRef(null);
  const { pathname } = useLocation();
  useEffect(() => {
    if (!menuOpen) return undefined;
    const panel = panelRef.current;
    const toggle = toggleRef.current;
    const store = panel?.closest(".live-store");
    const previousOverflow = store?.style.overflowY;
    if (store) store.style.overflowY = "hidden";
    panel?.querySelector("button")?.focus();
    const handleKey = event => {
      if (event.key === "Escape") setMenuOpen(false);
      if (event.key !== "Tab") return;
      const targets = Array.from(panel?.querySelectorAll("a[href],button") || []);
      const first = targets[0], last = targets.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener("keydown", handleKey);
    const media = window.matchMedia?.("(min-width:761px)");
    const closeOnResize = event => { if (event.matches) setMenuOpen(false); };
    media?.addEventListener?.("change", closeOnResize);
    return () => {
      document.removeEventListener("keydown", handleKey);
      media?.removeEventListener?.("change", closeOnResize);
      if (store) store.style.overflowY = previousOverflow;
      toggle?.focus();
    };
  }, [menuOpen]);
  const links = [[homePath,c("nav.home")],[shopPath,c("common.products")],[categoriesPath,c("nav.categories")],[contactPath,c("nav.contact")]];
  const brandLink = <Link className="live-store-brand" to={homePath} onClick={() => setMenuOpen(false)}>{logoUrl && <img {...getResponsiveMediaProps(logoUrl, { fallbackWidth:160, sizes:"48px" })} alt="" />}<span>{brand}</span></Link>;
  const navigate = useNavigate();
  const searchStore = (event) => {
    event.preventDefault();
    const query = searchQuery.trim();
    navigate(query ? `${shopPath}?search=${encodeURIComponent(query)}` : shopPath);
    setMenuOpen(false);
  };
  return (
    <>
    <header className="live-store-header">
      <div className="live-store-header-inner">
        {brandLink}
        <button
          type="button"
          className="live-store-mobile-menu"
          ref={toggleRef}
          onClick={() => setMenuOpen((value) => !value)}
          aria-label={c("nav.shop")}
          aria-expanded={menuOpen}
          aria-controls="live-store-mobile-navigation"
        >
          {menuOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
        <nav id="live-store-navigation" aria-label={c("nav.navigation")}>
          <Link to={homePath} onClick={() => setMenuOpen(false)}>{c("nav.home")}</Link>
          <Link to={shopPath} onClick={() => setMenuOpen(false)}>{c("common.products")}</Link>
          <Link to={categoriesPath} onClick={() => setMenuOpen(false)}>{c("nav.categories")}</Link>
          <Link to={contactPath} onClick={() => setMenuOpen(false)}>{c("nav.contact")}</Link>
        </nav>
        <form className="live-store-header-search" role="search" onSubmit={searchStore}>
          <input type="search" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder={c("catalog.searchPlaceholder")} aria-label={c("nav.searchStore")} />
          <button type="submit" aria-label={c("common.search")}><Search size={18} aria-hidden="true" /></button>
        </form>
        <button type="button" className="live-store-language" onClick={() => i18n.changeLanguage(activeLocale() === "ar" ? "en" : "ar")}>{activeLocale() === "ar" ? "English" : "العربية"}</button>
        <button type="button" className="live-store-cart" onClick={onCartOpen} aria-label={c("nav.openCart", { count: cartCount })}>
          <ShoppingCart size={21} strokeWidth={1.8} aria-hidden="true" />
          {cartCount > 0 && <b>{cartCount > 99 ? "99+" : cartCount}</b>}
        </button>
      </div>
    </header>
    {menuOpen && <div className="live-store-menu-overlay" onMouseDown={event => { if (event.target === event.currentTarget) setMenuOpen(false); }}>
      <section ref={panelRef} className="live-store-menu-panel" role="dialog" aria-modal="true" aria-label={c("nav.navigation")}>
        <header>{brandLink}<button type="button" onClick={() => setMenuOpen(false)} aria-label={c("admin.close")}><X size={22} aria-hidden="true" /></button></header>
        <div className="live-store-menu-content">
          <p className="live-store-menu-label">{c("nav.menu")}</p>
          <nav id="live-store-mobile-navigation" aria-label={c("nav.navigation")}>
            {links.map(([path,label]) => <Link key={path} to={path} aria-current={pathname === path ? "page" : undefined} onClick={() => setMenuOpen(false)}><span>{label}</span><ChevronRight size={18} aria-hidden="true" /></Link>)}
          </nav>
          <div className="live-store-menu-language"><p className="live-store-menu-label">{c("nav.language")}</p><button type="button" onClick={() => { i18n.changeLanguage(activeLocale() === "ar" ? "en" : "ar"); setMenuOpen(false); }}><Globe2 size={20} aria-hidden="true" /><span>{activeLocale() === "ar" ? "English" : "\u0627\u0644\u0639\u0631\u0628\u064a\u0629"}</span><ChevronRight size={18} aria-hidden="true" /></button></div>
        </div>
      </section>
    </div>}
    </>
  );
}

function StoreCart({ open, items, homePath, checkoutPath, delivery, selectedAreaId, onSelectedAreaChange, loyalty, normalDiscounts, onClose, onQuantityChange, onRemove }) {
  const currency = items[0]?.currency || "USD";
  const subtotal = items.reduce((total, item) => total + Number(item.price || 0) * Number(item.quantity || 0), 0);
  const estimatedDiscount = estimateCartDiscount(items, normalDiscounts, loyalty?.entitlements || []);
  const selectedArea = delivery.areas.find((area) => area.id === selectedAreaId);
  const deliveryFee = Number(selectedArea?.delivery_fee || 0);
  const total = subtotal - estimatedDiscount + deliveryFee;
  if (!open) return null;
  return (
    <div className="live-store-cart-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className="live-store-cart-drawer" role="dialog" aria-modal="true" aria-labelledby="live-store-cart-title">
        <header>
          <div><span>{c("cart.selection")}</span><h2 id="live-store-cart-title">{c("cart.title")}</h2></div>
          <button type="button" onClick={onClose} aria-label={c("cart.close")}><X size={21} /></button>
        </header>
        {items.length === 0 ? (
          <div className="live-store-cart-empty"><ShoppingBag size={34} aria-hidden="true" /><h3>{c("cart.emptyTitle")}</h3><p>{c("cart.emptyBody")}</p></div>
        ) : (
          <div className="live-store-cart-items">
            {items.map((item) => (
              <article key={cartLineKey(item)}>
                <Link className="live-store-cart-item-image" to={`${homePath}/product/${encodeURIComponent(item.slug)}`} onClick={onClose}><ProductImage product={item} /></Link>
                <div className="live-store-cart-item-copy">
                  <Link to={`${homePath}/product/${encodeURIComponent(item.slug)}`} onClick={onClose}>{item.name}</Link>
                  {item.price != null && <span>{formatPrice(item.price, item.currency, activeLocale())}</span>}
                  {item.selected_options?.length > 0 && <small>{optionSnapshotText(item.selected_options)}</small>}
                  <div className="live-store-cart-item-actions">
                    <div aria-label={c("cart.quantityFor", { name: item.name })}>
                      <button type="button" onClick={() => onQuantityChange(cartLineKey(item), item.quantity - 1)} aria-label={c("cart.decrease", { name: item.name })}><Minus size={14} /></button>
                      <span>{item.quantity}</span>
                      <button type="button" onClick={() => onQuantityChange(cartLineKey(item), item.quantity + 1)} aria-label={c("cart.increase", { name: item.name })}><Plus size={14} /></button>
                    </div>
                    <button type="button" className="live-store-cart-remove" onClick={() => onRemove(cartLineKey(item))} aria-label={c("cart.remove", { name: item.name })}><Trash2 size={16} /></button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
        <footer>
          {items.length > 0 && (
            <>
              <div className="live-store-cart-subtotal"><span>{c("common.subtotal")}</span><strong>{formatPrice(subtotal, currency, activeLocale())}</strong></div>
              {estimatedDiscount > 0 && <div className="live-store-cart-subtotal"><span>{c("common.discount")}</span><strong>-{formatPrice(estimatedDiscount, currency, activeLocale())}</strong></div>}
              <label className="live-store-cart-delivery">
                <span>{c("checkout.serviceArea")}</span>
                <select value={selectedAreaId} disabled={delivery.loading || !delivery.areas.length} onChange={(event) => onSelectedAreaChange(event.target.value)}>
                  <option value="">{delivery.loading ? c("checkout.loadingAreas") : c("checkout.chooseArea")}</option>
                  {delivery.areas.map((area) => <option key={area.id} value={area.id}>{activeLocale() === "ar" ? area.name_ar || area.name_en : area.name_en || area.name_ar}</option>)}
                </select>
              </label>
              <div className="live-store-cart-subtotal"><span>{c("merchant.deliveryFee")}</span><strong>{selectedArea ? formatPrice(deliveryFee, currency, activeLocale()) : c("checkout.chooseArea")}</strong></div>
              <div className="live-store-cart-subtotal is-total"><span>{c("common.total")}</span><strong>{formatPrice(total, currency, activeLocale())}</strong></div>
              <Link className="live-store-cart-checkout" to={checkoutPath} onClick={onClose}>{c("cart.checkout")} <ArrowRight size={17} aria-hidden="true" /></Link>
              <Link className="live-store-cart-continue" to={`${homePath}/catalog`} onClick={onClose}>{c("cart.continue")}</Link>
            </>
          )}
          {items.length === 0 && <Link className="live-store-cart-checkout" to={`${homePath}/catalog`} onClick={onClose}>{c("landing.browse")}</Link>}
        </footer>
      </aside>
    </div>
  );
}

function StoreCheckout({ items, loyalty, normalDiscounts, shopPath, storePath, delivery, selectedAreaId, onSelectedAreaChange, onPlaceOrder, onNotify }) {
  const navigate = useNavigate();
  const [status, setStatus] = useState({ saving: false, error: "" });
  const currency = items[0]?.currency || "USD";
  const subtotal = items.reduce((total, item) => total + Number(item.price || 0) * Number(item.quantity || 0), 0);
  const estimatedDiscount = estimateCartDiscount(items, normalDiscounts, loyalty?.entitlements || []);
  const selectedArea = delivery.areas.find((area) => area.id === selectedAreaId);
  const deliveryFee = Number(selectedArea?.delivery_fee || 0);
  const estimatedTotal = subtotal - estimatedDiscount + deliveryFee;

  const checkoutTracked = useRef(false);
  useEffect(() => {
    if (checkoutTracked.current || !items.length || delivery.loading || !selectedArea) return;
    checkoutTracked.current = true;
    trackCommerceEvent("begin_checkout", { item_count: items.reduce((sum, item) => sum + item.quantity, 0), subtotal, discount_total: estimatedDiscount, delivery_fee: deliveryFee, total: estimatedTotal, currency, locale: activeLocale() });
  }, [currency, delivery.loading, deliveryFee, estimatedDiscount, estimatedTotal, items, selectedArea, subtotal]);

  if (!items.length) {
    return (
      <section className="live-store-checkout-empty">
        <ShoppingBag size={38} aria-hidden="true" />
        <h1>{c("cart.emptyTitle")}</h1>
        <p>{c("checkout.empty")}</p>
        <Link to={shopPath}>{c("landing.browse")}</Link>
      </section>
    );
  }

  const submit = async (event) => {
    event.preventDefault();
    const minimumLengths = { customer_name: 2, phone: 5, street: 3 };
    const invalidField = Array.from(event.currentTarget.elements).find((field) =>
      field.willValidate && (!field.validity.valid ||
        (minimumLengths[field.name] && String(field.value).trim().length < minimumLengths[field.name]))
    );
    if (invalidField) {
      onNotify({ type: "error", title: c("storeFeedback.completeFields"), message: c("storeFeedback.completeFieldsBody") });
      invalidField.focus();
      return;
    }
    setStatus({ saving: true, error: "" });
    const form = new FormData(event.currentTarget);
    try {
      const result = await onPlaceOrder({
        customer_name: String(form.get("customer_name") || "").trim(),
        email: String(form.get("email") || "").trim(),
        phone: String(form.get("phone") || "").trim(),
        service_area_id: String(form.get("service_area_id") || ""),
        street: String(form.get("street") || "").trim(),
        building: String(form.get("building") || "").trim(),
        floor_apartment: String(form.get("floor_apartment") || "").trim(),
        address_description: String(form.get("address_description") || "").trim(),
        delivery_notes: String(form.get("delivery_notes") || "").trim(),
        payment_method: "cash_on_delivery",
        items: items.map((item) => ({ product_id: item.id, ...(item.variant_id ? { variant_id: item.variant_id } : {}), quantity: item.quantity })),
      });
      if (!result?.confirmation_token) throw new Error(c("errors.confirmationUnavailable"));
      onNotify({ type: "success", title: c("storeFeedback.orderPlaced"), message: c("storeFeedback.orderPlacedBody") });
      navigate(`${storePath}/confirmation/${result.confirmation_token}`, { replace: true });
    } catch (error) {
      const validationFailed = error?.status === 422;
      const message = validationFailed ? c("storeFeedback.completeFields") : error instanceof StorefrontActionError ? c(error.messageKey) : c("errors.placeOrder");
      setStatus({ saving: false, error: message });
      onNotify({ type: "error", title: message, message: c(validationFailed ? "storeFeedback.completeFieldsBody" : "admin.tryAgain") });
    }
  };

  return (
    <section className="live-store-checkout">
      <header className="live-store-page-heading">
        <Link className="live-store-back" to={shopPath}><ArrowLeft size={15} aria-hidden="true" />{c("product.back")}</Link>
        <h1>{c("checkout.title")}</h1>
        <p>{c("checkout.subtitle")}</p>
      </header>
      <form onSubmit={submit} noValidate>
        <div className="live-store-checkout-form">
          <section>
            <h2>{c("checkout.contact")}</h2>
            <div className="live-store-checkout-fields">
              <label className="is-wide"><span>{c("checkout.name")}</span><input name="customer_name" minLength={2} autoComplete="name" required maxLength={160} /></label>
              <label><span>{c("checkout.email")}</span><input name="email" type="email" autoComplete="email" required maxLength={254} dir="ltr" /></label>
              <label><span>{c("checkout.phone")}</span><input name="phone" minLength={5} type="tel" autoComplete="tel" required maxLength={50} dir="ltr" /></label>
            </div>
          </section>
          <section>
            <h2>{c("checkout.delivery")}</h2>
            <div className="live-store-checkout-fields">
              {delivery.loading && <p className="is-wide">{c("checkout.loadingAreas")}</p>}
              {!delivery.loading && delivery.error && <p className="is-wide live-store-checkout-error">{delivery.error}</p>}
              {!delivery.loading && !delivery.error && !delivery.areas.length && <p className="is-wide live-store-checkout-error">{c("checkout.noAreas")}</p>}
              <label className="is-wide"><span>{c("checkout.serviceArea")}</span><select name="service_area_id" required value={selectedAreaId} disabled={!delivery.areas.length} onChange={(event) => onSelectedAreaChange(event.target.value)}><option value="">{c("checkout.chooseArea")}</option>{delivery.areas.map((area) => <option key={area.id} value={area.id}>{activeLocale() === "ar" ? area.name_ar || area.name_en : area.name_en || area.name_ar} — {formatPrice(area.delivery_fee || 0, currency, activeLocale())}</option>)}</select></label>
              <label className="is-wide"><span>{c("checkout.street")}</span><input name="street" minLength={3} autoComplete="street-address" required maxLength={240} /></label>
              <label><span>{c("checkout.building")}</span><input name="building" maxLength={120} /></label>
              <label><span>{c("checkout.floor")}</span><input name="floor_apartment" maxLength={120} /></label>
              <label className="is-wide"><span>{c("checkout.description")}</span><textarea name="address_description" rows={2} maxLength={500} /></label>
              <label className="is-wide"><span>{c("checkout.notes")}</span><textarea name="delivery_notes" rows={3} maxLength={1000} /></label>
            </div>
          </section>
          <section className="live-store-payment-method">
            <h2>{c("checkout.payment")}</h2>
            <div><ShieldCheck size={21} aria-hidden="true" /><span><strong>{c("checkout.cod")}</strong></span></div>
          </section>
        </div>
        <aside className="live-store-checkout-summary">
          <h2>{c("checkout.review")}</h2>
          <div className="live-store-checkout-items">
            {items.map((item) => <article key={cartLineKey(item)}><ProductImage product={item} /><div><strong>{item.name}</strong>{item.selected_options?.length > 0 && <small>{optionSnapshotText(item.selected_options)}</small>}<span>{c("common.quantity")} {item.quantity}</span></div><b>{formatPrice(Number(item.price || 0) * item.quantity, item.currency, activeLocale())}</b></article>)}
          </div>
          <div className="live-store-checkout-total"><span>{c("common.subtotal")}</span><strong>{formatPrice(subtotal, currency, activeLocale())}</strong></div>
          {estimatedDiscount > 0 && <div className="live-store-checkout-total"><span>{c("common.discount")}</span><strong>-{formatPrice(estimatedDiscount, currency, activeLocale())}</strong></div>}
          <div className="live-store-checkout-total"><span>{c("merchant.deliveryFee")}</span><strong>{formatPrice(deliveryFee, currency, activeLocale())}</strong></div>
          <div className="live-store-checkout-total is-grand-total"><span>{c("common.total")}</span><strong>{formatPrice(estimatedTotal, currency, activeLocale())}</strong></div>
          {selectedArea && <p>{c("checkout.serviceArea")}: <strong>{activeLocale() === "ar" ? selectedArea.name_ar || selectedArea.name_en : selectedArea.name_en || selectedArea.name_ar}</strong></p>}
          {status.error && <div className="live-store-checkout-error" role="alert">{status.error}</div>}
          <button type="submit" disabled={status.saving || delivery.loading || !delivery.areas.length}>{status.saving ? c("checkout.placing") : c("checkout.placeOrder")}</button>
        </aside>
      </form>
    </section>
  );
}

function StoreConfirmation({ data, shopPath }) {
  const order = data?.order;
  useEffect(() => {
    if (order) trackPurchaseOnce(order, data?.items || [], activeLocale());
  }, [data?.items, order]);
  if (!order) return <section className="live-store-checkout-empty"><h1>{c("errors.storeUnavailable")}</h1><Link to={shopPath}>{c("confirmation.backToShop")}</Link></section>;
  const address = [order.street, order.building, order.floor_apartment].filter(Boolean).join(", ");
  return (
    <section className="live-store-checkout-success live-store-confirmation">
      <CheckCircle2 size={44} aria-hidden="true" /><p>{c("confirmation.title")}</p><h1>{order.order_number}</h1>
      <span>{c("confirmation.orderDate")}: {new Intl.DateTimeFormat(activeLocale(), { dateStyle: "medium", timeStyle: "short" }).format(new Date(order.created_at))}</span>
      <div className="live-store-confirmation-grid"><article><h2>{c("confirmation.customer")}</h2><p>{order.customer_name}<br /><bdi>{order.customer_phone}</bdi><br /><bdi>{order.customer_email}</bdi></p></article><article><h2>{c("confirmation.delivery")}</h2><p><strong>{activeLocale() === "ar" ? order.service_area_name_ar || order.service_area_name_en : order.service_area_name_en || order.service_area_name_ar}</strong><br />{address}</p></article><article><h2>{c("confirmation.payment")}</h2><p>{c("payment.cash_on_delivery")}<br />{c(`payment.${order.payment_status}`)}</p></article><article><h2>{c("common.status")}</h2><p>{c(`status.${order.status}`)}</p></article></div>
      <div className="live-store-checkout-items">{(data.items || []).map((item) => <article key={item.id}><div><strong>{item.product_name}</strong><span><bdi>{c("common.sku")} {item.sku}</bdi> · {c("common.quantity")} {item.quantity}</span>{item.discount_source === "loyalty" && <small>{c("loyalty.appliedDiscount")}: -{formatPrice(item.discount_amount, order.currency, activeLocale())}</small>}</div><b>{formatPrice(item.line_total, order.currency, activeLocale())}</b></article>)}</div>
      {(data.items || []).map((item) => Array.isArray(item.selected_options_snapshot?.items) && item.selected_options_snapshot.items.length > 0 ? <p className="live-store-confirmation-options" key={`${item.id}-options`}>{item.selected_options_snapshot.items.map((entry) => `${entry.option_name_translations?.[activeLocale()] || entry.option_name_translations?.en || entry.option_name_translations?.ar || entry.option_code}: ${entry.value_translations?.[activeLocale()] || entry.value_translations?.en || entry.value_translations?.ar || entry.value_code}`).join(" · ")}</p> : null)}
      <div className="live-store-checkout-total"><span>{c("common.subtotal")}</span><strong>{formatPrice(order.subtotal, order.currency, activeLocale())}</strong></div>
      <div className="live-store-checkout-total"><span>{c("common.discount")}</span><strong>{formatPrice(order.discount_total, order.currency, activeLocale())}</strong></div>
      <div className="live-store-checkout-total"><span>{c("merchant.deliveryFee")}</span><strong>{formatPrice(order.delivery_fee, order.currency, activeLocale())}</strong></div>
      <div className="live-store-checkout-total"><span>{c("common.total")}</span><strong>{formatPrice(order.total, order.currency, activeLocale())}</strong></div>
      <Link to={shopPath}>{c("cart.continue")}</Link>
    </section>
  );
}

function SkeletonBlock({ className = "" }) {
  return <span className={`live-store-skeleton-block ${className}`.trim()} aria-hidden="true" />;
}

function StoreSkeleton({ view }) {
  const label = c(`loading.${view === "product" ? "product" : view === "catalog" ? "catalog" : view}`);
  if (view === "landing") {
    return (
      <div className="live-store-skeleton is-landing" aria-busy="true" role="status" aria-label={c("loading.home")}>
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
      <section className="live-store-skeleton is-categories" aria-busy="true" role="status" aria-label={c("loading.categories")}>
        <div className="live-store-skeleton-copy"><SkeletonBlock className="is-title" /><SkeletonBlock className="is-line" /></div>
        <div className="live-store-skeleton-category-grid">{Array.from({ length: 6 }, (_, index) => <SkeletonBlock className="is-category" key={index} />)}</div>
      </section>
    );
  }

  if (view === "contact") {
    return (
      <section className="live-store-skeleton is-contact" aria-busy="true" role="status" aria-label={c("loading.contact")}>
        <div className="live-store-skeleton-copy"><SkeletonBlock className="is-title" /><SkeletonBlock className="is-line" /><SkeletonBlock className="is-line is-short" /></div>
        <SkeletonBlock className="is-contact-card" />
      </section>
    );
  }

  if (view === "product") {
    return (
      <section className="live-store-skeleton is-product" aria-busy="true" role="status" aria-label={c("loading.product")}>
        <SkeletonBlock className="is-product-image" />
        <div className="live-store-skeleton-copy"><SkeletonBlock className="is-subtitle" /><SkeletonBlock className="is-title" /><SkeletonBlock className="is-price" /><SkeletonBlock className="is-line" /><SkeletonBlock className="is-line is-short" /><SkeletonBlock className="is-button" /></div>
      </section>
    );
  }

  return (
    <section className="live-store-skeleton is-catalog" role="status" aria-label={label} aria-busy="true">
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
        <h1>{c("common.categories")}</h1>
        <p className="live-store-page-subtitle">{c("categories.browse")}</p>
        <p>{c("catalog.chooseCategory")}</p>
      </header>
      {categories.length > 0 ? (
        <div className="live-store-directory-grid">
          {categories.map((category) => (
            <Link key={category.id} to={`${shopPath}?category=${encodeURIComponent(category.slug)}`}>
              {category.image_url && <img className="live-store-directory-image" {...getResponsiveMediaProps(category.image_url, { widths: [480, 768, 1024, 1440], fallbackWidth: 1024, sizes: "(max-width: 760px) calc(100vw - 34px), (max-width: 980px) 50vw, 600px" })} alt="" loading="lazy" decoding="async" />}
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
          <h2>{c("categories.emptyTitle")}</h2>
          <p>{c("categories.emptyBody")}</p>
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
        <h1>{c("contact.title")}</h1>
        <p className="live-store-page-subtitle">{c("contact.subtitle")}</p>
        <p>{site?.description || c("contact.fallback", { brand })}</p>
      </div>
      <div className="live-store-contact-panel">
        <h2>{brand}</h2>
        {(hasEmail || hasPhone) ? (
          <div className="live-store-contact-links">
            {hasEmail && <a href={`mailto:${site.contact_email}`}><Mail size={21} aria-hidden="true" /><span><small>{c("checkout.email")}</small><bdi>{site.contact_email}</bdi></span></a>}
            {hasPhone && <a href={`tel:${site.phone}`}><Phone size={21} aria-hidden="true" /><span><small>{c("checkout.phone")}</small><bdi>{site.phone}</bdi></span></a>}
          </div>
        ) : (
          <p className="live-store-contact-empty">{c("contact.empty")}</p>
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
          style={{ "--category-depth": depth }}
          onClick={() => onSelect(item.slug)}
          title={item.name}
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
          <span>{c("common.viewAll")}</span>
        </button>
      </li>
      {renderBranch()}
    </ul>
  );
}

function PriceRangeFilter({ bounds, minimum, maximum, locale, onChange }) {
  const boundMinimum = Number(bounds?.min);
  const boundMaximum = Number(bounds?.max);
  const hasRange = Number.isFinite(boundMinimum) && Number.isFinite(boundMaximum);
  const safeMinimum = hasRange ? Math.max(0, boundMinimum) : 0;
  const safeMaximum = hasRange ? Math.max(safeMinimum, boundMaximum) : 0;
  const requestedMinimum = Number(minimum);
  const requestedMaximum = Number(maximum);
  const initialMinimum = minimum === "" || !Number.isFinite(requestedMinimum) ? safeMinimum : Math.min(safeMaximum, Math.max(safeMinimum, requestedMinimum));
  const initialMaximum = maximum === "" || !Number.isFinite(requestedMaximum) ? safeMaximum : Math.max(safeMinimum, Math.min(safeMaximum, requestedMaximum));
  const [values, setValues] = useState({ min: Math.min(initialMinimum, initialMaximum), max: Math.max(initialMinimum, initialMaximum) });
  const commitTimerRef = useRef(null);
  const currency = bounds?.currency || "USD";
  const spread = safeMaximum - safeMinimum;
  const start = spread > 0 ? ((values.min - safeMinimum) / spread) * 100 : 0;
  const end = spread > 0 ? ((values.max - safeMinimum) / spread) * 100 : 100;

  useEffect(() => () => window.clearTimeout(commitTimerRef.current), []);

  const scheduleChange = (next) => {
    setValues(next);
    window.clearTimeout(commitTimerRef.current);
    commitTimerRef.current = window.setTimeout(() => {
      const nextMinimum = next.min <= safeMinimum ? "" : String(Number(next.min.toFixed(2)));
      const nextMaximum = next.max >= safeMaximum ? "" : String(Number(next.max.toFixed(2)));
      onChange(nextMinimum, nextMaximum);
    }, 280);
  };

  return (
    <section className="live-store-filter-card live-store-price-filter" aria-labelledby="store-price-filter-title">
      <div className="live-store-price-filter-heading">
        <h2 id="store-price-filter-title">{c("catalog.priceFilter")}</h2>
        {(minimum || maximum) && <button type="button" onClick={() => onChange("", "")}>{c("catalog.clearPrice")}</button>}
      </div>
      <div className="live-store-price-values" aria-live="polite">
        <span><small>{c("catalog.minPrice")}</small><strong>{formatPrice(values.min, currency, locale)}</strong></span>
        <span><small>{c("catalog.maxPrice")}</small><strong>{formatPrice(values.max, currency, locale)}</strong></span>
      </div>
      <div className="live-store-price-range" style={{ "--price-start": `${start}%`, "--price-end": `${end}%` }}>
        <span className="live-store-price-range-track" aria-hidden="true" />
        <input
          type="range"
          min={safeMinimum}
          max={safeMaximum}
          step="0.01"
          value={values.min}
          disabled={!hasRange || spread === 0}
          aria-label={c("catalog.minPrice")}
          onChange={(event) => scheduleChange({ min: Math.min(Number(event.target.value), values.max), max: values.max })}
        />
        <input
          type="range"
          min={safeMinimum}
          max={safeMaximum}
          step="0.01"
          value={values.max}
          disabled={!hasRange || spread === 0}
          aria-label={c("catalog.maxPrice")}
          onChange={(event) => scheduleChange({ min: values.min, max: Math.max(Number(event.target.value), values.min) })}
        />
      </div>
    </section>
  );
}

function ProductGallery({ product }) {
  const media = Array.isArray(product?.images) ? product.images.slice(0, 10) : [];
  const [selectedMedia, setSelectedMedia] = useState("");
  const [hoveredMedia, setHoveredMedia] = useState("");
  const [lightboxMedia, setLightboxMedia] = useState("");
  const [zoomOrigin, setZoomOrigin] = useState({ x: 50, y: 50 });
  const activeMedia = media.includes(selectedMedia) ? selectedMedia : (media[0] || "");
  const hoverZoomed = hoveredMedia === activeMedia;
  const lightboxOpen = lightboxMedia === activeMedia;

  useEffect(() => {
    if (!lightboxOpen) return undefined;
    const previousOverflow = document.body.style.overflow;
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setLightboxMedia("");
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [lightboxOpen]);

  if (!media.length) {
    return <div className="live-store-detail-gallery"><div className="live-store-detail-main-image"><ProductImage product={product} /></div></div>;
  }

  const selectedIndex = media.indexOf(activeMedia);
  const activeUrl = resolveMediaUrl(activeMedia);
  const updateZoomOrigin = (event) => {
    if (!hoverZoomed) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return;
    setZoomOrigin({
      x: Math.max(0, Math.min(100, ((event.clientX - bounds.left) / bounds.width) * 100)),
      y: Math.max(0, Math.min(100, ((event.clientY - bounds.top) / bounds.height) * 100)),
    });
  };
  const chooseMedia = (item) => {
    setHoveredMedia("");
    setLightboxMedia("");
    setZoomOrigin({ x: 50, y: 50 });
    setSelectedMedia(item);
  };
  return (
    <div className="live-store-detail-gallery">
      <div className={`live-store-detail-main-image${!isVideoMediaUrl(activeMedia) ? " is-zoomable" : ""}`}>
        {isVideoMediaUrl(activeMedia)
          ? <video src={activeUrl} controls playsInline preload="metadata" aria-label={`${product.name} ${selectedIndex + 1}`} />
          : (
            <button
              type="button"
              className={`live-store-product-zoom-surface${hoverZoomed ? " is-hovered" : ""}`}
              onClick={() => setLightboxMedia(activeMedia)}
              onMouseEnter={() => setHoveredMedia(activeMedia)}
              onMouseLeave={() => {
                setHoveredMedia("");
                setZoomOrigin({ x: 50, y: 50 });
              }}
              onMouseMove={updateZoomOrigin}
              aria-label={c("product.openZoom")}
            >
              <img
                {...getResponsiveMediaProps(activeMedia, { sizes: "(max-width: 760px) 100vw, 58vw" })}
                alt={`${product.name} ${selectedIndex + 1}`}
                decoding="async"
                style={{ transformOrigin: `${zoomOrigin.x}% ${zoomOrigin.y}%` }}
              />
              <span className="live-store-product-zoom-indicator" aria-hidden="true">
                <ZoomIn size={20} />
              </span>
            </button>
          )}
      </div>
      {media.length > 1 && <div className="live-store-detail-thumbnails">{media.map((item, index) => { const video = isVideoMediaUrl(item); return <button type="button" className={index === selectedIndex ? "is-active" : ""} key={item} onClick={() => chooseMedia(item)} aria-label={c(video ? "product.showMedia" : "product.showImage", { count: index + 1 })}>{video ? <video src={resolveMediaUrl(item)} muted playsInline preload="metadata" /> : <img {...getResponsiveMediaProps(item, { fallbackWidth: 320, sizes: "120px" })} alt="" loading="lazy" decoding="async" />}</button>; })}</div>}
      {lightboxOpen && (
        <div
          className="live-store-product-lightbox"
          role="dialog"
          aria-modal="true"
          aria-label={c("product.imageZoom")}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setLightboxMedia("");
          }}
        >
          <button type="button" className="live-store-product-lightbox-close" onClick={() => setLightboxMedia("")} aria-label={c("product.closeZoom")}>
            <X size={24} aria-hidden="true" />
          </button>
          <img
            {...getResponsiveMediaProps(activeMedia, { sizes: "100vw" })}
            src={activeUrl}
            alt={`${product.name} ${selectedIndex + 1}`}
            decoding="async"
          />
        </div>
      )}
    </div>
  );
}

function StoreProductDetail({ detail, locale, shopPath, onAdd }) {
  const { product, category, tags = [], attributes = [], options = [], variants = [] } = detail;
  const [selection, setSelection] = useState({});
  const activeVariants = variants.filter((variant) => variant.active !== false);
  const selectedIds = Object.values(selection).filter(Boolean);
  const requiredComplete = options.filter((option) => option.required).every((option) => Boolean(selection[option.id]));
  const matchingVariants = activeVariants.filter((variant) => selectedIds.every((id) => variant.option_value_ids.includes(id)));
  const resolved = requiredComplete && matchingVariants.length === 1 ? matchingVariants[0] : undefined;
  const optionForValue = (valueId) => options.find((option) => option.values.some((value) => value.id === valueId));
  const detailsForVariant = (variant) => variant.option_value_ids.map((valueId) => {
    const option = optionForValue(valueId);
    const value = option?.values.find((item) => item.id === valueId);
    return option && value ? { option, value } : null;
  }).filter(Boolean);
  const inventoryCount = (item) => Math.max(0, Math.floor(Number(item?.inventory_quantity) || 0));
  const valueHasStock = (valueId) => activeVariants.some((variant) => variant.in_stock && variant.option_value_ids.includes(valueId));
  const possible = (optionId, valueId) => activeVariants.some((variant) => {
    if (!variant.in_stock || !variant.option_value_ids.includes(valueId)) return false;
    return Object.entries(selection).every(([selectedOptionId, selectedValueId]) => selectedOptionId === optionId || !selectedValueId || variant.option_value_ids.includes(selectedValueId));
  });
  const selectOption = (optionId, valueId) => setSelection((current) => {
    const next = { ...current, [optionId]: valueId };
    const compatible = activeVariants.some((variant) => variant.in_stock && Object.values(next).filter(Boolean).every((id) => variant.option_value_ids.includes(id)));
    return compatible ? next : { [optionId]: valueId };
  });
  const selectVariant = (variant) => {
    const next = {};
    detailsForVariant(variant).forEach(({ option, value }) => { next[option.id] = value.id; });
    setSelection(next);
  };
  const displayProduct = resolved ? { ...product, price: resolved.price, compare_at_price: resolved.compare_at_price, images: resolved.images?.length ? resolved.images : product.images, sku: resolved.sku, in_stock: resolved.in_stock, track_inventory: resolved.track_inventory, inventory_quantity: resolved.inventory_quantity, allow_backorder: resolved.allow_backorder } : product;
  const selectedOptions = resolved ? detailsForVariant(resolved).map(({ option, value }) => ({
    option_code: option.code, option_name: option.name, value_code: value.code, value: value.value,
  })) : [];
  const canAdd = options.length ? Boolean(resolved?.in_stock) : product.in_stock;
  const allVariantStockIsCounted = activeVariants.length > 0 && activeVariants.every((variant) => variant.track_inventory && !variant.allow_backorder);
  const exactStock = options.length
    ? (allVariantStockIsCounted ? activeVariants.reduce((total, variant) => total + inventoryCount(variant), 0) : null)
    : (product.track_inventory && !product.allow_backorder ? inventoryCount(product) : null);
  const availableVariantCount = activeVariants.filter((variant) => variant.in_stock).length;
  const stockText = exactStock === null
    ? c(product.in_stock ? "product.available" : "product.outOfStock")
    : c("product.itemsAvailable", { count: exactStock });
  return (
    <section className="live-store-detail">
      <ProductGallery product={displayProduct} />
      <div className="live-store-detail-copy">
        <Link className="live-store-back" to={shopPath}><ArrowLeft size={15} aria-hidden="true" />{c("product.back")}</Link>
        <p className="live-store-product-category">{[product.brand, category?.name].filter(Boolean).join(" / ")}</p>
        <h1>{product.name}</h1>
        <div className={`live-store-stock-summary ${product.in_stock ? "" : "is-sold-out"}`}>
          <strong>{stockText}</strong>
          {options.length > 0 && <span>{c("product.variantsAvailable", { available: availableVariantCount, total: activeVariants.length })}</span>}
        </div>
        {attributes.length > 0 && <section className="live-store-product-facts" aria-labelledby="product-specifications"><h2 id="product-specifications">{c("product.specifications")}</h2><dl className="live-store-attributes">{attributes.map((attribute) => <div key={attribute.id}><dt>{attribute.name}</dt><dd>{attribute.value}</dd></div>)}</dl></section>}
        <div className="live-store-detail-price">{formatPrice(displayProduct.price, product.currency, locale)}</div>
        {displayProduct.compare_at_price && <del className="live-store-detail-compare-price">{formatPrice(displayProduct.compare_at_price, product.currency, locale)}</del>}
        {product.description && <p>{product.description}</p>}
        {options.length > 0 && <div className="live-store-variant-options">{options.map((option) => <fieldset key={option.id}><legend>{option.name}{option.required ? " *" : ""}</legend><div>{option.values.map((value) => { const inStock = valueHasStock(value.id); const enabled = inStock && possible(option.id, value.id); return <button type="button" key={value.id} disabled={!inStock} className={`${selection[option.id] === value.id ? "is-active" : ""}${option.display_type === "color" ? " is-color" : ""}${!inStock ? " is-sold-out" : ""}${inStock && !enabled ? " is-incompatible" : ""}`} aria-label={value.value} aria-pressed={selection[option.id] === value.id} onClick={() => selectOption(option.id, value.id)}>{option.display_type === "color" && value.color_hex && <span className="live-store-color-swatch" style={{ backgroundColor: value.color_hex }} aria-hidden="true" />}<span>{value.value}</span>{!inStock && <small>{c("product.outOfStock")}</small>}</button>; })}</div></fieldset>)}</div>}
        {activeVariants.length > 0 && <section className="live-store-variant-inventory" aria-labelledby="variant-inventory-heading">
          <header><h2 id="variant-inventory-heading">{c("product.variantsStock")}</h2><span>{availableVariantCount}/{activeVariants.length}</span></header>
          <div className="live-store-variant-list">
            {activeVariants.map((variant) => {
              const variantDetails = detailsForVariant(variant);
              const quantity = variant.track_inventory ? inventoryCount(variant) : null;
              const label = variantDetails.map(({ value }) => value.value).join(" / ") || variant.sku;
              const quantityText = quantity === null ? c("product.available") : c("product.itemsAvailable", { count: quantity });
              return <button type="button" key={variant.id} disabled={!variant.in_stock} className={`live-store-variant-card ${resolved?.id === variant.id ? "is-active" : ""} ${variant.in_stock ? "" : "is-sold-out"}`} aria-label={c("product.selectVariant", { variant: label, stock: variant.in_stock ? quantityText : c("product.outOfStock") })} aria-pressed={resolved?.id === variant.id} onClick={() => selectVariant(variant)}>
                <span className="live-store-variant-card-values">{variantDetails.map(({ option, value }) => <span key={value.id}>{option.display_type === "color" && value.color_hex && <i className="live-store-color-swatch" style={{ backgroundColor: value.color_hex }} aria-hidden="true" />}<span><small>{option.name}</small><strong>{value.value}</strong></span></span>)}</span>
                <span className="live-store-variant-card-stock"><strong>{quantityText}</strong>{!variant.in_stock && <small>{c("product.outOfStock")}</small>}{variant.allow_backorder && quantity === 0 && <small>{c("product.availableToOrder")}</small>}</span>
              </button>;
            })}
          </div>
        </section>}
        {options.length > 0 && !resolved && <p className="live-store-variant-help">{c("product.requiredHelp")}</p>}
        {resolved && <p className="live-store-variant-meta"><bdi>{c("common.sku")} {resolved.sku}</bdi> · {resolved.in_stock ? c("product.available") : c("product.outOfStock")}</p>}
        <button type="button" disabled={!canAdd} onClick={() => onAdd({ ...displayProduct, variant_id: resolved?.id, selected_options: selectedOptions })}><ShoppingBag size={18} />{canAdd ? c("product.addToCart") : resolved ? c("product.outOfStock") : options.length ? c("product.chooseOptions") : c("product.outOfStock")}</button>
        {tags.length > 0 && <div className="live-store-detail-tags">{tags.map((item) => <span key={item.id}>{item.name}</span>)}</div>}
      </div>
    </section>
  );
}


function ProductCard({ product, locale, productPath, onAdd, eager = false }) {
  return (
    <article className="live-store-product-card">
      <Link className="live-store-product-image" to={productPath}>
        <ProductImage product={product} eager={eager} />
        <span className="live-store-product-view">{c("common.products")}</span>
      </Link>
      <div className="live-store-product-body">
        <h2><Link to={productPath}>{product.name}</Link></h2>
        {product.variant_options?.length > 0 && (
          <div className="live-store-product-variant-preview" aria-label={c("product.variantsAvailable", { available: product.variant_options.reduce((total, option) => total + option.values.length, 0), total: product.variant_options.reduce((total, option) => total + option.values.length, 0) })}>
            {product.variant_options.flatMap((option) => option.values.map((value) => (
              <span key={`${option.id}:${value}`} title={option.name}>{value}</span>
            )))}
          </div>
        )}
        <div className="live-store-product-bottom">
          <div className="live-store-price-row">
            <strong>{formatPrice(product.price, product.currency, locale)}</strong>
            {product.compare_at_price && (
              <del>{formatPrice(product.compare_at_price, product.currency, locale)}</del>
            )}
          </div>
          {product.has_variants ? <Link className="live-store-product-options" to={productPath}>{c("product.chooseOptions")}</Link> : <button type="button" disabled={!product.in_stock} onClick={() => onAdd(product)}>
            <ShoppingBag size={16} aria-hidden="true" />
            {product.in_stock ? c("product.addToCart") : c("product.outOfStock")}
          </button>}
        </div>
      </div>
    </article>
  );
}

function CategoryCarousel({ categories, shopPath, categoriesPath, kind = "category" }) {
  const trackRef = useRef(null);
  const loopResetRef = useRef(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const rtl = activeLocale() === "ar";
  const isBrandCarousel = kind === "brand";
  const carouselTitle = isBrandCarousel ? c("catalog.brands") : c("common.categories");
  const filterKey = isBrandCarousel ? "brand" : "category";
  const viewAllPath = isBrandCarousel ? shopPath : categoriesPath;
  const categoryCount = categories.length;
  const loopedCategories = categoryCount > 1
    ? [-1, 0, 1].flatMap((group) => categories.map((category, index) => ({ category, index, group })))
    : categories.map((category, index) => ({ category, index, group: 0 }));
  const scrollToItem = useCallback((renderIndex, behavior = "smooth") => {
    const track = trackRef.current;
    const item = track?.children[renderIndex];
    if (!track || !item) return;
    const trackRect = track.getBoundingClientRect();
    const itemRect = item.getBoundingClientRect();
    const left = rtl ? itemRect.right - trackRect.right : itemRect.left - trackRect.left;
    if (typeof track.scrollBy === "function") track.scrollBy({ left, behavior });
    else track.scrollLeft += left;
  }, [rtl]);
  const scheduleLoopReset = useCallback((renderIndex, categoryIndex, delay = 220) => {
    if (renderIndex >= categoryCount && renderIndex < categoryCount * 2) return;
    window.clearTimeout(loopResetRef.current);
    loopResetRef.current = window.setTimeout(
      () => scrollToItem(categoryCount + categoryIndex, "auto"),
      delay,
    );
  }, [categoryCount, scrollToItem]);
  useLayoutEffect(() => {
    if (categoryCount > 1) scrollToItem(categoryCount, "auto");
    return () => window.clearTimeout(loopResetRef.current);
  }, [categoryCount, scrollToItem]);
  const move = useCallback((step) => {
    if (categoryCount < 2) return;
    window.clearTimeout(loopResetRef.current);
    const nextIndex = (activeIndex + step + categoryCount) % categoryCount;
    const crossesEnd = step > 0 && activeIndex === categoryCount - 1;
    const crossesStart = step < 0 && activeIndex === 0;
    const renderIndex = crossesEnd
      ? categoryCount * 2
      : crossesStart
        ? categoryCount - 1
        : categoryCount + nextIndex;
    setActiveIndex(nextIndex);
    scrollToItem(renderIndex);
    if (crossesEnd || crossesStart) scheduleLoopReset(renderIndex, nextIndex, 520);
  }, [activeIndex, categoryCount, scheduleLoopReset, scrollToItem]);
  useEffect(() => {
    const prefersReducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (categoryCount < 2 || prefersReducedMotion) return undefined;
    const timer = window.setInterval(() => move(1), 5000);
    return () => window.clearInterval(timer);
  }, [categoryCount, move]);
  const syncActiveIndex = () => {
    const track = trackRef.current;
    if (!track) return;
    const trackRect = track.getBoundingClientRect();
    const trackEdge = rtl ? trackRect.right : trackRect.left;
    let nearestIndex = 0;
    let nearestRenderIndex = categoryCount;
    let nearestDistance = Number.POSITIVE_INFINITY;
    Array.from(track.children).forEach((item, index) => {
      const itemRect = item.getBoundingClientRect();
      const itemEdge = rtl ? itemRect.right : itemRect.left;
      const distance = Math.abs(itemEdge - trackEdge);
      if (distance < nearestDistance) {
        nearestIndex = Number(item.dataset.categoryIndex || 0);
        nearestRenderIndex = index;
        nearestDistance = distance;
      }
    });
    setActiveIndex(nearestIndex);
    scheduleLoopReset(nearestRenderIndex, nearestIndex);
  };
  const previousLabel = c(isBrandCarousel ? "catalog.previousBrands" : "catalog.previousCategories");
  const nextLabel = c(isBrandCarousel ? "catalog.nextBrands" : "catalog.nextCategories");

  return (
    <section className={`live-store-landing-section live-store-category-section${isBrandCarousel ? " live-store-brand-section" : ""}`} aria-label={carouselTitle}>
      <header>
        <div><h2>{carouselTitle}</h2></div>
        <div className="live-store-category-header-actions">
          <Link to={viewAllPath}>{c("common.viewAll")} <ArrowRight size={17} aria-hidden="true" /></Link>
        </div>
      </header>
      <div className="live-store-category-stage">
        {categories.length > 1 && (
          <button className="live-store-category-side-control is-previous" type="button" onClick={() => move(-1)} aria-label={previousLabel}>
            {rtl ? <ChevronRight size={24} aria-hidden="true" /> : <ChevronLeft size={24} aria-hidden="true" />}
          </button>
        )}
        <ul className="live-store-category-carousel" ref={trackRef} onScroll={syncActiveIndex} style={{ "--store-carousel-columns": Math.min(5, Math.max(1, categories.length)), "--store-carousel-tablet-columns": Math.min(3, Math.max(1, categories.length)) }}>
          {loopedCategories.map(({ category, index, group }) => (
            <li
              key={`${group}-${category.id}`}
              data-category-index={index}
              aria-hidden={group === 0 ? undefined : "true"}
            >
              <Link to={`${shopPath}?${filterKey}=${encodeURIComponent(category.slug)}`} tabIndex={group === 0 ? undefined : -1}>
                <div className={`live-store-category-media${category.image_url ? "" : " is-placeholder"}`}>
                  {category.image_url
                    ? <img {...getResponsiveMediaProps(category.image_url, { widths: [240, 320, 480, 640], fallbackWidth: 480, sizes: "(max-width: 760px) 50vw, (max-width: 980px) 33vw, 20vw" })} alt="" loading={index < 5 ? "eager" : "lazy"} decoding="async" />
                    : <span>{String(index + 1).padStart(2, "0")}</span>}
                </div>
                <div className="live-store-category-copy">
                  <div><h3>{category.name}</h3></div>
                  <ArrowRight size={20} aria-hidden="true" />
                </div>
              </Link>
            </li>
          ))}
        </ul>
        {categories.length > 1 && (
          <button className="live-store-category-side-control is-next" type="button" onClick={() => move(1)} aria-label={nextLabel}>
            {rtl ? <ChevronLeft size={24} aria-hidden="true" /> : <ChevronRight size={24} aria-hidden="true" />}
          </button>
        )}
      </div>
    </section>
  );
}


function StoreLanding({ brand, site, catalog, categoryById, locale, shopPath, productBasePath, onAdd }) {
  const selectedProductIds = site?.growth?.featured_product_ids || [];
  const selectedCategoryIds = site?.growth?.featured_category_ids || [];
  const featuredProducts = (selectedProductIds.length ? catalog.featured_products : catalog.products).slice(0, 12);
  const featuredBrands = (catalog.brands || []).slice(0, 6);
  const featuredCategories = (selectedCategoryIds.length ? catalog.featured_categories : catalog.categories.filter((item) => !item.parent_id)).slice(0, 6);
  const leadProduct = featuredProducts[0];
  const productTotal = Number(catalog.pagination?.total || catalog.products.length || 0);

  return (
    <div className="live-store-landing">
      <section className="live-store-landing-hero">
        <div className="live-store-landing-copy">
          <h1 className="live-store-welcome-title">{brand}</h1>
          {site?.description && <p>{site.description}</p>}
          <div className="live-store-landing-actions">
            <Link className="live-store-primary-link" to={shopPath}>{c("landing.browse")} <ArrowRight size={18} /></Link>
            {featuredCategories[0] && <Link className="live-store-text-link" to={`${shopPath}?category=${encodeURIComponent(featuredCategories[0].slug)}`}>{c("landing.shopCategory", { name: featuredCategories[0].name })}</Link>}
          </div>
          {(productTotal > 0 || catalog.categories.length > 0) && (
            <dl className="live-store-landing-facts">
              {productTotal > 0 && <div><dt>{productTotal}</dt><dd>{c("landing.products")}</dd></div>}
              {catalog.categories.length > 0 && <div><dt>{catalog.categories.length}</dt><dd>{c("landing.collections")}</dd></div>}
            </dl>
          )}
        </div>
        <div className="live-store-landing-visual">
          {leadProduct ? (
            <Link to={`${productBasePath}/product/${encodeURIComponent(leadProduct.slug)}`}>
              <ProductImage product={leadProduct} eager />
              <span><small>{c("landing.featured")}</small><strong>{leadProduct.name}</strong><b>{formatPrice(leadProduct.price, leadProduct.currency, locale)}</b></span>
            </Link>
          ) : (
            <div className="live-store-landing-placeholder"><ShoppingBag size={42} aria-label="No featured product" /></div>
          )}
        </div>
      </section>

      {featuredBrands.length > 0 && (
        <CategoryCarousel
          categories={featuredBrands}
          shopPath={shopPath}
          categoriesPath={shopPath}
          kind="brand"
        />
      )}

      {featuredCategories.length > 0 && (
        <CategoryCarousel
          categories={featuredCategories}
          shopPath={shopPath}
          categoriesPath={`${productBasePath}/categories`}
        />
      )}

      <section className="live-store-landing-section live-store-featured-section">
        <header><div><h2>{c("common.products")}</h2></div><Link to={shopPath}>{c("common.viewAll")} <ArrowRight size={17} /></Link></header>
        {featuredProducts.length > 0 ? (
          <div className="live-store-grid">
            {featuredProducts.map((product, index) => (
              <ProductCard key={product.id} product={product} category={categoryById.get(product.category_id)} locale={locale} productPath={`${productBasePath}/product/${encodeURIComponent(product.slug)}`} onAdd={onAdd} eager={index < 3} />
            ))}
          </div>
        ) : (
          <div className="live-store-landing-empty"><ShoppingBag size={30} /><h3>{c("landing.noPublished")}</h3></div>
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
  const { i18n: commerceI18n } = useTranslation("commerce");
  const locale = normalizeCommerceLocale(commerceI18n.resolvedLanguage || commerceI18n.language);
  const canonicalStorePath = suppliedBasePath === "/shop" ? "/shop" : `/site/${encodeURIComponent(subdomain)}/shop`;
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
  const confirmationToken = routeTail.match(/^confirmation\/([0-9a-f]{64})\/?$/)?.[1] || "";
  const confirmationRoute = Boolean(confirmationToken);
  const urlFilters = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const [draftPreviewMode] = useState(() => new URLSearchParams(window.location.search).get("preview") === "draft");
  const [draftTheme, setDraftTheme] = useState(() => draftPreviewMode ? readThemePreview() : null);
  const [catalog, setCatalog] = useState(EMPTY_CATALOG);
  const [site, setSite] = useState(null);
  const siteRef = useRef(null);
  const [productDetail, setProductDetail] = useState(null);
  const [confirmation, setConfirmation] = useState(null);
  const [loyalty, setLoyalty] = useState(null);
  const [normalDiscounts, setNormalDiscounts] = useState([]);
  const [delivery, setDelivery] = useState({ loading: false, error: "", areas: [] });
  const [selectedAreaId, setSelectedAreaId] = useState("");
  const [requestStatus, setRequestStatus] = useState({
    key: "",
    loading: true,
    error: "",
  });
  const cartKey = `madar-store-cart:${subdomain}`;
  const [cart, setCart] = useState(() => readCart(cartKey));
  const [cartOpen, setCartOpen] = useState(false);
  const [notification, setNotification] = useState(null);
  const notify = useCallback((value) => setNotification({ ...value }), []);
  const dismissNotification = useCallback(() => setNotification(null), []);
  const orderAttemptRef = useRef({ fingerprint: "", key: "" });
  const analyticsViewsRef = useRef(new Set());
  const recordedVisitRef = useRef("");

  useEffect(() => {
    if (!subdomain || draftPreviewMode) return;
    const visitKey = `store:${subdomain}`;
    if (recordedVisitRef.current === visitKey) return;
    recordedVisitRef.current = visitKey;
    recordPublicSiteVisit(subdomain, "store").catch(() => {});
  }, [draftPreviewMode, subdomain]);

  const filters = {
    search: urlFilters.get("search") || "",
    category: urlFilters.get("category") || "",
    brand: urlFilters.get("brand") || "",
    tag: urlFilters.get("tag") || "",
    minPrice: urlFilters.get("min_price") || "",
    maxPrice: urlFilters.get("max_price") || "",
    sort: urlFilters.get("sort") || "latest",
    page: urlFilters.get("page") || "1",
    locale,
  };

  const hasCatalogFilters = Boolean(filters.search || filters.category || filters.brand || filters.tag || filters.minPrice || filters.maxPrice || filters.page !== "1" || filters.sort !== "latest");
  const landingRoute = routeTail === "";
  const isLanding = landingRoute && !hasCatalogFilters;
  const isCatalogView = catalogRoute || (landingRoute && hasCatalogFilters);

  const requestKey = JSON.stringify([
    subdomain,
    productSlug,
    filters.search,
    filters.category,
    filters.brand,
    filters.tag,
    filters.minPrice,
    filters.maxPrice,
    filters.sort,
    filters.page,
    locale,
    contactRoute,
    checkoutRoute,
    confirmationToken,
    notify,
  ]);
  const loading = requestStatus.key !== requestKey || requestStatus.loading;
  const error = requestStatus.key === requestKey ? requestStatus.error : "";

  useEffect(() => {
    let cancelled = false;
    const request = confirmationToken
      ? fetchPublicEcommerceOrderConfirmation(subdomain, confirmationToken)
      : productSlug
      ? fetchPublicEcommerceProduct(subdomain, productSlug, locale)
      : contactRoute || checkoutRoute
        ? fetchPublicEcommerceProfile(subdomain)
        : fetchPublicEcommerceCatalog(subdomain, {
          search: filters.search,
          category: filters.category,
          brand: filters.brand,
          tag: filters.tag,
          min_price: filters.minPrice,
          max_price: filters.maxPrice,
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
        if (confirmationToken) {
          setConfirmation(result || null);
          setProductDetail(null);
        } else if (productSlug) {
          setProductDetail(result || null);
        } else {
          setCatalog(result?.catalog || EMPTY_CATALOG);
          setProductDetail(null);
        }
        setRequestStatus({ key: requestKey, loading: false, error: "" });
      })
      .catch(() => {
        if (!cancelled) {
          setRequestStatus({
            key: requestKey,
            loading: false,
            error: c("errors.loadStore"),
          });
          notify({ type: "error", title: c("errors.loadStore"), message: c("admin.tryAgain") });
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
    filters.sort,
    filters.page,
    requestKey,
    contactRoute,
    checkoutRoute,
    filters.category,
    filters.brand,
    filters.tag,
    filters.minPrice,
    filters.maxPrice,
    confirmationToken,
    notify,
  ]);

  useEffect(() => {
    let cancelled = false;
    fetchPublicEcommerceLoyalty(subdomain)
      .then((result) => { if (!cancelled) setLoyalty(result); })
      .catch(() => { if (!cancelled) setLoyalty(null); });
    fetchPublicEcommerceDiscounts(subdomain)
      .then((result) => { if (!cancelled) setNormalDiscounts(result?.conditions || []); })
      .catch(() => { if (!cancelled) { setNormalDiscounts([]); notify({ type: "error", title: c("storeFeedback.discountsUnavailable"), message: c("storeFeedback.discountsUnavailableBody") }); } });
    return () => { cancelled = true; };
  }, [subdomain, confirmationToken, notify]);

  useEffect(() => {
    if (!subdomain || (!cartOpen && !checkoutRoute)) return undefined;
    let cancelled = false;
    queueMicrotask(() => {
      if (!cancelled) setDelivery((current) => ({ ...current, loading: true, error: "" }));
    });
    fetchPublicEcommerceDeliveryAreas(subdomain)
      .then((result) => {
        if (cancelled) return;
        const areas = result?.areas || [];
        setDelivery({ loading: false, error: "", areas });
        setSelectedAreaId((current) => areas.some((area) => area.id === current) ? current : areas[0]?.id || "");
      })
      .catch(() => {
        if (!cancelled) {
          setDelivery({ loading: false, error: c("storeFeedback.deliveryUnavailable"), areas: [] });
          notify({ type: "error", title: c("storeFeedback.deliveryUnavailable"), message: c("admin.tryAgain") });
        }
      });
    return () => { cancelled = true; };
  }, [cartOpen, checkoutRoute, notify, subdomain]);

  useEffect(() => {
    if (loading || error || !productDetail?.product) return;
    const product = productDetail.product; const key = `item:${locale}:${product.id}`;
    if (analyticsViewsRef.current.has(key)) return;
    analyticsViewsRef.current.add(key);
    trackCommerceEvent("view_item", { product_id: product.id, price: Number(product.price || 0), currency: product.currency, locale });
  }, [error, loading, locale, productDetail]);

  useEffect(() => {
    if (loading || error || (!isLanding && !isCatalogView) || !catalog.products.length) return;
    const key = `list:${locale}:${filters.category}:${filters.brand}:${filters.tag}:${filters.search}:${filters.page}`;
    if (analyticsViewsRef.current.has(key)) return;
    analyticsViewsRef.current.add(key);
    trackCommerceEvent("view_item_list", { store: subdomain, list: filters.category || "catalog", product_ids: catalog.products.map((item) => item.id), currency: catalog.products[0]?.currency, locale });
  }, [catalog.products, error, filters.brand, filters.category, filters.page, filters.search, filters.tag, isCatalogView, isLanding, loading, locale, subdomain]);

  const announcementText = String(site?.growth?.[locale === "ar" ? "announcement_text_ar" : "announcement_text_en"] || site?.growth?.announcement_text_en || site?.growth?.announcement_text_ar || "").trim();
  const announcementLink = safePublicUrl(site?.growth?.announcement_link, window.location.origin);
  useEffect(() => {
    if (!site?.growth?.announcement_enabled || !announcementText) return;
    const key = `promotion:${locale}:${announcementText}`;
    if (analyticsViewsRef.current.has(key)) return;
    analyticsViewsRef.current.add(key);
    trackCommerceEvent("promotion_view", { store: subdomain, locale, placement: "announcement" });
  }, [announcementText, locale, site?.growth?.announcement_enabled, subdomain]);

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
    navigate(`${shopPath}${next.toString() ? `?${next}` : ""}`, {
      preventScrollReset: true,
      state: { preserveScroll: true },
    });
  };

  const setPriceFilters = (rawMinimum, rawMaximum) => {
    const normalizePrice = (value) => {
      if (String(value ?? "").trim() === "") return "";
      const parsed = Number(value);
      return Number.isFinite(parsed) && parsed >= 0 ? String(parsed) : "";
    };
    let minimum = normalizePrice(rawMinimum);
    let maximum = normalizePrice(rawMaximum);
    if (minimum && maximum && Number(minimum) > Number(maximum)) {
      [minimum, maximum] = [maximum, minimum];
    }
    const next = new URLSearchParams(location.search);
    if (minimum) next.set("min_price", minimum);
    else next.delete("min_price");
    if (maximum) next.set("max_price", maximum);
    else next.delete("max_price");
    next.delete("page");
    navigate(`${shopPath}${next.toString() ? `?${next}` : ""}`, {
      preventScrollReset: true,
      state: { preserveScroll: true },
    });
  };

  const cartItems = useMemo(() => Array.from(cart.reduce((items, item) => {
    const key = cartLineKey(item); const current = items.get(key);
    items.set(key, { ...current, ...item, quantity: (current?.quantity || 0) + Number(item.quantity || 1) });
    return items;
  }, new Map()).values()), [cart]);
  const cartCount = cartItems.reduce((total, item) => total + item.quantity, 0);

  const saveCart = (next) => {
    try {
      localStorage.setItem(cartKey, JSON.stringify(next));
      setCart(next);
      return true;
    } catch {
      notify({ type: "error", title: c("storeFeedback.cartUnavailable"), message: c("storeFeedback.cartUnavailableBody") });
      return false;
    }
  };

  const addToCart = (product) => {
    const identity = cartLineKey(product); const existing = cartItems.find((item) => cartLineKey(item) === identity);
    if (existing?.quantity >= 99) {
      notify({ type: "error", title: c("storeFeedback.quantityLimit"), message: c("storeFeedback.quantityLimitBody") });
      return;
    }
    const nextItem = {
      id: product.id,
      slug: product.slug,
      name: product.name,
      quantity: Math.min(99, (existing?.quantity || 0) + 1),
      price: product.price,
      currency: product.currency,
      variant_id: product.variant_id || null,
      selected_options: product.selected_options || [],
      images: product.images || [],
    };
    trackCommerceEvent("add_to_cart", { product_id: product.id, variant_id: product.variant_id || null, quantity: 1, amount: Number(product.price || 0), currency: product.currency, locale, selected_options: (product.selected_options || []).map((item) => ({ option_code: item.option_code, value_code: item.value_code })) });
    if (saveCart([...cartItems.filter((item) => cartLineKey(item) !== identity), nextItem])) notify({ type: "success", title: c("storeFeedback.added"), message: c("storeFeedback.addedBody", { name: product.name }) });
  };

  const removeCartItem = (id) => {
    const removed = cartItems.find((item) => cartLineKey(item) === id);
    if (removed) trackCommerceEvent("remove_from_cart", { product_id: removed.id, variant_id: removed.variant_id || null, quantity: removed.quantity, currency: removed.currency, locale });
    if (saveCart(cartItems.filter((item) => cartLineKey(item) !== id))) notify({ type: "success", title: c("storeFeedback.removed"), message: c("storeFeedback.removedBody") });
  };
  const openCart = () => {
    trackCommerceEvent("view_cart", { item_count: cartCount, subtotal: cartItems.reduce((sum, item) => sum + Number(item.price || 0) * item.quantity, 0), currency: cartItems[0]?.currency || site?.commerce_currency, locale });
    setCartOpen(true);
  };

  const changeCartQuantity = (id, quantity) => {
    if (quantity < 1) {
      removeCartItem(id);
      return;
    }
      const removed = cartItems.find((item) => cartLineKey(item) === id);
      if (removed) trackCommerceEvent("remove_from_cart", { product_id: removed.id, variant_id: removed.variant_id || null, quantity: removed.quantity, currency: removed.currency, locale });
    if (quantity > 99) {
      notify({ type: "error", title: c("storeFeedback.quantityLimit"), message: c("storeFeedback.quantityLimitBody") });
      return;
    }
    if (saveCart(cartItems.map((item) => cartLineKey(item) === id ? { ...item, quantity } : item))) notify({ type: "success", title: c("storeFeedback.quantityUpdated"), message: c("storeFeedback.quantityUpdatedBody") });
  };

  const placeOrder = async (payload) => {
    if (!Array.isArray(payload.items) || payload.items.length < 1 || payload.items.length > 50 ||
      payload.items.some(item => !Number.isInteger(item.quantity) || item.quantity < 1 || item.quantity > 99)) {
      throw new StorefrontActionError("cart.changed");
    }
    const reconciliation = await reconcilePublicEcommerceCart(subdomain, payload.items);
    if (!reconciliation?.valid) {
      throw new StorefrontActionError("cart.changed");
    }
    const reconciledById = new Map((reconciliation.items || []).map((item) => [`${item.product_id}:${item.variant_id || "simple"}`, item]));
    const refreshedCart = cartItems.map((item) => {
      const current = reconciledById.get(cartLineKey(item));
      return current ? { ...item, name: current.name || item.name, slug: current.slug || item.slug, images: current.images || item.images, price: current.price, currency: current.currency } : item;
    });
    const pricesChanged = refreshedCart.some((item, index) =>
      String(item.price) !== String(cartItems[index]?.price) || item.currency !== cartItems[index]?.currency
    );
    if (pricesChanged) {
      saveCart(refreshedCart);
      throw new StorefrontActionError("cart.priceChanged");
    }
    const fingerprint = JSON.stringify(payload);
    if (orderAttemptRef.current.fingerprint !== fingerprint) {
      orderAttemptRef.current = {
        fingerprint,
        key: globalThis.crypto?.randomUUID?.() || `checkout-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      };
    }
    const result = await createPublicEcommerceOrder(subdomain, {
      ...payload,
      idempotency_key: orderAttemptRef.current.key,
    });
    if (!result?.confirmation_token) throw new StorefrontActionError("errors.confirmationUnavailable");
    orderAttemptRef.current = { fingerprint: "", key: "" };
    saveCart([]);
    return result;
  };

  const categoryById = useMemo(
    () => new Map(catalog.categories.map((item) => [item.id, item])),
    [catalog.categories]
  );
  const priceBounds = useMemo(() => {
    if (catalog.price_bounds?.min != null && catalog.price_bounds?.max != null) return catalog.price_bounds;
    const prices = catalog.products.map((item) => Number(item.price)).filter(Number.isFinite);
    return prices.length
      ? { min: Math.min(...prices), max: Math.max(...prices), currency: catalog.products[0]?.currency || "USD" }
      : { min: 0, max: 0, currency: "USD" };
  }, [catalog.price_bounds, catalog.products]);
  const brand = (locale === "ar" && site?.brand_ar?.trim()) || site?.brand || site?.footer_store_name || "";
  const description = (locale === "ar" && site?.description_ar?.trim()) || site?.description || "";
  const localizedSite = site ? { ...site, brand, description } : site;
  const socialLinks = STORE_SOCIAL_NETWORKS
    .map(([key, label]) => ({ key, label, href: String(site?.social_links?.[key] || "").trim() }));
  const activeCategory = catalog.categories.find((item) => item.slug === filters.category) || null;
  const seoView = error || (filters.category && !activeCategory) ? "missing" : draftPreviewMode ? "preview" : confirmationRoute ? "confirmation" : checkoutRoute ? "checkout" : productSlug ? (productDetail?.product ? "product" : "missing") : categoriesRoute ? "categories" : isCatalogView ? "catalog" : contactRoute ? "contact" : "home";
  const savedTheme = normalizeStoreTheme(draftTheme || site?.store_theme || site?.theme);
  const storeStyle = {
    "--store-accent": savedTheme.accent,
    "--store-paper": savedTheme.background,
    "--store-soft": savedTheme.softSurface || savedTheme.surface,
    "--store-ink": savedTheme.text,
    "--store-muted": savedTheme.muted,
    "--store-night": savedTheme.accentDark || savedTheme.text,
  };
  const catalogRefreshing = loading && isCatalogView && Boolean(requestStatus.key);

  useLayoutEffect(() => {
    const root = document.documentElement;
    const body = document.body;
    const previous = { rootDir: root.getAttribute("dir"), rootLang: root.getAttribute("lang"), bodyDir: body?.getAttribute("dir") };
    root.setAttribute("dir", locale === "ar" ? "rtl" : "ltr");
    root.setAttribute("lang", locale);
    body?.setAttribute("dir", locale === "ar" ? "rtl" : "ltr");
    return () => {
      if (previous.rootDir === null) root.removeAttribute("dir"); else root.setAttribute("dir", previous.rootDir);
      if (previous.rootLang === null) root.removeAttribute("lang"); else root.setAttribute("lang", previous.rootLang);
      if (body) { if (previous.bodyDir === null) body.removeAttribute("dir"); else body.setAttribute("dir", previous.bodyDir); }
    };
  }, [locale]);

  return (
    <div className="live-store" style={storeStyle} dir={locale === "ar" ? "rtl" : "ltr"} lang={locale}>
      <StorefrontSeo origin={window.location.origin} storePath={canonicalStorePath} locale={locale} site={site} productDetail={productDetail} category={activeCategory} view={seoView} />
      <StoreHeader brand={brand} logoUrl={site?.logo_url} cartCount={cartCount} shopPath={shopPath} homePath={homePath} categoriesPath={categoriesPath} contactPath={contactPath} onCartOpen={openCart} />
      {site?.growth?.announcement_enabled && announcementText && <div className="live-store-announcement" role="status">{announcementLink ? <a href={announcementLink} onClick={() => trackCommerceEvent("promotion_click", { store: subdomain, locale, placement: "announcement" })}>{announcementText}</a> : <span>{announcementText}</span>}</div>}
      <StoreActionToast notification={notification} onDismiss={dismissNotification} locale={locale} />
      <StoreWhatsAppLink phone={site?.phone} brand={brand} />
      <StoreCart open={cartOpen} items={cartItems} homePath={homePath} checkoutPath={checkoutPath} delivery={delivery} selectedAreaId={selectedAreaId} onSelectedAreaChange={setSelectedAreaId} loyalty={loyalty} normalDiscounts={normalDiscounts} onClose={() => setCartOpen(false)} onQuantityChange={changeCartQuantity} onRemove={removeCartItem} />
      {loyalty && <section className="live-store-loyalty" aria-label={c("loyalty.title")}>
        <Gift size={20} aria-hidden="true" />
        <div><strong>{c("loyalty.balance")}: {loyalty.account?.current_balance || 0}</strong>
          {(loyalty.entitlements || []).find((item) => item.status === "active") && <small>
            {c("loyalty.activeReward")}: {c("loyalty.appliedDiscount")} · {
              (loyalty.entitlements || []).find((item) => item.status === "active")?.expires_at
                ? c("loyalty.expires", { date: new Intl.DateTimeFormat(activeLocale()).format(new Date((loyalty.entitlements || []).find((item) => item.status === "active").expires_at)) })
                : c("loyalty.rewardLifetime")
            }
          </small>}
        </div>
      </section>}
      <main>

        {loading && !catalogRefreshing && <StoreSkeleton view={productSlug ? "product" : categoriesRoute ? "categories" : contactRoute ? "contact" : checkoutRoute ? "catalog" : isLanding ? "landing" : "catalog"} />}
        {!loading && error && <div className="live-store-state is-error"><h2>{c("errors.storeUnavailable")}</h2><p>{error}</p></div>}

        {!loading && !error && isLanding && (
          <StoreLanding brand={brand} site={localizedSite} catalog={catalog} categoryById={categoryById} locale={locale} shopPath={shopPath} productBasePath={homePath} onAdd={addToCart} />
        )}

        {!loading && !error && categoriesRoute && (
          <StoreCategories categories={catalog.categories} shopPath={shopPath} />
        )}

        {!loading && !error && contactRoute && (
          <StoreContact brand={brand} site={localizedSite} />
        )}

        {!loading && !error && checkoutRoute && (
          <StoreCheckout items={cartItems} loyalty={loyalty} normalDiscounts={normalDiscounts} shopPath={shopPath} storePath={storePath} delivery={delivery} selectedAreaId={selectedAreaId} onSelectedAreaChange={setSelectedAreaId} onPlaceOrder={placeOrder} onNotify={notify} />
        )}

        {!loading && !error && confirmationRoute && (
          <StoreConfirmation data={confirmation} shopPath={shopPath} />
        )}

        {!loading && !error && productSlug && productDetail?.product && <StoreProductDetail key={productDetail.product.id} detail={productDetail} locale={locale} shopPath={shopPath} onAdd={addToCart} />}

        {(!loading || catalogRefreshing) && !error && !productSlug && !checkoutRoute && isCatalogView && (
          <section className={`live-store-catalog-page${catalogRefreshing ? " is-refreshing" : ""}`} aria-busy={catalogRefreshing}>
            <header className="live-store-page-heading">
              <h1>{c("catalog.title")}</h1>
            </header>
            <div className="live-store-shell">
              <aside>
              <form className="live-store-search" onSubmit={(event) => { event.preventDefault(); const value = new FormData(event.currentTarget).get("search"); setFilter("search", typeof value === "string" ? value : ""); }}>
                <input key={filters.search} name="search" defaultValue={filters.search} placeholder={c("catalog.searchPlaceholder")} aria-label={c("catalog.searchProducts")} />
                <button type="submit" aria-label={c("common.search")}><Search size={18} /></button>
              </form>
              <div className="live-store-filter-card"><h2>{c("common.categories")}</h2><CategoryList categories={catalog.categories} activeSlug={filters.category} onSelect={(value) => setFilter("category", value)} /></div>
              {catalog.brands?.length > 0 && <div className="live-store-filter-card"><h2>{c("catalog.brands")}</h2><div className="live-store-tags"><button type="button" className={!filters.brand ? "is-active" : ""} onClick={() => setFilter("brand", "")}>{c("catalog.allBrands")}</button>{catalog.brands.map((item) => <button type="button" key={item.id} className={filters.brand === item.slug ? "is-active" : ""} onClick={() => setFilter("brand", filters.brand === item.slug ? "" : item.slug)}>{item.name}</button>)}</div></div>}
              <PriceRangeFilter key={`${priceBounds.min}:${priceBounds.max}:${filters.minPrice}:${filters.maxPrice}`} bounds={priceBounds} minimum={filters.minPrice} maximum={filters.maxPrice} locale={locale} onChange={setPriceFilters} />
              {catalog.tags.length > 0 && <div className="live-store-filter-card"><h2>{c("common.tags")}</h2><div className="live-store-tags">{catalog.tags.map((item) => <button type="button" key={item.id} className={filters.tag === item.slug ? "is-active" : ""} onClick={() => setFilter("tag", filters.tag === item.slug ? "" : item.slug)}>{item.name}</button>)}</div></div>}
            </aside>
            <div className="live-store-results">
              <div className="live-store-toolbar"><p>{c("catalog.showing", { count: catalog.pagination.total })}</p><select value={filters.sort} onChange={(event) => setFilter("sort", event.target.value)} aria-label={c("catalog.title")}><option value="latest">{c("catalog.latest")}</option><option value="price_low">{c("catalog.priceLow")}</option><option value="price_high">{c("catalog.priceHigh")}</option><option value="name">{c("catalog.name")}</option></select></div>
              {catalog.products.length > 0 ? <div className="live-store-grid">{catalog.products.map((product, index) => <ProductCard key={product.id} product={product} category={categoryById.get(product.category_id)} locale={locale} productPath={`${homePath}/product/${encodeURIComponent(product.slug)}`} onAdd={addToCart} eager={index < 3} />)}</div> : <div className="live-store-empty"><ShoppingBag size={38} /><h2>{c("catalog.emptyTitle")}</h2><p>{c("catalog.emptyBody")}</p></div>}
              {catalog.pagination.pages > 1 && <nav className="live-store-pagination" aria-label={c("catalog.pages")}>{Array.from({ length: catalog.pagination.pages }, (_, index) => index + 1).map((page) => <button type="button" key={page} className={Number(filters.page) === page ? "is-active" : ""} onClick={() => setFilter("page", String(page), false)}>{page}</button>)}</nav>}
              </div>
            </div>
          </section>
        )}
      </main>
      <footer className="live-store-footer has-social-links">
        <div>{brand && <strong>{brand}</strong>}{description && <p>{description}</p>}</div>
        <div><strong>{c("nav.shop")}</strong><Link to={shopPath}>{c("common.products")}</Link><Link to={categoriesPath}>{c("common.categories")}</Link></div>
        <div><strong>{c("nav.contact")}</strong>{site?.contact_email && <a dir="ltr" href={`mailto:${site.contact_email}`}>{site.contact_email}</a>}{site?.phone && <a dir="ltr" href={`tel:${site.phone}`}>{site.phone}</a>}</div>
        <div className="live-store-footer-social"><strong>{c("footer.followUs")}</strong><nav aria-label={c("footer.followUs")}>{socialLinks.map((item) => item.href ? <a key={item.key} href={item.href} target="_blank" rel="noopener noreferrer" aria-label={item.label} title={item.label}><SocialIcon network={item.key} /></a> : <span key={item.key} className="is-disabled" title={item.label} aria-hidden="true"><SocialIcon network={item.key} /></span>)}</nav></div>
      </footer>
    </div>
  );
}

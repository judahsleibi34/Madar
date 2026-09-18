import { getEcommerceCacheScope, readEcommerceAdminCacheSnapshot } from "./utils/ecommerceAdminCache";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, CheckCircle2, PackageCheck, RefreshCw, Search, SlidersHorizontal } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import useDebouncedValue from "../../hooks/useDebouncedValue";
import AuthToast from "../AuthPages/AuthToast";
import EcommerceOperationsSkeleton from "./EcommerceOperationsSkeleton";
import { collectEcommerceOrderPayment, fetchEcommerceDeliveryAreas, fetchEcommerceOrder, fetchEcommerceOrders, transitionEcommerceOrder } from "../../services/ecommerceApi";

import { useCommerceI18n } from "../../utils/commerceI18n";
const NEXT_STATUS = {
  pending: ["confirmed", "cancelled", "rejected"],
  confirmed: ["preparing", "cancelled", "rejected"],
  preparing: ["out_for_delivery", "cancelled"],
  out_for_delivery: ["delivered"],
};

const snapshotText = (snapshot, locale) => (snapshot?.items || []).map((entry) => {
  const option = entry.option_name_translations?.[locale] || entry.option_name_translations?.en || entry.option_name_translations?.ar || Object.values(entry.option_name_translations || {})[0] || entry.option_code;
  const value = entry.value_translations?.[locale] || entry.value_translations?.en || entry.value_translations?.ar || Object.values(entry.value_translations || {})[0] || entry.value_code;
  return option && value ? `${option}: ${value}` : "";
}).filter(Boolean).join(" · ");

function OrderDetail({ cacheScope, orderId }) {
  const { t, locale, direction, money, dateTime, status: statusLabel, payment: paymentLabel } = useCommerceI18n();
  const navigate = useNavigate();
  const initial = readEcommerceAdminCacheSnapshot(cacheScope, `order:${orderId}`);
  const [data, setData] = useState(() => initial?.data || null);
  const [loading, setLoading] = useState(() => !initial);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);
  useEffect(() => {
    let cancelled = false;
    fetchEcommerceOrder(orderId, { scope: cacheScope })
      .then((result) => { if (!cancelled) setData(result); })
      .catch(() => { if (!cancelled) setToast({ type: "error", title: t("errors.loadOrders"), message: t("admin.tryAgain") }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [cacheScope, orderId, t]);
  const act = async (action) => {
    setBusy(true);
    try {
      const result = action === "collect" ? await collectEcommerceOrderPayment(orderId) : await transitionEcommerceOrder(orderId, action, "");
      setData(result);
      setToast({ type: "success", title: t("admin.orderUpdated"), message: action === "collect" ? t("admin.codRecorded") : t("admin.statusChanged", { status: statusLabel(action) }) });
    } catch { setToast({ type: "error", title: t("errors.updateOrder"), message: t("admin.tryAgain") }); }
    finally { setBusy(false); }
  };
  if (loading) return <main className="ecommerce-page ecommerce-operations-page" dir={direction} lang={locale}><EcommerceOperationsSkeleton variant="order-detail" label={t("merchant.loadingOrders")} /></main>;
  if (!data?.order) return <main className="ecommerce-page ecommerce-operations-page" dir={direction} lang={locale}><button onClick={() => navigate("/ecommerce/orders")}>{t("common.back")}</button><p>{t("admin.orderNotFound")}</p><AuthToast {...toast} dir={direction} onDismiss={() => setToast(null)} /></main>;
  const { order, items = [], status_history: history = [] } = data;
  return (
    <main className="ecommerce-page ecommerce-operations-page" dir={direction} lang={locale}>
      <header className="ecommerce-page-header app-page-intro"><div><Link to="/ecommerce/orders" className="ecommerce-back-link"><ArrowLeft size={16} />{t("merchant.ordersTitle")}</Link><h1 dir="ltr">{order.order_number}</h1><p>{dateTime(order.created_at)}</p></div><div className="ecommerce-status-actions">{(NEXT_STATUS[order.status] || []).map((status) => <button key={status} disabled={busy} onClick={() => act(status)}>{statusLabel(status)}</button>)}{order.payment_status === "unpaid" && <button disabled={busy} onClick={() => act("collect")}><CheckCircle2 size={16} />{t("merchant.markCollected")}</button>}</div></header>
      <div className="ecommerce-order-detail-grid">
        <section><h2>{t("merchant.customer")}</h2><p><strong>{order.customer_name}</strong><br /><bdi>{order.customer_phone}</bdi><br /><bdi>{order.customer_email}</bdi></p></section>
        <section><h2>{t("common.delivery")}</h2><p><strong>{locale === "ar" ? order.service_area_name_ar || order.service_area_name_en : order.service_area_name_en || order.service_area_name_ar || order.city}</strong><br />{order.street || order.address_line_1}</p></section>
        <section><h2>{t("merchant.payment")}</h2><p>{paymentLabel("cash_on_delivery")}<br /><strong>{paymentLabel(order.payment_status)}</strong></p></section>
        <section><h2>{t("merchant.orderDetail")}</h2><p>{t("common.status")}: <strong>{statusLabel(order.status)}</strong><br />{t("common.subtotal")}: {money(order.subtotal, order.currency)}<br />{t("common.discount")}: {money(order.discount_total, order.currency)}<br />{t("common.total")}: <strong>{money(order.total, order.currency)}</strong></p></section>
      </div>
      <section className="ecommerce-operations-card">
        <h2>{t("merchant.items")}</h2>
        <div className="ecommerce-order-items">{items.map((item) => {
          const options = snapshotText(item.selected_options_snapshot, locale);
          const barcode = item.variant_snapshot?.barcode;
          return (
            <article key={item.id}>
              <div>
                <strong>{item.product_name}</strong>
                <small>{t("common.sku")} <bdi>{item.sku}</bdi> · {t("common.quantity")} {item.quantity}</small>
                {item.variant_id && <small>{t("admin.variant")}: {options || <bdi>{item.variant_snapshot?.sku || item.sku}</bdi>}</small>}
                {barcode && <small>{t("common.barcode")}: <bdi>{barcode}</bdi></small>}
              </div>
              <div>
                <span>{t("admin.listPrice")} {money(item.list_unit_price, order.currency)}</span>
                <span>{t("common.discount")} {money(item.discount_amount, order.currency)}{item.discount_source === "loyalty" ? ` · ${t("loyalty.appliedDiscount")}` : ""}</span>
                <span>{t("admin.unitPrice")} {money(item.unit_price, order.currency)}</span>
                <strong>{money(item.line_total, order.currency)}</strong>
              </div>
            </article>
          );
        })}</div>
      </section>
      <section className="ecommerce-operations-card"><h2>{t("merchant.statusHistory")}</h2><ol className="ecommerce-status-history">{history.map((entry) => <li key={entry.id || `${entry.new_status}-${entry.created_at}`}><PackageCheck size={17} /><span><strong>{statusLabel(entry.new_status)}</strong><small>{dateTime(entry.created_at)}{entry.note ? ` · ${entry.note}` : ""}</small></span></li>)}</ol></section>
      <AuthToast dir={direction} key={toast?.id} type={toast?.type} title={toast?.title} message={toast?.message} onDismiss={() => setToast(null)} />
    </main>
  );
}

export default function EcommerceOrdersPage({ user }) {
  const cacheScope = getEcommerceCacheScope(user);
  const location = useLocation();
  const { t, locale, direction, money, dateTime, status: statusLabel, payment: paymentLabel } = useCommerceI18n();
  const orderId = location.pathname.match(/\/ecommerce\/orders\/([^/]+)/)?.[1];
  const initial = readEcommerceAdminCacheSnapshot(cacheScope, "orders:/ecommerce/orders");
  const [orders, setOrders] = useState(() => initial?.data?.orders || []);
  const [areas, setAreas] = useState(() => readEcommerceAdminCacheSnapshot(cacheScope, "delivery-areas")?.data?.areas || []);
  const [filters, setFilters] = useState({ order_number: "", customer_name: "", phone: "", status: "", payment_status: "", date_from: "", date_to: "", service_area_id: "" });
  const [loading, setLoading] = useState(() => !initial);
  const [error, setError] = useState("");
  const [toast, setToast] = useState(null);
  const query = useDebouncedValue(filters);
  const requestVersion = useRef(0);
  const load = () => {
    const version = ++requestVersion.current;
    setLoading(true); setError("");
    fetchEcommerceOrders(filters, { scope:cacheScope, force:true })
      .then((result) => { if (version === requestVersion.current) { setOrders(result?.orders || []); setToast({type:"success", title:t("feedback.ordersRefreshed"), message:t("feedback.ordersRefreshedBody")}); } })
      .catch(() => { if (version === requestVersion.current) { setError(t("errors.loadOrders")); setToast({type:"error", title:t("errors.loadOrders"), message:t("admin.tryAgain")}); } })
      .finally(() => { if (version === requestVersion.current) setLoading(false); });
  };
  useEffect(() => {
    let cancelled = false;
    fetchEcommerceDeliveryAreas({ scope: cacheScope }).then((result) => { if (!cancelled) setAreas(result?.areas || []); }).catch(() => { if (!cancelled) setToast({ type: "error", title: t("admin.loadDelivery"), message: t("admin.tryAgain") }); });
    return () => { cancelled = true; };
  }, [cacheScope, t]);
  useEffect(() => {
    if (orderId) return undefined;
    const version = ++requestVersion.current;
    let cancelled = false;
    const params = new URLSearchParams(Object.entries(query).filter(([, value]) => String(value || "").trim()));
    const snapshot = readEcommerceAdminCacheSnapshot(cacheScope, `orders:/ecommerce/orders${params.size ? `?${params}` : ""}`);
    Promise.resolve().then(() => {
      if (cancelled) return null;
      setLoading(!snapshot); setError("");
      if (snapshot) setOrders(snapshot.data?.orders || []);
      return fetchEcommerceOrders(query, { scope:cacheScope });
    })
      .then((result) => { if (!cancelled && version === requestVersion.current) setOrders(result?.orders || []); })
      .catch(() => { if (!cancelled && version === requestVersion.current) { if (!snapshot) setError(t("errors.loadOrders")); setToast({ type:"error", title:t("errors.loadOrders"), message:t("admin.tryAgain") }); } })
      .finally(() => { if (!cancelled && version === requestVersion.current) setLoading(false); });
    return () => { cancelled = true; };
  }, [cacheScope, orderId, query, t]);
  if (orderId) return <OrderDetail key={`${cacheScope}:${orderId}`} cacheScope={cacheScope} orderId={orderId} />;
  const update = (key, value) => setFilters((current) => ({ ...current, [key]: value }));
  return (
    <main className="ecommerce-page ecommerce-operations-page ecommerce-orders-page" dir={direction} lang={locale}>
      <header className="ecommerce-page-header app-page-intro"><div><h1>{t("merchant.ordersTitle")}</h1><p>{t("merchant.ordersSubtitle")}</p></div></header>
      <div className="ecommerce-orders-workspace">
        <aside className="ecommerce-operations-card ecommerce-orders-sidebar" aria-labelledby="orders-metadata-title">
          <header className="ecommerce-orders-filter-toolbar"><h2 id="orders-metadata-title"><SlidersHorizontal size={18} />{t("merchant.filters")}</h2></header>
      <div className="ecommerce-orders-panel-actions"><button type="button" className="ecommerce-secondary-button ecommerce-order-clear-filters" disabled={!Object.values(filters).some(Boolean)} onClick={() => setFilters({ order_number: "", customer_name: "", phone: "", status: "", payment_status: "", date_from: "", date_to: "", service_area_id: "" })}>{t("merchant.clearOrderFilters")}</button><button type="button" className="ecommerce-primary-button" disabled={loading} onClick={load}><RefreshCw size={17} />{t("common.refresh")}</button></div>
          <div className="ecommerce-order-filters">
          <label><span>{t("common.status")}</span><select aria-label={t("common.status")} value={filters.status} onChange={(event) => update("status", event.target.value)}><option value="">{t("merchant.allOrderStatuses")}</option>{["pending","confirmed","preparing","out_for_delivery","delivered","fulfilled","cancelled","rejected"].map((value) => <option key={value} value={value}>{statusLabel(value)}</option>)}</select></label>
          <label><span>{t("confirmation.paymentStatus")}</span><select aria-label={t("confirmation.paymentStatus")} value={filters.payment_status} onChange={(event) => update("payment_status", event.target.value)}><option value="">{t("merchant.allPaymentStatuses")}</option>{["unpaid","collected","paid","refunded"].map((value) => <option key={value} value={value}>{paymentLabel(value)}</option>)}</select></label>
          <label><span>{t("admin.serviceArea")}</span><select aria-label={t("admin.serviceArea")} value={filters.service_area_id} onChange={(event) => update("service_area_id", event.target.value)}><option value="">{t("admin.allDeliveryAreas")}</option>{areas.map((area) => <option key={area.id} value={area.id}>{locale === "ar" ? area.name_ar || area.name_en : area.name_en || area.name_ar}</option>)}</select></label>
          <label><span>{t("admin.ordersFrom")}</span><input aria-label={t("admin.ordersFrom")} type="date"  value={filters.date_from} onChange={(event) => update("date_from", event.target.value)} /></label>
          <label><span>{t("admin.ordersTo")}</span><input aria-label={t("admin.ordersTo")} type="date"  value={filters.date_to} onChange={(event) => update("date_to", event.target.value)} /></label>
          </div>
        </aside>
        <div className="ecommerce-orders-main">
          <section className="ecommerce-operations-card ecommerce-orders-search-card" aria-label={t("common.search")}>
            <div className="ecommerce-order-filters">
          <label><span>{t("confirmation.orderNumber")}</span><span className="ecommerce-search"><Search size={17} /><input aria-label={t("confirmation.orderNumber")} type="text" placeholder={t("confirmation.orderNumber")} value={filters.order_number} onChange={(event) => update("order_number", event.target.value)} /></span></label>
          <label><span>{t("merchant.customer")}</span><input aria-label={t("merchant.customer")} type="text" placeholder={t("merchant.customer")} value={filters.customer_name} onChange={(event) => update("customer_name", event.target.value)} /></label>
          <label><span>{t("checkout.phone")}</span><input aria-label={t("checkout.phone")} type="text" placeholder={t("checkout.phone")} value={filters.phone} onChange={(event) => update("phone", event.target.value)} dir="ltr"/></label>
            </div>
          </section>
      <section className="ecommerce-operations-card ecommerce-orders-results">
        <header className="ecommerce-orders-results-header"><h2>{t("merchant.ordersTitle")}</h2><span>{t("merchant.orderResultsCount", { count: orders.length })}</span></header>
        {loading ? <EcommerceOperationsSkeleton variant="orders" label={t("merchant.loadingOrders")} /> : error ? <div className="ecommerce-operations-state is-error">{error}<button onClick={load}>{t("common.retry")}</button></div> : !orders.length ? <div className="ecommerce-operations-state ecommerce-orders-empty"><span className="ecommerce-orders-empty-icon"><PackageCheck size={28} /></span><h3>{t("merchant.noOrders")}</h3><p>{t(Object.values(filters).some(Boolean) ? "merchant.noMatchingOrdersHelp" : "merchant.noOrdersHelp")}</p></div> : <div className="ecommerce-orders-table" role="table">{orders.map((order) => <Link key={order.id} to={`/ecommerce/orders/${order.id}`} role="row"><span><strong dir="ltr">{order.order_number}</strong><small>{dateTime(order.created_at)}</small></span><span>{order.customer_name}<small dir="ltr">{order.customer_phone}</small></span><span>{locale === "ar" ? order.service_area_name_ar || order.service_area_name_en : order.service_area_name_en || order.service_area_name_ar}</span><span>{money(order.total, order.currency)}</span><span>{statusLabel(order.status)}</span><span>{paymentLabel(order.payment_status)}</span></Link>)}</div>}
      </section>
        </div>
      </div>
      <AuthToast {...toast} dir={direction} onDismiss={() => setToast(null)} />
    </main>
  );
}

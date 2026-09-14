import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, CheckCircle2, LoaderCircle, PackageCheck, RefreshCw, Search } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import AuthToast from "../AuthPages/AuthToast";
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

function OrderDetail({ orderId }) {
  const { t, locale, direction, money, dateTime, status: statusLabel, payment: paymentLabel } = useCommerceI18n();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);
  useEffect(() => {
    let cancelled = false;
    fetchEcommerceOrder(orderId)
      .then((result) => { if (!cancelled) setData(result); })
      .catch((error) => { if (!cancelled) setToast({ type: "error", title: t("errors.loadOrders"), message: error.message }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [orderId, t]);
  const act = async (action) => {
    setBusy(true);
    try {
      const result = action === "collect" ? await collectEcommerceOrderPayment(orderId) : await transitionEcommerceOrder(orderId, action, "");
      setData(result);
      setToast({ type: "success", title: t("admin.orderUpdated"), message: action === "collect" ? t("admin.codRecorded") : t("admin.statusChanged", { status: statusLabel(action) }) });
    } catch (error) { setToast({ type: "error", title: t("errors.updateOrder"), message: error.message }); }
    finally { setBusy(false); }
  };
  if (loading) return <main className="ecommerce-page ecommerce-operations-page" dir={direction}><div className="ecommerce-operations-state"><LoaderCircle className="is-spinning" />{t("merchant.loadingOrders")}</div></main>;
  if (!data?.order) return <main className="ecommerce-page ecommerce-operations-page" dir={direction} lang={locale}><button onClick={() => navigate("/ecommerce/orders")}>{t("common.back")}</button><p>{t("admin.orderNotFound")}</p><AuthToast {...toast} /></main>;
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
      <AuthToast key={toast?.id} type={toast?.type} title={toast?.title} message={toast?.message} onDismiss={() => setToast(null)} />
    </main>
  );
}

export default function EcommerceOrdersPage() {
  const location = useLocation();
  const { t, locale, direction, money, dateTime, status: statusLabel, payment: paymentLabel } = useCommerceI18n();
  const orderId = location.pathname.match(/\/ecommerce\/orders\/([^/]+)/)?.[1];
  const [orders, setOrders] = useState([]);
  const [areas, setAreas] = useState([]);
  const [filters, setFilters] = useState({ order_number: "", customer_name: "", phone: "", status: "", payment_status: "", date_from: "", date_to: "", service_area_id: "" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const query = useMemo(() => filters, [filters]);
  const load = () => { setLoading(true); setError(""); fetchEcommerceOrders(query).then((result) => setOrders(result?.orders || [])).catch((failure) => setError(failure.message)).finally(() => setLoading(false)); };
  useEffect(() => {
    let cancelled = false;
    fetchEcommerceDeliveryAreas().then((result) => { if (!cancelled) setAreas(result?.areas || []); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    let cancelled = false;
    fetchEcommerceOrders(query)
      .then((result) => { if (!cancelled) setOrders(result?.orders || []); })
      .catch((failure) => { if (!cancelled) setError(failure.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [query]);
  if (orderId) return <OrderDetail orderId={orderId} />;
  const update = (key, value) => setFilters((current) => ({ ...current, [key]: value }));
  return (
    <main className="ecommerce-page ecommerce-operations-page" dir={direction} lang={locale}>
      <header className="ecommerce-page-header app-page-intro"><div><h1>{t("merchant.ordersTitle")}</h1></div><button className="ecommerce-secondary-button" onClick={load}><RefreshCw size={17} />{t("common.retry")}</button></header>
      <section className="ecommerce-operations-card">
        <div className="ecommerce-order-filters"><label><Search size={16} /><input aria-label={t("confirmation.orderNumber")} placeholder={t("confirmation.orderNumber")} value={filters.order_number} onChange={(event) => update("order_number", event.target.value)} /></label><input aria-label={t("merchant.customer")} placeholder={t("merchant.customer")} value={filters.customer_name} onChange={(event) => update("customer_name", event.target.value)} /><input aria-label={t("checkout.phone")} placeholder={t("checkout.phone")} value={filters.phone} onChange={(event) => update("phone", event.target.value)} dir="ltr" /><select aria-label={t("common.status")} value={filters.status} onChange={(event) => update("status", event.target.value)}><option value="">{t("merchant.filters")}</option>{["pending","confirmed","preparing","out_for_delivery","delivered","fulfilled","cancelled","rejected"].map((value) => <option key={value} value={value}>{statusLabel(value)}</option>)}</select><select aria-label={t("confirmation.paymentStatus")} value={filters.payment_status} onChange={(event) => update("payment_status", event.target.value)}><option value="">{t("merchant.filters")}</option>{["unpaid","collected","paid","refunded"].map((value) => <option key={value} value={value}>{paymentLabel(value)}</option>)}</select></div>
        <div className="ecommerce-order-filters ecommerce-order-filters-secondary">
          <select aria-label={t("admin.serviceArea")} value={filters.service_area_id} onChange={(event) => update("service_area_id", event.target.value)}><option value="">{t("admin.allDeliveryAreas")}</option>{areas.map((area) => <option key={area.id} value={area.id}>{locale === "ar" ? area.name_ar || area.name_en : area.name_en || area.name_ar}</option>)}</select>
          <label><span>{t("admin.from")}</span><input aria-label={t("admin.ordersFrom")} type="date" value={filters.date_from} onChange={(event) => update("date_from", event.target.value)} /></label>
          <label><span>{t("admin.to")}</span><input aria-label={t("admin.ordersTo")} type="date" value={filters.date_to} onChange={(event) => update("date_to", event.target.value)} /></label>
        </div>
        {loading ? <div className="ecommerce-operations-state"><LoaderCircle className="is-spinning" />{t("merchant.loadingOrders")}</div> : error ? <div className="ecommerce-operations-state is-error">{error}<button onClick={load}>{t("common.retry")}</button></div> : !orders.length ? <div className="ecommerce-operations-state">{t("merchant.noOrders")}</div> : <div className="ecommerce-orders-table" role="table">{orders.map((order) => <Link key={order.id} to={`/ecommerce/orders/${order.id}`} role="row"><span><strong dir="ltr">{order.order_number}</strong><small>{dateTime(order.created_at)}</small></span><span>{order.customer_name}<small dir="ltr">{order.customer_phone}</small></span><span>{locale === "ar" ? order.service_area_name_ar || order.service_area_name_en : order.service_area_name_en || order.service_area_name_ar}</span><span>{money(order.total, order.currency)}</span><span>{statusLabel(order.status)}</span><span>{paymentLabel(order.payment_status)}</span></Link>)}</div>}
      </section>
    </main>
  );
}

import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Clock, FlaskConical, RotateCcw, XCircle } from "lucide-react";
import * as commerce from "../../services/elearningCommerce";
import { checkoutStatus } from "../../utils/learningPayments";
import LearningErrorNotice from "./LearningErrorNotice";
import "../../styles/enrollment-checkout.css";

const ICONS = { processing: Clock, confirmed: CheckCircle2, failed: XCircle, cancelled: XCircle, refunded: RotateCcw };

/** "TEST MODE — no real payment is taken" (shown whenever payments are simulated). */
export function TestModeBanner() {
  const { t } = useTranslation("dashboard");
  return <p className="enrollment-test-banner" role="note"><FlaskConical size={18} aria-hidden="true" />{t("elearning.enrollment.testMode")}</p>;
}

export function PaymentStatus({ status }) {
  const { t } = useTranslation("dashboard");
  const Icon = ICONS[status] || Clock;
  return <p className={`enrollment-status is-${status}`} role="status"><Icon size={20} aria-hidden="true" /><span><strong>{t(`elearning.enrollment.state_${status}`)}</strong> {t(`elearning.enrollment.help_${status}`)}</span></p>;
}

/**
 * EH / Checkout for opt-in academies: order summary, TEST MODE banner and the
 * Processing/Confirmed/Failed/Cancelled/Refunded states. Access and referral
 * links follow only from a Confirmed payment recorded by the server.
 */
export default function EnrollmentCheckout({ checkout, local, testMode, referralCode, courseId, onPaid, onClose }) {
  const { t, i18n } = useTranslation("dashboard");
  const [status, setStatus] = useState(checkoutStatus(checkout.state || "pending"));
  const [busy, setBusy] = useState(false), [error, setError] = useState(null);
  const terms = checkout.terms;
  const price = new Intl.NumberFormat(i18n.language, { style: "currency", currency: terms.currency }).format(Number(terms.amount));
  async function outcome(state) {
    setBusy(true); setError(null);
    try { await commerce.localPaymentEvent(checkout.id, state); setStatus(checkoutStatus(state)); if (state === "paid" || state === "refunded") onPaid?.(); }
    catch (failure) { setError(failure); } finally { setBusy(false); }
  }
  return <section className="enrollment-checkout" aria-label={t("elearning.commerce.checkout")}>
    {testMode && <TestModeBanner />}
    <h2>{t("elearning.enrollment.orderSummary")}</h2>
    <dl className="enrollment-summary">
      <div><dt>{t("elearning.enrollment.item")}</dt><dd lang="en">{terms.name}</dd></div>
      <div><dt>{t("elearning.enrollment.price")}</dt><dd dir="ltr">{price}</dd></div>
      <div><dt>{t("elearning.enrollment.payment")}</dt><dd>{t(terms.billing_type === "one_time" ? "elearning.enrollment.oneTime" : `elearning.commerce.${terms.billing_type}`)}</dd></div>
      {terms.billing_type === "one_time" && <div><dt>{t("elearning.enrollment.access")}</dt><dd>{t("elearning.enrollment.lifetime")}</dd></div>}
      <div><dt>{t("elearning.enrollment.referralCode")}</dt><dd dir="ltr">{referralCode || t("elearning.enrollment.noReferral")}</dd></div>
    </dl>
    <PaymentStatus status={status} />
    {error && <LearningErrorNotice as="p">{t("elearning.commerce.error")}</LearningErrorNotice>}
    <div className="enrollment-actions">
      {status === "confirmed" && <>
        <Link className="ecommerce-primary-button" to={courseId ? `/my-learning/courses/${courseId}` : "/my-learning/course"}>{t("elearning.enrollment.startLearning")}</Link>
        <Link className="ecommerce-secondary-button" to="/my-learning/referral">{t("elearning.enrollment.referralReady")}</Link>
      </>}
      {local && ["processing", "failed"].includes(status) && <>
        <button type="button" className="ecommerce-primary-button" disabled={busy} onClick={() => outcome("paid")}>{t("elearning.enrollment.testPay")}</button>
        <button type="button" className="ecommerce-secondary-button" disabled={busy} onClick={() => outcome("failed")}>{t("elearning.enrollment.testFail")}</button>
      </>}
      {local && status === "confirmed" && terms.billing_type === "one_time" && <button type="button" className="ecommerce-secondary-button" disabled={busy} onClick={() => outcome("refunded")}>{t("elearning.enrollment.testRefund")}</button>}
      {["processing", "failed"].includes(status) && <button type="button" className="ecommerce-secondary-button" disabled={busy} onClick={() => setStatus("cancelled")}>{t("elearning.commerce.cancel")}</button>}
      {["cancelled", "refunded"].includes(status) && onClose && <button type="button" className="ecommerce-secondary-button" onClick={onClose}>{t("elearning.enrollment.close")}</button>}
    </div>
  </section>;
}

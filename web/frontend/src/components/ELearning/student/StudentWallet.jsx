import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowDownCircle, Award, Clock, Wallet } from "lucide-react";
import { formatMoney, pendingRewards, walletHistory, withdrawState } from "../../../utils/studentFinance";
import ELearningSkeleton from "../ELearningSkeleton";
import LearningErrorNotice from "../LearningErrorNotice";
import { request } from "../academyProgrammeApi";
import useStudentData from "./useStudentData";
import { StatCard, StatusPill, StudentPage } from "./StudentParts";

function Balances({ wallet, referrals }) {
  const { t, i18n } = useTranslation("dashboard");
  const money = value => formatMoney(value, wallet?.currency, i18n.language);
  return <div className="stat-grid">
    <StatCard icon={Wallet} label={t("elearning.student.availableBalance")} value={money(wallet?.available)} />
    <StatCard icon={Clock} label={t("elearning.student.pendingBalance")} value={money(pendingRewards(referrals))} detail={Number(wallet?.pending) > 0 ? t("elearning.student.heldForWithdrawal", { amount: money(wallet.pending) }) : undefined} />
    <StatCard icon={Award} label={t("elearning.student.totalEarned")} value={money(wallet?.total_earned)} />
    <StatCard icon={ArrowDownCircle} label={t("elearning.student.totalWithdrawn")} value={money(wallet?.total_withdrawn)} />
  </div>;
}

/** EH / Transaction history table (website document §18), shared with affiliates. */
export function WalletHistory({ referrals, withdrawals, currency }) {
  const { t, i18n } = useTranslation("dashboard");
  const rows = walletHistory(referrals, withdrawals);
  const date = value => new Date(value).toLocaleDateString(i18n.language);
  const money = (value, rowCurrency) => formatMoney(value, rowCurrency || currency, i18n.language);
  return <section className="student-panel">
    <h2>{t("elearning.student.transactionHistory")}</h2>
    {rows.length ? <div className="affiliate-table-scroll"><table className="student-table">
      <thead><tr>{["date", "type", "description", "amount", "status", "balanceAfter"].map(key => <th scope="col" key={key}>{t(`elearning.student.column_${key}`)}</th>)}</tr></thead>
      <tbody>{rows.map(row => <tr key={row.id}>
        <td>{date(row.date)}</td>
        <td>{t(row.type === "reward" ? "elearning.student.referralReward" : "elearning.student.withdrawal")}</td>
        <td>{row.type === "reward" ? t(row.simulated ? "elearning.student.rewardTestDescription" : "elearning.student.rewardDescription") : t("elearning.student.withdrawalDescription", { reference: String(row.reference).slice(0, 8) })}</td>
        <td dir="ltr" className={row.status === "reversed" || row.status === "rejected" ? "is-void" : row.status === "pending" ? "is-pending" : row.amount < 0 ? "is-negative" : "is-positive"}>{row.amount > 0 ? "+" : ""}{money(row.amount, row.currency)}</td>
        <td><StatusPill status={row.status === "available" ? "earned" : row.status}>{t(row.type === "reward" ? `elearning.student.reward_${row.status}` : `elearning.programmes.${row.status}`)}</StatusPill></td>
        <td>{row.balanceAfter == null ? "—" : money(row.balanceAfter)}</td>
      </tr>)}</tbody>
    </table></div> : <p className="student-empty">{t("elearning.student.noTransactions")}</p>}
    <small>{t("elearning.student.walletReadOnly")}</small>
  </section>;
}

/** EH / Wallet (website document §18): balances and transaction history. */
export function StudentWallet() {
  const { t, i18n } = useTranslation("dashboard");
  const data = useStudentData({ withCourse: false });
  if (data.loading) return <ELearningSkeleton label={t("elearning.loading")} direction={i18n.dir()} />;
  const wallet = data.programmes?.wallet || data.referrals?.wallet;
  if (!wallet) return <StudentPage title={t("elearning.student.wallet")}><LearningErrorNotice as="p">{t("elearning.referrals.unavailable")}</LearningErrorNotice></StudentPage>;
  return <StudentPage title={t("elearning.student.wallet")} intro={t("elearning.student.walletIntro")}>
    <Balances wallet={wallet} referrals={data.referrals} />
    <WalletHistory referrals={data.referrals} withdrawals={data.programmes?.withdrawals || []} currency={wallet.currency} />
  </StudentPage>;
}

function WithdrawalForm({ wallet, settings, onDone }) {
  const { t, i18n } = useTranslation("dashboard");
  const [key, setKey] = useState(() => crypto.randomUUID());
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");
  async function submit(event) {
    event.preventDefault(); setBusy(true); setResult("");
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await request("/withdrawals", { amount: values.amount, payment_method: values.payment_method, payment_information: values.payment_information, ownership_confirmed: confirmed, idempotency_key: key });
      setKey(crypto.randomUUID()); setConfirmed(false); setResult("saved"); onDone();
    } catch { setResult("error"); } finally { setBusy(false); }
  }
  return <form className="student-panel student-form" onSubmit={submit}>
    <h2>{t("elearning.student.requestWithdrawal")}</h2>
    <label>{t("elearning.programmes.amount")}<input name="amount" type="number" inputMode="decimal" step="0.01" min={settings.minimum_withdrawal_amount} max={wallet.available} required dir="ltr" /></label>
    <small>{t("elearning.student.maximumAmount", { amount: formatMoney(wallet.available, wallet.currency, i18n.language) })}</small>
    <label>{t("elearning.programmes.payment_method")}<select name="payment_method" required>{settings.withdrawal_methods.map(value => <option key={value}>{value}</option>)}</select></label>
    <label>{t("elearning.programmes.payment_information")}<textarea name="payment_information" required maxLength={4000} /></label>
    {/* Website document §19, word for word. */}
    <label className="student-check"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />{t("elearning.student.ownershipConfirm")}</label>
    <button className="ecommerce-primary-button" disabled={busy || !confirmed}>{t(busy ? "elearning.programmes.saving" : "elearning.student.requestWithdrawal")}</button>
    <p role="status">{result === "saved" ? t("elearning.student.withdrawalSubmitted") : result === "error" ? t("elearning.programmes.error") : ""}</p>
  </form>;
}

/** EH / Withdraw (website document §19): below-minimum and eligible states. */
export function StudentWithdraw({ walletPath = "/my-learning/wallet" }) {
  const { t, i18n } = useTranslation("dashboard");
  const data = useStudentData({ withCourse: false });
  if (data.loading) return <ELearningSkeleton label={t("elearning.loading")} direction={i18n.dir()} />;
  const wallet = data.programmes?.wallet;
  const { state, minimum } = withdrawState(wallet, data.programmes?.settings);
  const money = value => formatMoney(value, wallet?.currency, i18n.language);
  const withdrawals = data.programmes?.withdrawals || [];
  return <StudentPage title={t("elearning.student.withdraw")}>
    {wallet && <Balances wallet={wallet} referrals={data.referrals} />}
    <section className="student-panel" data-testid={`withdraw-${state}`}>
      {minimum != null && <p><strong>{t("elearning.student.minimumWithdrawal")}:</strong> {money(minimum)}</p>}
      {state === "belowMinimum" && <>
        {/* Website document §19, word for word. */}
        <StatusPill status="locked">{t("elearning.student.belowMinimum")}</StatusPill>
        <p>{t("elearning.student.onlyAvailable")}</p>
        <button type="button" className="ecommerce-primary-button" disabled>{t("elearning.student.requestWithdrawal")}</button>
      </>}
      {state === "blocked" && <StatusPill status="locked">{t("elearning.student.withdrawBlocked")}</StatusPill>}
      {state === "unavailable" && <p>{t("elearning.student.withdrawUnavailable")}</p>}
      {state === "eligible" && <StatusPill status="eligible">{t("elearning.student.withdrawEligible")}</StatusPill>}
    </section>
    {state === "eligible" && <WithdrawalForm wallet={wallet} settings={data.programmes.settings} onDone={data.retry} />}
    <section className="student-panel">
      <h2>{t("elearning.student.withdrawalHistory")}</h2>
      {withdrawals.length ? <ul className="student-list">{withdrawals.map(row => <li key={row.id}>
        <span dir="auto">{t("elearning.student.withdrawalLine", { reference: String(row.id).slice(0, 8), amount: money(row.amount) })}</span>
        <StatusPill status={row.status}>{t(`elearning.programmes.${row.status}`)}</StatusPill>
      </li>)}</ul> : <p className="student-empty">{t("elearning.student.noWithdrawals")}</p>}
      <Link to={walletPath}>{t("elearning.student.wallet")}</Link>
    </section>
  </StudentPage>;
}

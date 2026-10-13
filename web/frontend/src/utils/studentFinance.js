// EduHope student money views, derived only from data the backend already verified.

/**
 * What My Referral shows. The backend issues a referral code only to a member
 * who bought the course or is an approved affiliate (academy_can_refer), so the
 * link appears only when that code exists; everyone else gets the affiliate
 * invitation (website document §9B, §16).
 */
export function referralView(referrals) {
  if (!referrals?.available) return "unavailable";
  return referrals.enabled && referrals.code ? "link" : "invite";
}

/** Tuition Support progress (website document §11C/D): sales X / threshold, remaining. */
export function tuitionProgress(wallet) {
  const threshold = Number(wallet?.threshold) || 4;
  const sales = Math.max(0, Number(wallet?.verified_sales) || 0);
  return { sales, threshold, remaining: Math.max(0, threshold - sales), eligible: wallet?.tuition_eligible ?? sales >= threshold };
}

const REWARD_STATUS = { pending: "pending", earned: "available", reversed: "reversed" };
const HELD = new Set(["pending", "approved", "processing", "paid"]);

/**
 * Pending referral rewards: referred purchases whose reward is not earned yet.
 * (The wallet's own "pending" is money held for withdrawal requests.)
 */
export function pendingRewards(referrals) {
  return (referrals?.history || []).filter(row => row.status === "pending" && !row.simulated).reduce((sum, row) => sum + Number(row.amount || 0), 0);
}

/**
 * Wallet history (website document §18): referral rewards and withdrawals,
 * newest first. "Balance after" follows the Available Balance the backend
 * computes — earned real rewards add; withdrawals that are pending, approved,
 * processing or paid subtract; pending, reversed and test-mode rewards do not
 * count — and is only given when the history is complete.
 */
export function walletHistory(referrals, withdrawals = []) {
  const rewards = (referrals?.history || []).map(row => ({
    id: `reward:${row.id}`, type: "reward", date: row.reversed_at || row.earned_at || row.created_at,
    amount: Number(row.amount), currency: row.currency, status: REWARD_STATUS[row.status] || row.status, simulated: Boolean(row.simulated),
  }));
  const payouts = withdrawals.map(row => ({
    id: `withdrawal:${row.id}`, type: "withdrawal", date: row.created_at,
    amount: -Number(row.amount), currency: row.currency, status: row.status, reference: row.id,
  }));
  const rows = [...rewards, ...payouts].sort((a, b) => new Date(a.date) - new Date(b.date) || a.id.localeCompare(b.id));
  const complete = (referrals?.history?.length || 0) >= (Number(referrals?.referred_count) || 0);
  let balance = 0;
  return rows.map(row => {
    if ((row.type === "reward" && row.status === "available" && !row.simulated) || (row.type === "withdrawal" && HELD.has(row.status))) balance += row.amount;
    return { ...row, balanceAfter: complete ? Math.max(balance, 0) : null };
  }).reverse();
}

/** Withdraw state (website document §19): only Available Balance, at or above the admin minimum. */
export function withdrawState(wallet, settings) {
  const minimum = settings?.minimum_withdrawal_amount == null ? null : Number(settings.minimum_withdrawal_amount);
  const available = Number(wallet?.available) || 0;
  if (!settings?.withdrawals_enabled || minimum == null || !(settings.withdrawal_methods || []).length) return { state: "unavailable", minimum, available };
  if (Number(wallet?.debt || 0) > 0) return { state: "blocked", minimum, available };
  return { state: available >= minimum ? "eligible" : "belowMinimum", minimum, available };
}

/** Share targets (website document §9D). Instagram has no share URL, so it copies the link. */
export function shareTargets(url, message) {
  const link = encodeURIComponent(url), text = encodeURIComponent(`${message} ${url}`);
  return [
    ["whatsapp", "WhatsApp", `https://wa.me/?text=${text}`],
    ["facebook", "Facebook", `https://www.facebook.com/sharer/sharer.php?u=${link}`],
    ["instagram", "Instagram", null],
    ["telegram", "Telegram", `https://t.me/share/url?url=${link}&text=${encodeURIComponent(message)}`],
    ["email", "Email", `mailto:?subject=${encodeURIComponent("EduHope")}&body=${text}`],
  ];
}

export function formatMoney(amount, currency = "USD", locale = "en") {
  if (amount == null || Number.isNaN(Number(amount))) return "—";
  return new Intl.NumberFormat(locale, { style: "currency", currency: currency || "USD" }).format(Number(amount));
}

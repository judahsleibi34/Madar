export function parseUsdMinor(value) {
  if (!/^(0|[1-9]\d{0,10})(\.\d{1,2})?$/.test(value)) throw new Error("Enter a positive USD amount with at most two decimal places.");
  const [whole, fraction = ""] = value.split(".");
  const result = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
  if (result <= 0n || result > 1000000000000n) throw new Error("Amount is outside the supported range.");
  return Number(result);
}
export const money = (minor) => `${(BigInt(minor || 0) / 100n).toString()}.${(BigInt(minor || 0) % 100n).toString().padStart(2, "0")} USD`;

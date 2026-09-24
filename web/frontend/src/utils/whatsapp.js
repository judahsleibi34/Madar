export const normalizeWhatsAppNumber = (value) => {
  let digits = String(value || "").trim().replace(/\D/g, "");
  if (digits.startsWith("00")) digits = digits.slice(2);
  if (digits.startsWith("0")) digits = `970${digits.slice(1)}`;
  return /^\d{8,15}$/.test(digits) ? digits : "";
};

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, Share2 } from "lucide-react";

/** Share a certificate's public verification link (native share, else copy). */
export default function CertificateShare({ title, url }) {
  const { t } = useTranslation("dashboard");
  const [state, setState] = useState("");
  async function share() {
    try {
      if (navigator.share) { await navigator.share({ title, url }); return; }
      await navigator.clipboard.writeText(url); setState("copied");
    } catch (error) { if (error?.name !== "AbortError") setState("failed"); }
  }
  return <>
    <button type="button" className="ecommerce-secondary-button" onClick={share}>{state === "copied" ? <Check size={16} aria-hidden="true" /> : <Share2 size={16} aria-hidden="true" />}{t(state === "copied" ? "elearning.certificates.linkCopied" : "elearning.certificates.share")}</button>
    {state === "failed" && <span role="status">{t("elearning.certificates.shareHelp")}</span>}
  </>;
}

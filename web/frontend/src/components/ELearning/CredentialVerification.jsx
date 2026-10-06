import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { verifyCredential } from "../../services/elearningCredentials";
import ELearningSkeleton from "./ELearningSkeleton";
import "../../styles/admin/dashboard/elearning-certificates.css";
export default function CredentialVerification() {
  const { token } = useParams(); const { t, i18n } = useTranslation("dashboard");
  const [state, setState] = useState({ loading: true }); const [retry, setRetry] = useState(0);
  useEffect(() => { let active = true; verifyCredential(token).then(data => { if (active) setState(data); }).catch(() => { if (active) setState({ error: true }); }); return () => { active = false; }; }, [token, retry]);
  return <main className="elearning-verification" dir={i18n.dir()} lang={i18n.language}><button className="ecommerce-secondary-button" onClick={() => i18n.changeLanguage(i18n.language.startsWith("ar") ? "en" : "ar")}>العربية / English</button>{state.loading ? <ELearningSkeleton label={t("elearning.certificates.loading")} direction={i18n.dir()} lang={i18n.language} /> : state.error ? <p role="alert">{t("elearning.certificates.error")}<button onClick={() => { setState({ loading: true }); setRetry(value => value+1); }}>{t("elearning.retry")}</button></p> : state.credential ? <article className="elearning-certificate-document"><h1>{t(`elearning.certificates.${state.credential.status === "revoked" ? "verificationRevoked" : "valid"}`)}</h1><dl>{["learner_name", "course_name", "issuer_name", "completed_at", "issued_at", "credential_number", "status"].map(key => <div key={key}><dt>{t(`elearning.certificates.public.${key}`)}</dt><dd>{key === "status" ? t(`elearning.certificates.${state.credential[key]}`) : key.endsWith("_at") ? new Date(state.credential[key]).toLocaleDateString(i18n.language) : state.credential[key]}</dd></div>)}</dl></article> : <h1>{t("elearning.certificates.notFound")}</h1>}<p>{t("elearning.certificates.issuedVia")}</p></main>;
}

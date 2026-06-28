import { useCallback, useEffect, useMemo, useState } from "react";
import { KeyRound, QrCode, RefreshCw, ShieldCheck, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { apiFetch } from "../../utils/apiClient";

const API_URL = import.meta.env.VITE_API_URL || "/api";

const getApiErrorMessage = (detail, fallback) => {
  if (typeof detail === "string" && detail.trim()) return detail;

  if (Array.isArray(detail)) {
    const message = detail
      .map((error) => {
        const field = Array.isArray(error.loc) ? error.loc.at(-1) : "";
        return [field, error.msg].filter(Boolean).join(": ");
      })
      .filter(Boolean)
      .join(" ");

    return message || fallback;
  }

  if (detail && typeof detail === "object") {
    return detail.message || detail.error || fallback;
  }

  return fallback;
};

const toQrImageSrc = (value) => {
  const cleanValue = String(value || "").trim();

  if (!cleanValue) return "";
  if (cleanValue.startsWith("data:image/")) return cleanValue;
  if (cleanValue.startsWith("<svg")) {
    return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(cleanValue)}`;
  }

  return "";
};

const getFactorLabel = (factor, fallback) => {
  return factor?.friendly_name || factor?.factor_type?.toUpperCase?.() || fallback;
};

export default function SecurityMfaPage({ lang = "en" }) {
  const { t } = useTranslation("dashboard");
  const isArabic = lang === "ar";

  const [status, setStatus] = useState(null);
  const [enrollment, setEnrollment] = useState(null);
  const [verificationCode, setVerificationCode] = useState("");
  const [friendlyName, setFriendlyName] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const qrImageSrc = useMemo(
    () => toQrImageSrc(enrollment?.totp?.qr_code),
    [enrollment]
  );

  const factors = Array.isArray(status?.factors) ? status.factors : [];
  const verifiedFactors = factors.filter((factor) => factor.status === "verified");
  const unverifiedFactors = factors.filter((factor) => factor.status !== "verified");

  const readResponse = useCallback(async (response) => {
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(getApiErrorMessage(data.detail, t("securityMfa.errors.generic")));
    }

    return data;
  }, [t]);

  const loadStatus = useCallback(async ({ showSpinner = false } = {}) => {
    if (showSpinner) setLoading(true);
    setError("");

    try {
      const response = await apiFetch(`${API_URL}/auth/mfa/status`, {
        method: "GET",
        cache: "no-store",
      });
      const data = await readResponse(response);
      setStatus(data);
    } catch (loadError) {
      setError(loadError.message || t("securityMfa.errors.load"));
    } finally {
      if (showSpinner) setLoading(false);
    }
  }, [readResponse, t]);

  useEffect(() => {
    loadStatus({ showSpinner: true });
  }, [loadStatus]);

  const startEnrollment = async () => {
    setBusyAction("enroll");
    setError("");
    setSuccess("");

    try {
      const response = await apiFetch(`${API_URL}/auth/mfa/enroll`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ friendly_name: friendlyName.trim() || null }),
      });
      const data = await readResponse(response);
      setEnrollment(data);
      setVerificationCode("");
      setSuccess(t("securityMfa.messages.enrollStarted"));
      await loadStatus();
    } catch (enrollError) {
      setError(enrollError.message || t("securityMfa.errors.enroll"));
    } finally {
      setBusyAction("");
    }
  };

  const verifyEnrollment = async () => {
    const factorId = enrollment?.factor?.id;
    const code = verificationCode.trim();

    if (!factorId || !code) {
      setError(t("securityMfa.errors.missingCode"));
      return;
    }

    setBusyAction("verify");
    setError("");
    setSuccess("");

    try {
      const response = await apiFetch(`${API_URL}/auth/mfa/enroll/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ factor_id: factorId, code }),
      });
      await readResponse(response);
      setEnrollment(null);
      setVerificationCode("");
      setFriendlyName("");
      setSuccess(t("securityMfa.messages.verified"));
      await loadStatus();
    } catch (verifyError) {
      setError(verifyError.message || t("securityMfa.errors.verify"));
    } finally {
      setBusyAction("");
    }
  };

  const removeFactor = async (factorId) => {
    if (!factorId) return;

    setBusyAction(`remove-${factorId}`);
    setError("");
    setSuccess("");

    try {
      const response = await apiFetch(
        `${API_URL}/auth/mfa/factors/${encodeURIComponent(factorId)}`,
        { method: "DELETE" }
      );
      await readResponse(response);
      setSuccess(t("securityMfa.messages.removed"));
      await loadStatus();
    } catch (removeError) {
      setError(removeError.message || t("securityMfa.errors.remove"));
    } finally {
      setBusyAction("");
    }
  };

  const renderFactor = (factor) => {
    const factorId = factor.id;
    const isRemoving = busyAction === `remove-${factorId}`;

    return (
      <article className="security-mfa-factor" key={factorId || factor.created_at}>
        <div>
          <strong>{getFactorLabel(factor, t("securityMfa.factorFallback"))}</strong>
          <span>{factor.status || t("securityMfa.status.unknown")}</span>
        </div>

        {factorId && (
          <button
            type="button"
            className="security-mfa-danger"
            onClick={() => removeFactor(factorId)}
            disabled={Boolean(busyAction)}
          >
            {isRemoving ? <RefreshCw size={16} /> : <Trash2 size={16} />}
            {isRemoving ? t("securityMfa.actions.removing") : t("securityMfa.actions.remove")}
          </button>
        )}
      </article>
    );
  };

  return (
    <section className="security-mfa-page" dir={isArabic ? "rtl" : "ltr"}>
      <header className="security-mfa-header">
        <span>{t("securityMfa.eyebrow")}</span>
        <h1>{t("securityMfa.title")}</h1>
        <p>{t("securityMfa.subtitle")}</p>
      </header>

      {loading ? (
        <div className="security-mfa-panel security-mfa-loading" role="status">
          <RefreshCw size={18} />
          {t("securityMfa.loading")}
        </div>
      ) : (
        <div className="security-mfa-grid">
          <section className="security-mfa-panel">
            <div className="security-mfa-panel-heading">
              <ShieldCheck size={20} />
              <div>
                <h2>{t("securityMfa.statusTitle")}</h2>
                <p>{t("securityMfa.statusDescription")}</p>
              </div>
            </div>

            <div className="security-mfa-status-grid">
              <div>
                <span>{t("securityMfa.required")}</span>
                <strong>{status?.mfa_required ? t("securityMfa.yes") : t("securityMfa.no")}</strong>
              </div>
              <div>
                <span>{t("securityMfa.currentAal")}</span>
                <strong>{status?.aal?.current_level || t("securityMfa.notProvided")}</strong>
              </div>
              <div>
                <span>{t("securityMfa.nextAal")}</span>
                <strong>{status?.aal?.next_level || t("securityMfa.notProvided")}</strong>
              </div>
            </div>
          </section>

          <section className="security-mfa-panel">
            <div className="security-mfa-panel-heading">
              <KeyRound size={20} />
              <div>
                <h2>{t("securityMfa.factorsTitle")}</h2>
                <p>{t("securityMfa.factorsDescription")}</p>
              </div>
            </div>

            <div className="security-mfa-factor-list">
              {factors.length ? factors.map(renderFactor) : (
                <p className="security-mfa-empty">{t("securityMfa.noFactors")}</p>
              )}
            </div>

            <div className="security-mfa-factor-counts">
              <span>{t("securityMfa.verifiedCount", { count: verifiedFactors.length })}</span>
              <span>{t("securityMfa.unverifiedCount", { count: unverifiedFactors.length })}</span>
            </div>
          </section>

          <section className="security-mfa-panel security-mfa-enroll-panel">
            <div className="security-mfa-panel-heading">
              <QrCode size={20} />
              <div>
                <h2>{t("securityMfa.enrollTitle")}</h2>
                <p>{t("securityMfa.enrollDescription")}</p>
              </div>
            </div>

            {error && <div className="security-mfa-error" role="alert">{error}</div>}
            {success && <div className="security-mfa-success" role="status">{success}</div>}

            {!enrollment ? (
              <div className="security-mfa-enroll-form">
                <label>
                  {t("securityMfa.friendlyName")}
                  <input
                    type="text"
                    value={friendlyName}
                    onChange={(event) => setFriendlyName(event.target.value)}
                    maxLength={64}
                  />
                </label>

                <button
                  type="button"
                  className="settings-save-button security-mfa-primary"
                  onClick={startEnrollment}
                  disabled={Boolean(busyAction)}
                >
                  {busyAction === "enroll" ? <RefreshCw size={16} /> : <QrCode size={16} />}
                  {busyAction === "enroll" ? t("securityMfa.actions.starting") : t("securityMfa.actions.start")}
                </button>
              </div>
            ) : (
              <div className="security-mfa-verify-flow">
                {qrImageSrc ? (
                  <img className="security-mfa-qr" src={qrImageSrc} alt={t("securityMfa.qrAlt")} />
                ) : enrollment?.totp?.uri ? (
                  <code className="security-mfa-uri">{enrollment.totp.uri}</code>
                ) : null}

                {enrollment?.totp?.uri && qrImageSrc && (
                  <code className="security-mfa-uri">{enrollment.totp.uri}</code>
                )}

                <label>
                  {t("securityMfa.verificationCode")}
                  <input
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    value={verificationCode}
                    onChange={(event) => setVerificationCode(event.target.value)}
                    dir="ltr"
                  />
                </label>

                <div className="security-mfa-actions">
                  <button
                    type="button"
                    className="settings-reset-password-button"
                    onClick={() => {
                      setEnrollment(null);
                      setVerificationCode("");
                    }}
                    disabled={Boolean(busyAction)}
                  >
                    {t("securityMfa.actions.cancel")}
                  </button>
                  <button
                    type="button"
                    className="settings-save-button security-mfa-primary"
                    onClick={verifyEnrollment}
                    disabled={Boolean(busyAction)}
                  >
                    {busyAction === "verify" ? <RefreshCw size={16} /> : <ShieldCheck size={16} />}
                    {busyAction === "verify" ? t("securityMfa.actions.verifying") : t("securityMfa.actions.verify")}
                  </button>
                </div>
              </div>
            )}
          </section>
        </div>
      )}
    </section>
  );
}

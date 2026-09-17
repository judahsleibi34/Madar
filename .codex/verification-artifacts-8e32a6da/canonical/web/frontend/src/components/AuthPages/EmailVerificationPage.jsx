import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { CheckCircle2, MailCheck, RefreshCw, TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  apiFetch,
  getApiUrl,
  postAuthJson,
  readApiError,
  readApiErrorCode,
  readApiResponse,
} from "../../utils/apiClient";
import {
  clearPendingVerificationEmail,
  clearVerificationCallbackFromAddressBar,
  getVerificationErrorState,
  maskEmail,
  readPendingVerificationEmail,
  readVerificationCallback,
} from "./emailVerification";

const FINAL_STATES = new Set(["verified", "expired", "invalid"]);

export default function EmailVerificationPage({ lang = "en" }) {
  const { t } = useTranslation("auth");
  const location = useLocation();
  const navigate = useNavigate();
  const pageDir = lang === "ar" ? "rtl" : "ltr";
  const callback = useMemo(
    () => readVerificationCallback({ hash: location.hash, search: location.search }),
    [location.hash, location.search]
  );
  const pendingEmail =
    String(location.state?.email || "").trim().toLowerCase() ||
    readPendingVerificationEmail();

  const [state, setState] = useState(() => {
    if (callback.hasProviderError) return getVerificationErrorState(callback);
    if (callback.exchangeCode && !callback.accessToken) return "provider_unavailable";
    return "checking";
  });
  const [maskedEmail, setMaskedEmail] = useState(() => maskEmail(pendingEmail));
  const [cooldown, setCooldown] = useState(() =>
    Math.max(0, Number(location.state?.resendAvailableAfter || 0))
  );
  const [message, setMessage] = useState(() =>
    callback.exchangeCode && !callback.accessToken
      ? t("verification.codeExchangeUnavailable")
      : ""
  );
  const [isResending, setIsResending] = useState(false);

  const checkStatus = useCallback(async ({ accessToken = "" } = {}) => {
    setState("checking");
    setMessage("");

    try {
      const headers = new Headers();
      if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

      const response = await apiFetch(getApiUrl("/auth/email-verification/status"), {
        method: "GET",
        cache: "no-store",
        headers,
        skipAuthRefresh: true,
      });
      const data = await readApiResponse(response);

      if (!response.ok) {
        const code = readApiErrorCode(data);
        setState(code === "pending_account_expired" ? "expired" : "provider_unavailable");
        setMessage(readApiError(data, t("verification.providerUnavailable")));
        return;
      }

      const nextState = String(data?.state || data?.account_state || "unknown");
      setState(nextState === "pending_verification" ? "pending" : nextState);
      setCooldown(Math.max(0, Number(data?.resend_available_after || 0)));
      if (data?.masked_email) setMaskedEmail(String(data.masked_email));

      if (nextState === "verified" || nextState === "active") {
        setState("verified");
        clearPendingVerificationEmail();
      }
    } catch {
      setState("provider_unavailable");
      setMessage(t("verification.providerUnavailable"));
    }
  }, [t]);

  useEffect(() => {
    clearVerificationCallbackFromAddressBar({
      pathname: location.pathname,
      search: location.search,
    });

    if (callback.hasProviderError) {
      return;
    }

    if (callback.exchangeCode && !callback.accessToken) {
      return;
    }

    let cancelled = false;
    queueMicrotask(() => {
      if (!cancelled) {
        checkStatus({ accessToken: callback.accessToken });
      }
    });
    return () => {
      cancelled = true;
    };
  }, [callback, checkStatus, location.pathname, location.search]);

  useEffect(() => {
    if (cooldown <= 0) return undefined;

    const timer = window.setInterval(() => {
      setCooldown((current) => Math.max(0, current - 1));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [cooldown]);

  const resendVerification = async () => {
    if (cooldown > 0 || isResending) return;

    setIsResending(true);
    setMessage("");

    try {
      const { response, data } = await postAuthJson(
        "/auth/email-verification/resend",
        pendingEmail ? { email: pendingEmail } : {}
      );

      if (!response.ok) {
        const code = readApiErrorCode(data);
        setMessage(
          code === "email_verification_resend_limited"
            ? t("verification.resendLimited")
            : readApiError(data, t("verification.providerUnavailable"))
        );
        setCooldown(Math.max(0, Number(data?.detail?.context?.resend_available_after || 0)));
        return;
      }

      const responseState = String(data?.state || "pending");
      setState(responseState);
      setCooldown(Math.max(0, Number(data?.resend_available_after || 0)));
      setMessage(
        responseState === "provider_unavailable"
          ? t("verification.providerUnavailable")
          : t("verification.resent")
      );
    } catch {
      setMessage(t("verification.providerUnavailable"));
    } finally {
      setIsResending(false);
    }
  };

  const startAgain = async (event) => {
    event.preventDefault();
    clearPendingVerificationEmail();
    try {
      await postAuthJson("/auth/email-verification/clear-context", {});
    } finally {
      navigate("/signup", { replace: true });
    }
  };

  const isVerified = state === "verified";
  const isFailure = state === "expired" || state === "invalid" || state === "provider_unavailable";
  const canResend = !isVerified && cooldown === 0 && !isResending;
  const Icon = isVerified ? CheckCircle2 : isFailure ? TriangleAlert : MailCheck;
  const title = t(`verification.states.${state}.title`, {
    defaultValue: t("verification.title"),
  });
  const body = t(`verification.states.${state}.body`, {
    defaultValue: t("verification.pendingBody"),
  });

  return (
    <main className="login-page" dir={pageDir}>
      <section className="login-card verification-card" aria-live="polite">
        <div className={`verification-icon verification-icon-${isVerified ? "success" : isFailure ? "error" : "pending"}`}>
          <Icon size={28} aria-hidden="true" />
        </div>

        <div className="login-heading app-page-intro">
          <h1>{title}</h1>
          <p>{body}</p>
        </div>

        {!isVerified && maskedEmail && (
          <p className="verification-destination">
            {t("verification.sentTo")} <strong>{maskedEmail}</strong>
          </p>
        )}

        {!isVerified && <p className="verification-help">{t("verification.spamHelp")}</p>}
        {message && <p className="form-status-message" role="status">{message}</p>}

        <div className="verification-actions">
          {isVerified ? (
            <button className="login-submit" type="button" onClick={() => navigate("/login", { replace: true })}>
              {t("verification.continueToLogin")}
            </button>
          ) : (
            <>
              <button
                className="login-submit"
                type="button"
                disabled={!canResend}
                onClick={resendVerification}
              >
                <RefreshCw size={17} aria-hidden="true" />
                {isResending
                  ? t("verification.resending")
                  : cooldown > 0
                    ? t("verification.resendIn", { seconds: cooldown })
                    : t("verification.resend")}
              </button>

              {!FINAL_STATES.has(state) && (
                <button className="verification-secondary" type="button" onClick={() => checkStatus()}>
                  {t("verification.checkAgain")}
                </button>
              )}
            </>
          )}
        </div>

        {!isVerified && (
          <p className="login-signup-text">
            {t("verification.wrongEmail")} {" "}
            <Link to="/signup" onClick={startAgain}>
              {t("verification.startAgain")}
            </Link>
          </p>
        )}
      </section>
    </main>
  );
}

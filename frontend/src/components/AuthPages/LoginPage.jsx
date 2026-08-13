import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { useTranslation } from "react-i18next";

import { postAuthJson, readApiError, readApiErrorCode } from "../../utils/apiClient";
import AuthToast from "./AuthToast";
import { formatAuthValidationToastMessage, normalizeAuthMessage } from "./authMessages";
import {
  isEmailVerificationRequiredError,
  rememberPendingVerificationEmail,
} from "./emailVerification";

export default function LoginPage({
  lang = "en",
  onLoginSuccess,
  signupPath = "/signup",
  forgotPasswordPath = "/forgot-password",
}) {
  const { t } = useTranslation("auth");
  const location = useLocation();
  const navigate = useNavigate();
  const pageDir = lang === "ar" ? "rtl" : "ltr";

  const [formData, setFormData] = useState({
    email: "",
    password: "",
  });

  const [errors, setErrors] = useState({});
  const [, setStatusMessage] = useState(() =>
    typeof location.state?.message === "string" ? location.state.message : ""
  );
  const [authToast, setAuthToast] = useState(() =>
    typeof location.state?.message === "string"
      ? {
          id: Date.now(),
          type: "success",
          title: t("login.success"),
          message: location.state.message,
        }
      : null
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [mfaStep, setMfaStep] = useState(null);
  const [mfaCode, setMfaCode] = useState("");
  const [isMfaSubmitting, setIsMfaSubmitting] = useState(false);

  const getValidationErrors = (values) => {
    const newErrors = {};

    if (!values.email.trim()) {
      newErrors.email = t("validation.required");
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email)) {
      newErrors.email = t("validation.invalidEmail");
    }

    if (!values.password.trim()) {
      newErrors.password = t("validation.required");
    }

    return newErrors;
  };

  const errorFieldLabels = {
    email: t("login.email"),
    password: t("login.password"),
    mfaCode: t("login.mfaCode"),
  };
  const showAuthToast = ({ type = "error", title, message, kind = "status" }) => {
    setAuthToast({
      id: Date.now(),
      type,
      title,
      message,
      kind,
    });
  };

  const showValidationToast = (validationErrors, title = t("signup.checkFields", { defaultValue: "Please check these fields" })) => {
    showAuthToast({
      type: "error",
      title,
      message: formatAuthValidationToastMessage(validationErrors, errorFieldLabels),
      kind: "validation",
    });
  };

  const handleChange = (event) => {
    const { name, value } = event.target;
    const nextFormData = {
      ...formData,
      [name]: value,
    };

    setFormData(nextFormData);
    const nextErrors = getValidationErrors(nextFormData);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length === 0) setAuthToast(null);
    else if (authToast?.kind === "validation") {
      showValidationToast(nextErrors, authToast.title);
    }

    setStatusMessage("");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    const newErrors = getValidationErrors(formData);
    setErrors(newErrors);

    if (Object.keys(newErrors).length > 0) {
      showValidationToast(newErrors, t("login.loginFailed"));
      return;
    }

    setIsSubmitting(true);
    setStatusMessage("");
    setMfaStep(null);
    setMfaCode("");

    try {
      const { response, data } = await postAuthJson(
        "/auth/login",
        {
          email: formData.email.trim(),
          password: formData.password,
        }
      );

      if (!response.ok) {
        if (response.status === 422 && Array.isArray(data.detail)) {
          const emailError = data.detail.find((error) =>
            error.loc?.includes("email")
          );

          if (emailError) {
            setErrors((prev) => ({
              ...prev,
              email: t("validation.invalidEmail"),
            }));
            showValidationToast({ email: t("validation.invalidEmail") }, t("login.loginFailed"));
            return;
          }

          setStatusMessage(t("login.loginFailed"));
          showAuthToast({
            type: "error",
            title: t("login.loginFailed"),
            message: t("login.loginFailed"),
          });
          return;
        }

        const rawDetail = readApiError(data, "");
        const errorCode = readApiErrorCode(data);

        if (errorCode === "pending_account_expired") {
          navigate("/signup", {
            replace: true,
            state: { accountExpired: true },
          });
          return;
        }

        if (isEmailVerificationRequiredError(data)) {
          const email = rememberPendingVerificationEmail(formData.email);
          navigate("/verify-email", {
            state: {
              email,
              resendAvailableAfter: Number(
                data?.detail?.context?.resend_available_after || 0
              ),
            },
          });
          return;
        }

        const message = normalizeAuthMessage(rawDetail, t("login.serverError"));
        setStatusMessage(message);
        showAuthToast({
          type: "error",
          title: t("login.loginFailed"),
          message,
        });
        return;
      }

      if (data.mfa_required) {
        const factors = Array.isArray(data.factors) ? data.factors : [];
        const firstFactorId = factors[0]?.id || "";

        setMfaStep({
          factors,
          factorId: firstFactorId,
        });
        setStatusMessage(t("login.mfaRequired"));
        showAuthToast({
          type: "error",
          title: t("login.mfaTitle"),
          message: t("login.mfaRequired"),
        });
        return;
      }

      const message = data.mfa_enrollment_recommended
        ? t("login.mfaRecommended")
        : t("login.success");
      setStatusMessage(message);
      showAuthToast({
        type: "success",
        title: t("login.success"),
        message,
      });

      if (onLoginSuccess) {
        onLoginSuccess(data.user);
      }
    } catch (error) {
      console.error(error);
      setStatusMessage(t("login.serverError"));
      showAuthToast({
        type: "error",
        title: t("login.loginFailed"),
        message: t("login.serverError"),
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleMfaSubmit = async (event) => {
    event.preventDefault();

    if (!mfaStep?.factorId) {
      setStatusMessage(t("login.mfaFailed"));
      showAuthToast({
        type: "error",
        title: t("login.mfaFailed"),
        message: t("login.mfaFailed"),
      });
      return;
    }

    if (!mfaCode.trim()) {
      const nextErrors = {
        ...errors,
        mfaCode: t("login.mfaCodeRequired"),
      };
      setErrors((prev) => ({
        ...prev,
        mfaCode: t("login.mfaCodeRequired"),
      }));
      showValidationToast(nextErrors, t("login.mfaFailed"));
      return;
    }

    setIsMfaSubmitting(true);
    setStatusMessage("");
    setErrors((prev) => ({
      ...prev,
      mfaCode: "",
    }));

    try {
      const {
        response: challengeResponse,
        data: challengeData,
      } = await postAuthJson("/auth/mfa/login/challenge", {
        factor_id: mfaStep.factorId,
      });

      if (!challengeResponse.ok) {
        const message = normalizeAuthMessage(challengeData.detail, t("login.serverError"));
        setStatusMessage(message);
        showAuthToast({
          type: "error",
          title: t("login.mfaFailed"),
          message,
        });
        return;
      }

      const {
        response: verifyResponse,
        data: verifyData,
      } = await postAuthJson("/auth/mfa/login/verify", {
        factor_id: mfaStep.factorId,
        challenge_id: challengeData.challenge_id,
        code: mfaCode.trim(),
      });

      if (!verifyResponse.ok) {
        const message = normalizeAuthMessage(verifyData.detail, t("login.mfaFailed"));
        setStatusMessage(message);
        showAuthToast({
          type: "error",
          title: t("login.mfaFailed"),
          message,
        });
        return;
      }

      setStatusMessage(t("login.success"));
      showAuthToast({
        type: "success",
        title: t("login.success"),
        message: t("login.success"),
      });

      if (onLoginSuccess) {
        onLoginSuccess(verifyData.user);
      }
    } catch (error) {
      console.error(error);
      setStatusMessage(t("login.serverError"));
      showAuthToast({
        type: "error",
        title: t("login.mfaFailed"),
        message: t("login.serverError"),
      });
    } finally {
      setIsMfaSubmitting(false);
    }
  };

  const resetMfaStep = () => {
    setMfaStep(null);
    setMfaCode("");
    setErrors((prev) => ({
      ...prev,
      mfaCode: "",
    }));
    setStatusMessage("");
    setAuthToast(null);
  };

  return (
    <main className="login-page" dir={pageDir}>
      <form
        className="login-card"
        onSubmit={mfaStep ? handleMfaSubmit : handleSubmit}
        dir={pageDir}
      >
        <div className="login-heading">
          <h1>{mfaStep ? t("login.mfaTitle") : t("login.title")}</h1>
          <p>{mfaStep ? t("login.mfaSubtitle") : t("login.subtitle")}</p>
        </div>

        {mfaStep ? (
          <>
            {mfaStep.factors.length > 1 && (
              <label>
                {t("login.mfaFactor")}

                <select
                  className="mfa-factor-select"
                  value={mfaStep.factorId}
                  onChange={(event) =>
                    setMfaStep((prev) => ({
                      ...prev,
                      factorId: event.target.value,
                    }))
                  }
                >
                  {mfaStep.factors.map((factor) => (
                    <option key={factor.id} value={factor.id}>
                      {factor.friendly_name || factor.id}
                    </option>
                  ))}
                </select>
              </label>
            )}

            <label>
              {t("login.mfaCode")}

              <input
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder={t("login.mfaCode")}
                value={mfaCode}
                onChange={(event) => {
                  setMfaCode(event.target.value);
                  setErrors((prev) => ({
                    ...prev,
                    mfaCode: "",
                  }));
                  setAuthToast(null);
                  setStatusMessage("");
                }}
                dir="ltr"
              />

            </label>

            <button
              className="login-submit"
              type="submit"
              disabled={isMfaSubmitting}
            >
              {isMfaSubmitting ? t("login.mfaVerifying") : t("login.mfaSubmit")}
            </button>

            <button
              className="auth-secondary-button"
              type="button"
              onClick={resetMfaStep}
              disabled={isMfaSubmitting}
            >
              {t("login.backToLogin")}
            </button>
          </>
        ) : (
          <>
            <label>
              {t("login.email")}

              <input
                type="email"
                name="email"
                placeholder={t("login.email")}
                value={formData.email}
                onChange={handleChange}
                dir="ltr"
              />
            </label>

            <label>
              {t("login.password")}

              <div className="password-field">
                <input
                  type={showPassword ? "text" : "password"}
                  name="password"
                  placeholder={t("login.password")}
                  value={formData.password}
                  onChange={handleChange}
                  dir="ltr"
                />

                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  aria-label={t("login.togglePassword")}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </label>

            <div className="login-options">
              <Link to={forgotPasswordPath}>{t("login.forgotPassword")}</Link>
            </div>

            <button className="login-submit" type="submit" disabled={isSubmitting}>
              {isSubmitting ? t("login.loading") : t("login.submit")}
            </button>

            <p className="login-signup-text">
              {t("login.noAccount")} <Link to={signupPath}>{t("login.signup")}</Link>
            </p>
          </>
        )}
      </form>
      <AuthToast
        key={authToast?.id}
        type={authToast?.type}
        title={authToast?.title}
        message={authToast?.message}
        dir={pageDir}
        onDismiss={() => setAuthToast(null)}
      />
    </main>
  );
}

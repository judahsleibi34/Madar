import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { useTranslation } from "react-i18next";

import { syncCsrfTokenFromResponseData } from "../../utils/apiClient";
import { normalizeAuthMessage } from "./authMessages";

const API_URL = import.meta.env.VITE_API_URL || "/api";

export default function LoginPage({
  lang = "en",
  onLoginSuccess,
  signupPath = "/signup",
  forgotPasswordPath = "/forgot-password",
}) {
  const { t } = useTranslation("auth");
  const location = useLocation();
  const pageDir = lang === "ar" ? "rtl" : "ltr";

  const [formData, setFormData] = useState({
    email: "",
    password: "",
  });

  const [errors, setErrors] = useState({});
  const [statusMessage, setStatusMessage] = useState(() =>
    typeof location.state?.message === "string" ? location.state.message : ""
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [mfaStep, setMfaStep] = useState(null);
  const [mfaCode, setMfaCode] = useState("");
  const [isMfaSubmitting, setIsMfaSubmitting] = useState(false);

  const handleChange = (event) => {
    const { name, value } = event.target;

    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));

    setErrors((prev) => ({
      ...prev,
      [name]: "",
    }));

    setStatusMessage("");
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.email.trim()) {
      newErrors.email = t("validation.required");
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = t("validation.invalidEmail");
    }

    if (!formData.password.trim()) {
      newErrors.password = t("validation.required");
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!validateForm()) return;

    setIsSubmitting(true);
    setStatusMessage("");
    setMfaStep(null);
    setMfaCode("");

    try {
      const response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: formData.email.trim(),
          password: formData.password,
        }),
      });

      const data = await response.json();
      syncCsrfTokenFromResponseData(data);

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
            return;
          }

          setStatusMessage(t("login.loginFailed"));
          return;
        }

        setStatusMessage(
          normalizeAuthMessage(data.detail, t("login.loginFailed"))
        );
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
        return;
      }

      setStatusMessage(
        data.mfa_enrollment_recommended
          ? t("login.mfaRecommended")
          : t("login.success")
      );

      if (onLoginSuccess) {
        onLoginSuccess(data.user);
      }
    } catch (error) {
      console.error(error);
      setStatusMessage(t("login.serverError"));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleMfaSubmit = async (event) => {
    event.preventDefault();

    if (!mfaStep?.factorId) {
      setStatusMessage(t("login.mfaFailed"));
      return;
    }

    if (!mfaCode.trim()) {
      setErrors((prev) => ({
        ...prev,
        mfaCode: t("login.mfaCodeRequired"),
      }));
      return;
    }

    setIsMfaSubmitting(true);
    setStatusMessage("");
    setErrors((prev) => ({
      ...prev,
      mfaCode: "",
    }));

    try {
      const challengeResponse = await fetch(`${API_URL}/auth/mfa/login/challenge`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ factor_id: mfaStep.factorId }),
      });
      const challengeData = await challengeResponse.json();

      if (!challengeResponse.ok) {
        setStatusMessage(
          typeof challengeData.detail === "string"
            ? challengeData.detail
            : t("login.mfaFailed")
        );
        return;
      }

      const verifyResponse = await fetch(`${API_URL}/auth/mfa/login/verify`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          factor_id: mfaStep.factorId,
          challenge_id: challengeData.challenge_id,
          code: mfaCode.trim(),
        }),
      });
      const verifyData = await verifyResponse.json();
      syncCsrfTokenFromResponseData(verifyData);

      if (!verifyResponse.ok) {
        setStatusMessage(
          typeof verifyData.detail === "string"
            ? verifyData.detail
            : t("login.mfaFailed")
        );
        return;
      }

      setStatusMessage(t("login.success"));

      if (onLoginSuccess) {
        onLoginSuccess(verifyData.user);
      }
    } catch (error) {
      console.error(error);
      setStatusMessage(t("login.serverError"));
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

        {statusMessage && (
          <p className="form-status-message">{statusMessage}</p>
        )}

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
                  setStatusMessage("");
                }}
                dir="ltr"
              />

              {errors.mfaCode && <span>{errors.mfaCode}</span>}
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

              {errors.email && <span>{errors.email}</span>}
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

              {errors.password && <span>{errors.password}</span>}
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
    </main>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { useTranslation } from "react-i18next";
import { postAuthJson, readApiError, readApiErrorCode } from "../../utils/apiClient";
import { normalizeAuthMessage } from "./authMessages";
import { meetsMinimumPasswordPolicy, PASSWORD_MIN_LENGTH } from "./passwordPolicy";
import { readRecoveryContext } from "./resetPasswordRecovery";

export default function ResetPasswordPage({ lang = "en" }) {
  const { t } = useTranslation("auth");
  const navigate = useNavigate();
  const pageDir = lang === "ar" ? "rtl" : "ltr";

  const [recoveryContext] = useState(readRecoveryContext);
  const accessToken = recoveryContext.accessToken;
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState(() =>
    accessToken
      ? ""
      : t("resetPassword.invalidToken")
  );
  const [statusMessage, setStatusMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    query.delete("request_token");
    const cleanQuery = query.toString();
    window.history.replaceState(
      window.history.state,
      document.title,
      `${window.location.pathname}${cleanQuery ? `?${cleanQuery}` : ""}`
    );
  }, []);

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!password) return setError(t("validation.required"));
    if (!meetsMinimumPasswordPolicy(password)) {
      return setError(t("resetPassword.passwordShort"));
    }
    if (password !== confirm) return setError(t("resetPassword.passwordMismatch"));

    setIsSubmitting(true);
    setError("");

    try {
      const { response, data } = await postAuthJson(
        "/auth/password-reset",
        {
          access_token: accessToken,
          password,
          ...(recoveryContext.requestToken
            ? { request_token: recoveryContext.requestToken }
            : {}),
        }
      );

      if (!response.ok) {
        const code = readApiErrorCode(data);
        const codeMessages = {
          password_policy_failed: t("resetPassword.passwordShort"),
          password_reset_expired: t("resetPassword.expired"),
          password_reset_replayed: t("resetPassword.replayed"),
          password_reset_in_progress: t("resetPassword.inProgress"),
          password_reset_invalid: t("resetPassword.invalidToken"),
          email_verification_required: t("login.emailNotVerified"),
        };
        setError(
          codeMessages[code] ||
          normalizeAuthMessage(
            readApiError(data, ""),
            t("resetPassword.unknownError")
          )
        );
        return;
      }

      setStatusMessage(t("resetPassword.success"));
      setTimeout(() => navigate("/login"), 2000);
    } catch (err) {
      console.error(err);
      setError(t("resetPassword.serverError"));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="login-page" dir={pageDir}>
      <form className="login-card" onSubmit={handleSubmit} dir={pageDir}>
        <div className="login-heading app-page-intro">
          <h1>{t("resetPassword.title")}</h1>
          <p>{t("resetPassword.subtitle")}</p>
        </div>

        {statusMessage && <p className="form-status-message">{statusMessage}</p>}
        {error && <p className="form-status-message">{error}</p>}

        {accessToken && !statusMessage && (
          <>
            <label>
              {t("resetPassword.password")}
              <div className="password-field">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  minLength={PASSWORD_MIN_LENGTH}
                  onChange={(event) => {
                    setPassword(event.target.value);
                    setError("");
                  }}
                  dir="ltr"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  aria-label={t("resetPassword.togglePassword")}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </label>

            <label>
              {t("resetPassword.confirmPassword")}
              <div className="password-field">
                <input
                  type={showConfirmPassword ? "text" : "password"}
                  value={confirm}
                  minLength={PASSWORD_MIN_LENGTH}
                  onChange={(event) => {
                    setConfirm(event.target.value);
                    setError("");
                  }}
                  dir="ltr"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword((prev) => !prev)}
                  aria-label={t("resetPassword.togglePassword")}
                >
                  {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </label>

            <button className="login-submit" type="submit" disabled={isSubmitting}>
              {isSubmitting ? t("resetPassword.loading") : t("resetPassword.submit")}
            </button>
          </>
        )}

        <p className="login-signup-text">
          <Link to="/login">{t("resetPassword.backToLogin")}</Link>
        </p>
      </form>
    </main>
  );
}

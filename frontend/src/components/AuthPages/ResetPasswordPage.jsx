import { useState } from "react";
import { Link } from "react-router-dom";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { useTranslation } from "react-i18next";

const readRecoveryToken = () => {
  const hash = window.location.hash;
  const params = new URLSearchParams(hash.replace("#", ""));
  const token = params.get("access_token");
  const type = params.get("type");

  return token && type === "recovery" ? token : null;
};

export default function ResetPasswordPage({ lang = "en" }) {
  const { t } = useTranslation("auth");
  const navigate = useNavigate();
  const pageDir = lang === "ar" ? "rtl" : "ltr";

  const [accessToken] = useState(readRecoveryToken);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState(() =>
    accessToken ? "" : t("resetPassword.invalidToken")
  );
  const [statusMessage, setStatusMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!password) return setError(t("validation.required"));
    if (password.length < 6) return setError(t("resetPassword.passwordShort"));
    if (password !== confirm) return setError(t("resetPassword.passwordMismatch"));

    setIsSubmitting(true);
    setError("");

    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL || "/api"}/auth/password-reset`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ access_token: accessToken, password }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        setError(data.detail || t("resetPassword.unknownError"));
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
        <div className="login-heading">
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

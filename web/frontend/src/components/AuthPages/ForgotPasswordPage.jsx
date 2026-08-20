import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { postAuthJson } from "../../utils/apiClient";
import { normalizeAuthMessage } from "./authMessages";

export default function ForgotPasswordPage({ lang = "en", loginPath = "/login" }) {
  const { t } = useTranslation("auth");
  const pageDir = lang === "ar" ? "rtl" : "ltr";

  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  const handleChange = (event) => {
    setEmail(event.target.value);
    setError("");
    setStatusMessage("");
  };

  const validateForm = () => {
    if (!email.trim()) {
      setError(t("validation.required"));
      return false;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError(t("validation.invalidEmail"));
      return false;
    }

    return true;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!validateForm()) return;

    setIsSubmitting(true);
    setStatusMessage("");

    try {
      const { response, data } = await postAuthJson(
        "/auth/forgot-password",
        { email: email.trim() }
      );

      if (!response.ok) {
        if (response.status === 404) {
          setStatusMessage(t("forgotPassword.notFound"));
          return;
        }

        setStatusMessage(normalizeAuthMessage(data.detail, t("forgotPassword.unknownError")));
        return;
      }

      setStatusMessage(t("forgotPassword.success"));
      setSent(true);
    } catch (error) {
      console.error(error);
      setStatusMessage(t("forgotPassword.serverError"));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="login-page" dir={pageDir}>
      <form className="login-card" onSubmit={handleSubmit} dir={pageDir}>
        <div className="login-heading">
          <h1>{t("forgotPassword.title")}</h1>
          <p>{t("forgotPassword.subtitle")}</p>
        </div>

        {statusMessage && (
          <p className="form-status-message">{statusMessage}</p>
        )}

        {!sent && (
          <>
            <label>
              {t("forgotPassword.email")}
              <input
                type="email"
                name="email"
                placeholder={t("forgotPassword.email")}
                value={email}
                onChange={handleChange}
                dir="ltr"
              />
              {error && <span>{error}</span>}
            </label>

            <button className="login-submit" type="submit" disabled={isSubmitting}>
              {isSubmitting ? t("forgotPassword.loading") : t("forgotPassword.submit")}
            </button>
          </>
        )}

        <p className="login-signup-text">
          <Link to={loginPath}>{t("forgotPassword.backToLogin")}</Link>
        </p>
      </form>
    </main>
  );
}

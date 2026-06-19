import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { useTranslation } from "react-i18next";

import { syncCsrfTokenFromResponseData } from "../../utils/apiClient";

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
          typeof data.detail === "string" ? data.detail : t("login.loginFailed")
        );
        return;
      }

      setStatusMessage(t("login.success"));

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

  return (
    <main className="login-page" dir={pageDir}>
      <form className="login-card" onSubmit={handleSubmit} dir={pageDir}>
        <div className="login-heading">
          <h1>{t("login.title")}</h1>
          <p>{t("login.subtitle")}</p>
        </div>

        {statusMessage && (
          <p className="form-status-message">{statusMessage}</p>
        )}

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
      </form>
    </main>
  );
}

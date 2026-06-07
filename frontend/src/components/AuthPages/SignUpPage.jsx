import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { useTranslation } from "react-i18next";

const API_URL = import.meta.env.VITE_API_URL || "/api";

export default function SignUpPage({
  lang = "en",
  loginPath = "/login",
  onSignupSuccess,
}) {
  const { t } = useTranslation("auth");
  const navigate = useNavigate();
  const pageDir = lang === "ar" ? "rtl" : "ltr";

  const [formData, setFormData] = useState({
    firstName: "",
    lastName: "",
    email: "",
    password: "",
    confirmPassword: "",
  });

  const [errors, setErrors] = useState({});
  const [statusMessage, setStatusMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => ({ ...prev, [name]: "" }));
    setStatusMessage("");
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.firstName.trim()) newErrors.firstName = t("validation.required");
    if (!formData.lastName.trim()) newErrors.lastName = t("validation.required");
    if (!formData.email.trim()) newErrors.email = t("validation.required");
    if (!formData.password.trim()) newErrors.password = t("validation.required");
    if (!formData.confirmPassword.trim()) {
      newErrors.confirmPassword = t("validation.required");
    }

    if (formData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = t("validation.invalidEmail");
    }

    const passwordRegex =
      /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{8,}$/;
    if (formData.password && !passwordRegex.test(formData.password)) {
      newErrors.password = t("signup.passwordInvalid");
    }

    if (
      formData.password &&
      formData.confirmPassword &&
      formData.password !== formData.confirmPassword
    ) {
      newErrors.confirmPassword = t("signup.passwordMismatch");
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
      const response = await fetch(`${API_URL}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          first_name: formData.firstName.trim(),
          last_name: formData.lastName.trim(),
          email: formData.email.trim(),
          password: formData.password,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        if (response.status === 422 && Array.isArray(data.detail)) {
          const newErrors = {};

          data.detail.forEach((error) => {
            const field = error.loc?.[1];

            if (field === "email") {
              newErrors.email = t("validation.invalidEmail");
            }

            if (field === "first_name") {
              newErrors.firstName = t("validation.required");
            }

            if (field === "last_name") {
              newErrors.lastName = t("validation.required");
            }

            if (field === "password") {
              newErrors.password = error.msg || t("validation.required");
            }
          });

          setErrors((prev) => ({
            ...prev,
            ...newErrors,
          }));

          setStatusMessage("");
          return;
        }

        if (
          typeof data.detail === "string" &&
          data.detail.toLowerCase().includes("already registered")
        ) {
          setStatusMessage(t("signup.alreadyRegistered"));
          return;
        }

        setStatusMessage(
          typeof data.detail === "string" ? data.detail : t("signup.signupFailed")
        );
        return;
      }

      setStatusMessage(t("signup.success"));
      setTimeout(() => {
        if (onSignupSuccess) {
          onSignupSuccess();
          return;
        }

        navigate(loginPath);
      }, 1500);
    } catch (error) {
      console.error(error);
      setStatusMessage(t("login.serverError"));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="register-page" dir={pageDir}>
      <form className="login-card register-card" onSubmit={handleSubmit} dir={pageDir}>
        <div className="login-heading">
          <h1>{t("signup.title")}</h1>
          <p>{t("signup.subtitle")}</p>
        </div>

        {statusMessage && (
          <p className="form-status-message">{statusMessage}</p>
        )}

        <div className="register-row">
          <label>
            {t("signup.firstName")}
            <input
              type="text"
              name="firstName"
              placeholder={t("signup.firstName")}
              value={formData.firstName}
              onChange={handleChange}
            />
            {errors.firstName && <span>{errors.firstName}</span>}
          </label>

          <label>
            {t("signup.lastName")}
            <input
              type="text"
              name="lastName"
              placeholder={t("signup.lastName")}
              value={formData.lastName}
              onChange={handleChange}
            />
            {errors.lastName && <span>{errors.lastName}</span>}
          </label>
        </div>

        <label>
          {t("signup.email")}
          <input
            type="email"
            name="email"
            placeholder={t("signup.email")}
            value={formData.email}
            onChange={handleChange}
            dir="ltr"
          />
          {errors.email && <span>{errors.email}</span>}
        </label>

        <label>
          {t("signup.password")}
          <div className="password-field">
            <input
              type={showPassword ? "text" : "password"}
              name="password"
              placeholder={t("signup.password")}
              value={formData.password}
              onChange={handleChange}
              dir="ltr"
            />
            <button
              type="button"
              onClick={() => setShowPassword((prev) => !prev)}
              aria-label={t("signup.togglePassword")}
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
          {errors.password && <span>{errors.password}</span>}
        </label>

        <label>
          {t("signup.confirmPassword")}
          <div className="password-field">
            <input
              type={showConfirmPassword ? "text" : "password"}
              name="confirmPassword"
              placeholder={t("signup.confirmPassword")}
              value={formData.confirmPassword}
              onChange={handleChange}
              dir="ltr"
            />
            <button
              type="button"
              onClick={() => setShowConfirmPassword((prev) => !prev)}
              aria-label={t("signup.toggleConfirmPassword")}
            >
              {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
          {errors.confirmPassword && <span>{errors.confirmPassword}</span>}
        </label>

        <button
          className="login-submit register-submit"
          type="submit"
          disabled={isSubmitting}
        >
          {isSubmitting ? t("signup.loading") : t("signup.submit")}
        </button>

        <p className="login-signup-text">
          {t("signup.hasAccount")} <Link to={loginPath}>{t("signup.login")}</Link>
        </p>
      </form>
    </main>
  );
}

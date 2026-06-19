import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { useTranslation } from "react-i18next";

const API_URL = import.meta.env.VITE_API_URL || "/api";
const PUBLIC_SITE_DOMAIN = import.meta.env.VITE_PUBLIC_SITE_DOMAIN || "";

const SUBDOMAIN_PATTERN = /^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$/;

const getApiDetail = (data) => {
  if (typeof data?.detail === "string") return data.detail;
  if (typeof data?.message === "string") return data.message;
  return "";
};

export default function SignUpPage({
  lang = "en",
  loginPath = "/login",
  onSignupSuccess,
  mode = "tenant",
}) {
  const { t } = useTranslation("auth");
  const navigate = useNavigate();
  const pageDir = lang === "ar" ? "rtl" : "ltr";
  const isTenantOnboarding = mode === "tenant";

  const [formData, setFormData] = useState({
    firstName: "",
    lastName: "",
    email: "",
    password: "",
    confirmPassword: "",
    businessName: "",
    businessType: "",
    subdomain: "",
  });

  const [errors, setErrors] = useState({});
  const [statusMessage, setStatusMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const normalizedSubdomain = useMemo(
    () => formData.subdomain.trim().toLowerCase(),
    [formData.subdomain]
  );

  const previewSubdomain = normalizedSubdomain || "your-site";
  const publicUrlPreview = PUBLIC_SITE_DOMAIN
    ? `${previewSubdomain}.${PUBLIC_SITE_DOMAIN}`
    : previewSubdomain;
  const publicUrlPreviewLabel = PUBLIC_SITE_DOMAIN
    ? t("signup.publicUrlAfterPublishing")
    : t("signup.subdomainPreview");

  const handleChange = (event) => {
    const { name, value } = event.target;
    const nextValue = name === "subdomain" ? value.toLowerCase() : value;

    setFormData((prev) => ({ ...prev, [name]: nextValue }));
    setErrors((prev) => ({ ...prev, [name]: "" }));
    setStatusMessage("");
  };

  const validateSubdomain = (newErrors) => {
    if (!isTenantOnboarding) return;

    if (!normalizedSubdomain) {
      newErrors.subdomain = t("validation.required");
      return;
    }

    if (normalizedSubdomain.length < 3) {
      newErrors.subdomain = t("signup.subdomainTooShort");
      return;
    }

    if (!SUBDOMAIN_PATTERN.test(normalizedSubdomain)) {
      newErrors.subdomain = t("signup.subdomainInvalid");
    }
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

    if (isTenantOnboarding) {
      if (!formData.businessName.trim()) {
        newErrors.businessName = t("validation.required");
      }
      if (!formData.businessType.trim()) {
        newErrors.businessType = t("validation.required");
      }
      validateSubdomain(newErrors);
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

  const getRequestPayload = () => {
    const basePayload = {
      first_name: formData.firstName.trim(),
      last_name: formData.lastName.trim(),
      email: formData.email.trim(),
      password: formData.password,
    };

    if (!isTenantOnboarding) return basePayload;

    return {
      ...basePayload,
      business_name: formData.businessName.trim(),
      business_type: formData.businessType.trim(),
      subdomain: normalizedSubdomain,
    };
  };

  const applyApiErrors = (response, data) => {
    if (response.status === 422 && Array.isArray(data.detail)) {
      const newErrors = {};

      data.detail.forEach((error) => {
        const field = error.loc?.[1];

        if (field === "email") newErrors.email = t("validation.invalidEmail");
        if (field === "first_name") newErrors.firstName = t("validation.required");
        if (field === "last_name") newErrors.lastName = t("validation.required");
        if (field === "business_name") newErrors.businessName = t("validation.required");
        if (field === "business_type") newErrors.businessType = t("validation.required");
        if (field === "subdomain") newErrors.subdomain = error.msg || t("signup.subdomainInvalid");
        if (field === "password") newErrors.password = error.msg || t("validation.required");
      });

      setErrors((prev) => ({ ...prev, ...newErrors }));
      setStatusMessage("");
      return true;
    }

    const detail = getApiDetail(data).toLowerCase();

    if (detail.includes("already registered")) {
      setStatusMessage(t("signup.alreadyRegistered"));
      return true;
    }

    if (detail.includes("subdomain") && detail.includes("taken")) {
      setErrors((prev) => ({ ...prev, subdomain: t("signup.subdomainTaken") }));
      setStatusMessage("");
      return true;
    }

    if (detail.includes("reserved")) {
      setErrors((prev) => ({ ...prev, subdomain: t("signup.subdomainReserved") }));
      setStatusMessage("");
      return true;
    }

    if (detail.includes("subdomain") || detail.includes("invalid")) {
      setErrors((prev) => ({ ...prev, subdomain: t("signup.subdomainInvalid") }));
      setStatusMessage("");
      return true;
    }

    return false;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!validateForm()) return;

    setIsSubmitting(true);
    setStatusMessage("");

    try {
      const response = await fetch(
        `${API_URL}${isTenantOnboarding ? "/auth/signup/onboard" : "/auth/signup"}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(getRequestPayload()),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        if (applyApiErrors(response, data)) return;

        setStatusMessage(
          typeof data.detail === "string" ? data.detail : t("signup.signupFailed")
        );
        return;
      }

      setStatusMessage(
        isTenantOnboarding ? t("signup.onboardingSuccess") : t("signup.success")
      );
      setTimeout(() => {
        if (onSignupSuccess) {
          onSignupSuccess();
          return;
        }

        navigate(loginPath, {
          state: isTenantOnboarding
            ? { message: t("signup.onboardingSuccess") }
            : undefined,
        });
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

        {isTenantOnboarding && (
          <div className="auth-section-title">{t("signup.accountSection")}</div>
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

        {isTenantOnboarding && (
          <>
            <div className="auth-section-title">{t("signup.businessSection")}</div>

            <label>
              {t("signup.businessName")}
              <input
                type="text"
                name="businessName"
                placeholder={t("signup.businessNamePlaceholder")}
                value={formData.businessName}
                onChange={handleChange}
              />
              {errors.businessName && <span>{errors.businessName}</span>}
            </label>

            <label>
              {t("signup.businessType")}
              <input
                type="text"
                name="businessType"
                placeholder={t("signup.businessTypePlaceholder")}
                value={formData.businessType}
                onChange={handleChange}
              />
              {errors.businessType && <span>{errors.businessType}</span>}
            </label>

            <label>
              {t("signup.subdomain")}
              <input
                type="text"
                name="subdomain"
                placeholder={t("signup.subdomainPlaceholder")}
                value={formData.subdomain}
                onChange={handleChange}
                dir="ltr"
                autoCapitalize="none"
                autoCorrect="off"
              />
              <small className="subdomain-preview">
                {publicUrlPreviewLabel}: {publicUrlPreview}
              </small>
              {errors.subdomain && <span>{errors.subdomain}</span>}
            </label>
          </>
        )}

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

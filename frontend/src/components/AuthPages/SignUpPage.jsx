import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { useTranslation } from "react-i18next";
import { postAuthJson, readApiError } from "../../utils/apiClient";
import AuthToast from "./AuthToast";
import { formatAuthValidationToastMessage, normalizeAuthMessage } from "./authMessages";
import { rememberPendingVerificationEmail } from "./emailVerification";
import { meetsMinimumPasswordPolicy, PASSWORD_MIN_LENGTH } from "./passwordPolicy";

const PUBLIC_SITE_DOMAIN = import.meta.env.VITE_PUBLIC_SITE_DOMAIN || "";

const SUBDOMAIN_PATTERN = /^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$/;
const DIGIT_PATTERN = /\p{N}/u;
const SAFE_PERSON_NAME_PATTERN = /^[\p{L}\s.'\u2019-]+$/u;
const SAFE_BUSINESS_TEXT_PATTERN = /^[\p{L}\s.'\u2019&/(),-]+$/u;

export default function SignUpPage({
  lang = "en",
  loginPath = "/login",
  mode = "account",
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
  const [, setStatusMessage] = useState("");
  const [authToast, setAuthToast] = useState(null);
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
  const errorFieldLabels = {
    firstName: t("signup.firstName"),
    lastName: t("signup.lastName"),
    email: t("signup.email"),
    password: t("signup.password"),
    confirmPassword: t("signup.confirmPassword"),
    businessName: t("signup.businessName"),
    businessType: t("signup.businessType"),
    subdomain: t("signup.subdomain"),
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

  const showValidationToast = (validationErrors) => {
    showAuthToast({
      type: "error",
      title: t("signup.checkFields", { defaultValue: "Please check these fields" }),
      message: formatAuthValidationToastMessage(validationErrors, errorFieldLabels),
      kind: "validation",
    });
  };

  const getErrorProps = (fieldName) => {
    const message = errors[fieldName];

    if (!message) {
      return {};
    }

    return {
      "aria-invalid": "true",
      "aria-describedby": `signup-${fieldName}-error`,
      className: "auth-field-error-input",
    };
  };

  const renderFieldError = (fieldName) => {
    const message = errors[fieldName];

    if (!message) return null;

    return (
      <span className="auth-field-error" id={`signup-${fieldName}-error`} role="alert">
        {message}
      </span>
    );
  };

  const validateSubdomain = (newErrors, values = formData) => {
    if (!isTenantOnboarding) return;
    const cleanSubdomain = values.subdomain.trim().toLowerCase();

    if (!cleanSubdomain) {
      return;
    }

    if (cleanSubdomain.length < 3) {
      newErrors.subdomain = t("signup.subdomainTooShort");
      return;
    }

    if (!SUBDOMAIN_PATTERN.test(cleanSubdomain)) {
      newErrors.subdomain = t("signup.subdomainInvalid");
    }
  };

  const getTextOnlyMessage = (fieldLabel) =>
    t("validation.textOnly", {
      defaultValue: `${fieldLabel} can only contain letters and normal punctuation.`,
    });

  const validateTextValue = (
    newErrors,
    value,
    fieldName,
    fieldLabel,
    pattern,
    { required = true } = {}
  ) => {
    const cleanValue = value.trim();

    if (!cleanValue) {
      if (required) newErrors[fieldName] = t("validation.required");
      return;
    }

    if (
      DIGIT_PATTERN.test(cleanValue) ||
      !/\p{L}/u.test(cleanValue) ||
      !pattern.test(cleanValue)
    ) {
      newErrors[fieldName] = getTextOnlyMessage(fieldLabel);
    }
  };

  const applyFriendlyDetailError = (detail) => {
    const safeDetail = String(detail || "").toLowerCase();
    const nextErrors = {};

    if (safeDetail.includes("already registered")) {
      setStatusMessage(t("signup.alreadyRegistered"));
      showAuthToast({
        type: "error",
        title: t("signup.signupFailed"),
        message: t("signup.alreadyRegistered"),
      });
      return true;
    }

    if (safeDetail.includes("first name")) {
      nextErrors.firstName = safeDetail.includes("required")
        ? t("validation.required")
        : getTextOnlyMessage(t("signup.firstName"));
    }

    if (safeDetail.includes("last name")) {
      nextErrors.lastName = safeDetail.includes("required")
        ? t("validation.required")
        : getTextOnlyMessage(t("signup.lastName"));
    }

    if (safeDetail.includes("business name")) {
      nextErrors.businessName = getTextOnlyMessage(t("signup.businessName"));
    }

    if (safeDetail.includes("business type")) {
      nextErrors.businessType = getTextOnlyMessage(t("signup.businessType"));
    }

    if (safeDetail.includes("password")) {
      nextErrors.password = safeDetail.includes("8 characters")
        ? t("signup.passwordInvalid")
        : t("validation.required");
    }

    if (safeDetail.includes("email")) {
      nextErrors.email = safeDetail.includes("registered")
        ? ""
        : t("validation.invalidEmail");
    }

    if (safeDetail.includes("subdomain") && safeDetail.includes("taken")) {
      nextErrors.subdomain = t("signup.subdomainTaken");
    } else if (safeDetail.includes("reserved")) {
      nextErrors.subdomain = t("signup.subdomainReserved");
    } else if (safeDetail.includes("subdomain") || safeDetail.includes("invalid subdomain")) {
      nextErrors.subdomain = t("signup.subdomainInvalid");
    }

    const cleanErrors = Object.fromEntries(
      Object.entries(nextErrors).filter(([, message]) => message)
    );

    if (Object.keys(cleanErrors).length > 0) {
      setErrors((prev) => ({ ...prev, ...cleanErrors }));
      setStatusMessage("");
      showValidationToast(cleanErrors);
      return true;
    }

    return false;
  };

  const getValidationErrors = (values = formData) => {
    const newErrors = {};

    validateTextValue(
      newErrors,
      values.firstName,
      "firstName",
      t("signup.firstName"),
      SAFE_PERSON_NAME_PATTERN
    );
    validateTextValue(
      newErrors,
      values.lastName,
      "lastName",
      t("signup.lastName"),
      SAFE_PERSON_NAME_PATTERN
    );
    if (!values.email.trim()) newErrors.email = t("validation.required");
    if (!values.password.trim()) newErrors.password = t("validation.required");
    if (!values.confirmPassword.trim()) {
      newErrors.confirmPassword = t("validation.required");
    }

    if (isTenantOnboarding) {
      validateTextValue(
        newErrors,
        values.businessName,
        "businessName",
        t("signup.businessName"),
        SAFE_BUSINESS_TEXT_PATTERN,
        { required: false }
      );
      validateTextValue(
        newErrors,
        values.businessType,
        "businessType",
        t("signup.businessType"),
        SAFE_BUSINESS_TEXT_PATTERN,
        { required: false }
      );
      validateSubdomain(newErrors, values);
    }

    if (values.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email)) {
      newErrors.email = t("validation.invalidEmail");
    }

    if (
      values.password &&
      !meetsMinimumPasswordPolicy(values.password)
    ) {
      newErrors.password = t("signup.passwordInvalid");
    }

    if (
      values.password &&
      values.confirmPassword &&
      values.password !== values.confirmPassword
    ) {
      newErrors.confirmPassword = t("signup.passwordMismatch");
    }

    return newErrors;
  };

  const handleChange = (event) => {
    const { name, value } = event.target;
    const nextValue = name === "subdomain" ? value.toLowerCase() : value;
    const nextFormData = { ...formData, [name]: nextValue };

    setFormData(nextFormData);
    const nextErrors = getValidationErrors(nextFormData);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length === 0) setAuthToast(null);
    else if (authToast?.kind === "validation") {
      showValidationToast(nextErrors);
    }
    setStatusMessage("");
  };

  const getRequestPayload = () => {
    const payload = {
      first_name: formData.firstName.trim(),
      last_name: formData.lastName.trim(),
      email: formData.email.trim(),
      password: formData.password,
    };

    if (isTenantOnboarding) {
      payload.business_name = formData.businessName.trim() || null;
      payload.business_type = formData.businessType.trim() || null;
      payload.subdomain = normalizedSubdomain || null;
    }

    return payload;
  };

  const applyApiErrors = (response, data) => {
    if (response.status === 422 && Array.isArray(data.detail)) {
      const newErrors = {};

      data.detail.forEach((error) => {
        const field = error.loc?.[1];

        if (field === "email") newErrors.email = t("validation.invalidEmail");
        if (field === "first_name") newErrors.firstName = t("validation.required");
        if (field === "last_name") newErrors.lastName = t("validation.required");
        if (field === "business_name") newErrors.businessName = getTextOnlyMessage(t("signup.businessName"));
        if (field === "business_type") newErrors.businessType = getTextOnlyMessage(t("signup.businessType"));
        if (field === "subdomain") newErrors.subdomain = t("signup.subdomainInvalid");
        if (field === "password") newErrors.password = error.msg || t("validation.required");
      });

      setErrors((prev) => ({ ...prev, ...newErrors }));
      setStatusMessage("");
      showValidationToast(newErrors);
      return true;
    }

    const detail = readApiError(data, "").toLowerCase();

    if (applyFriendlyDetailError(detail)) return true;

    return false;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    const newErrors = getValidationErrors(formData);
    setErrors(newErrors);

    if (Object.keys(newErrors).length > 0) {
      showValidationToast(newErrors);
      return;
    }

    setIsSubmitting(true);
    setStatusMessage("");

    try {
      const { response, data } = await postAuthJson(
        "/auth/signup",
        getRequestPayload()
      );

      if (!response.ok) {
        if (applyApiErrors(response, data)) return;

        const message = normalizeAuthMessage(readApiError(data, ""), t("signup.signupFailed"));
        setStatusMessage(message);
        showAuthToast({
          type: "error",
          title: t("signup.signupFailed"),
          message,
        });
        return;
      }

      const message = data.requires_email_verification
        ? t("signup.verifyEmail")
        : t("signup.success");
      setStatusMessage(message);

      if (data.requires_email_verification) {
        setAuthToast(null);
        const email = rememberPendingVerificationEmail(formData.email);
        navigate("/verify-email", {
          replace: true,
          state: {
            email,
            resendAvailableAfter: Number(data.resend_available_after || 0),
          },
        });
        return;
      }

      showAuthToast({
        type: "success",
        title: t("signup.success"),
        message,
      });
    } catch (error) {
      console.error(error);
      setStatusMessage(t("login.serverError"));
      showAuthToast({
        type: "error",
        title: t("signup.signupFailed"),
        message: t("login.serverError"),
      });
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
              {...getErrorProps("firstName")}
            />
            {renderFieldError("firstName")}
          </label>

          <label>
            {t("signup.lastName")}
            <input
              type="text"
              name="lastName"
              placeholder={t("signup.lastName")}
              value={formData.lastName}
              onChange={handleChange}
              {...getErrorProps("lastName")}
            />
            {renderFieldError("lastName")}
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
            {...getErrorProps("email")}
          />
          {renderFieldError("email")}
        </label>

        <label>
          {t("signup.password")}
          <div className="password-field">
            <input
              type={showPassword ? "text" : "password"}
              name="password"
              placeholder={t("signup.password")}
              value={formData.password}
              minLength={PASSWORD_MIN_LENGTH}
              onChange={handleChange}
              dir="ltr"
              {...getErrorProps("password")}
            />
            <button
              type="button"
              onClick={() => setShowPassword((prev) => !prev)}
              aria-label={t("signup.togglePassword")}
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
          {renderFieldError("password")}
        </label>

        <label>
          {t("signup.confirmPassword")}
          <div className="password-field">
            <input
              type={showConfirmPassword ? "text" : "password"}
              name="confirmPassword"
              placeholder={t("signup.confirmPassword")}
              value={formData.confirmPassword}
              minLength={PASSWORD_MIN_LENGTH}
              onChange={handleChange}
              dir="ltr"
              {...getErrorProps("confirmPassword")}
            />
            <button
              type="button"
              onClick={() => setShowConfirmPassword((prev) => !prev)}
              aria-label={t("signup.toggleConfirmPassword")}
            >
              {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
          {renderFieldError("confirmPassword")}
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
                {...getErrorProps("businessName")}
              />
              {renderFieldError("businessName")}
            </label>

            <label>
              {t("signup.businessType")}
              <input
                type="text"
                name="businessType"
                placeholder={t("signup.businessTypePlaceholder")}
                value={formData.businessType}
                onChange={handleChange}
                {...getErrorProps("businessType")}
              />
              {renderFieldError("businessType")}
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
                {...getErrorProps("subdomain")}
              />
              {renderFieldError("subdomain")}
              <small className="subdomain-preview">
                {publicUrlPreviewLabel}: {publicUrlPreview}
              </small>
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

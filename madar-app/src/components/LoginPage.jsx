import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
console.log("LOGIN API_URL:", API_URL);

const pageText = {
  en: {
    title: "Log In",
    subtitle: "Welcome back. Log in to continue to your Madar account.",
    email: "Email",
    password: "Password",
    forgotPassword: "Forgot password?",
    button: "Log In",
    loading: "Logging in...",
    success: "User is logged in! Redirecting...",
    serverError: "Could not connect to backend.",
    loginFailed: "Login failed.",
    noAccount: "Don't have an account?",
    signup: "Sign Up",
    required: "This field is required.",
    invalidEmail: "Please enter a valid email address.",
  },
  ar: {
    title: "تسجيل الدخول",
    subtitle: "مرحبًا بعودتك. سجّل الدخول للمتابعة إلى حسابك في مدار.",
    email: "البريد الإلكتروني",
    password: "كلمة المرور",
    forgotPassword: "نسيت كلمة المرور؟",
    button: "تسجيل الدخول",
    loading: "جاري تسجيل الدخول...",
    success: "تم تسجيل الدخول! جاري التحويل...",
    serverError: "تعذر الاتصال بالخادم.",
    loginFailed: "فشل تسجيل الدخول.",
    noAccount: "ليس لديك حساب؟",
    signup: "إنشاء حساب",
    required: "هذا الحقل مطلوب.",
    invalidEmail: "يرجى إدخال بريد إلكتروني صحيح.",
  },
};

export default function LoginPage({ lang = "en", onLoginSuccess }) {
  const t = pageText[lang] || pageText.en;
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    email: "",
    password: "",
  });

  const [errors, setErrors] = useState({});
  const [statusMessage, setStatusMessage] = useState("");
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
      newErrors.email = t.required;
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = t.invalidEmail;
    }

    if (!formData.password.trim()) {
      newErrors.password = t.required;
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
      const response = await fetch(`${API_URL}/login`, {
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

      if (!response.ok) {
      if (response.status === 422 && Array.isArray(data.detail)) {
        const emailError = data.detail.find((error) =>
          error.loc?.includes("email")
        );

        if (emailError) {
          setErrors((prev) => ({
            ...prev,
            email: t.invalidEmail,
          }));
          return;
        }

        setStatusMessage(t.loginFailed);
        return;
      }

      setStatusMessage(
        typeof data.detail === "string" ? data.detail : t.loginFailed
      );
      return;
    }

      setStatusMessage(t.success);
      console.log("Login response:", data);

      if (onLoginSuccess) {
        onLoginSuccess();
      }

      setTimeout(() => navigate("/pricing"), 1500);
    } catch (error) {
      console.error(error);
      setStatusMessage(t.serverError);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <div className="login-heading">
          <h1>{t.title}</h1>
          <p>{t.subtitle}</p>
        </div>

        {statusMessage && (
          <p className="form-status-message">{statusMessage}</p>
        )}

        <label>
          {t.email}
          <input
            type="email"
            name="email"
            placeholder={t.email}
            value={formData.email}
            onChange={handleChange}
            dir="ltr"
          />
          {errors.email && <span>{errors.email}</span>}
        </label>

        <label>
          {t.password}
          <div className="password-field">
            <input
              type={showPassword ? "text" : "password"}
              name="password"
              placeholder={t.password}
              value={formData.password}
              onChange={handleChange}
              dir="ltr"
            />
            <button
              type="button"
              onClick={() => setShowPassword((prev) => !prev)}
              aria-label="Toggle password visibility"
            >
              👁
            </button>
          </div>
          {errors.password && <span>{errors.password}</span>}
        </label>

        <div className="login-options">
          <Link to="/forgot-password">{t.forgotPassword}</Link>
        </div>

        <button className="login-submit" type="submit" disabled={isSubmitting}>
          {isSubmitting ? t.loading : t.button}
        </button>

        <p className="login-signup-text">
          {t.noAccount} <Link to="/signup">{t.signup}</Link>
        </p>
      </form>
    </main>
  );
}
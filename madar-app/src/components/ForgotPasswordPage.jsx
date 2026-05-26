import { useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "/api";
console.log("LOGIN API_URL:", API_URL);

const pageText = {
  en: {
    title: "Forgot Password",
    subtitle: "Enter your email and we'll send you a reset link.",
    email: "Email",
    button: "Send Reset Link",
    loading: "Sending...",
    success: "Reset link sent! Check your email.",
    serverError: "Server unavailable. Try again later.",
    required: "This field is required.",
    invalidEmail: "Please enter a valid email address.",
    notFound: "This email is not registered. Please sign up first.",

  },
  ar: {
    title: "نسيت كلمة المرور",
    subtitle: "أدخل بريدك الإلكتروني وسنرسل لك رابط إعادة التعيين.",
    email: "البريد الإلكتروني",
    button: "إرسال رابط الإعادة",
    loading: "جاري الإرسال...",
    success: "تم الإرسال! تحقق من بريدك الإلكتروني.",
    serverError: "الخادم غير متاح. حاول لاحقًا.",
    required: "هذا الحقل مطلوب.",
    invalidEmail: "يرجى إدخال بريد إلكتروني صحيح.",
    notFound: "هذا البريد الإلكتروني غير مسجل. يرجى إنشاء حساب أولاً.",
  },
};

export default function ForgotPasswordPage({ lang = "en" }) {
  const t = pageText[lang] || pageText.en;

  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  const handleChange = (e) => {
    setEmail(e.target.value);
    setError("");
    setStatusMessage("");
  };

  const validateForm = () => {
    if (!email.trim()) {
      setError(t.required);
      return false;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError(t.invalidEmail);
      return false;
    }
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) return;

    setIsSubmitting(true);
    setStatusMessage("");

    try {
      const response = await fetch(`${API_URL}/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });

      const data = await response.json();

      if (!response.ok) {
        if (response.status === 404) {
          setStatusMessage(t.notFound);
          return;
        }
        setStatusMessage(data.detail || "Something went wrong.");
        return;
      }

      setStatusMessage(t.success);
      setSent(true);
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

        {!sent && (
          <>
            <label>
              {t.email}
              <input
                type="email"
                name="email"
                placeholder={t.email}
                value={email}
                onChange={handleChange}
                dir="ltr"
              />
              {error && <span>{error}</span>}
            </label>

            <button className="login-submit" type="submit" disabled={isSubmitting}>
              {isSubmitting ? t.loading : t.button}
            </button>
          </>
        )}
      </form>
    </main>
  );
}

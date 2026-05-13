import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;

const pageText = {
  en: {
    title: "Reset Password",
    subtitle: "Enter your new password below.",
    password: "New Password",
    confirm: "Confirm Password",
    button: "Update Password",
    loading: "Updating...",
    success: "Password updated! Redirecting to login...",
    mismatch: "Passwords do not match.",
    short: "Password must be at least 6 characters.",
    required: "This field is required.",
    invalidLink: "Invalid or expired reset link.",
  },
  ar: {
    title: "إعادة تعيين كلمة المرور",
    subtitle: "أدخل كلمة المرور الجديدة أدناه.",
    password: "كلمة المرور الجديدة",
    confirm: "تأكيد كلمة المرور",
    button: "تحديث كلمة المرور",
    loading: "جاري التحديث...",
    success: "تم تحديث كلمة المرور! جاري التحويل...",
    mismatch: "كلمتا المرور غير متطابقتين.",
    short: "يجب أن تكون كلمة المرور 6 أحرف على الأقل.",
    required: "هذا الحقل مطلوب.",
    invalidLink: "رابط إعادة التعيين غير صالح أو منتهي الصلاحية.",
  },
};

export default function ResetPasswordPage({ lang = "en" }) {
  const t = pageText[lang] || pageText.en;
  const navigate = useNavigate();

  const [accessToken, setAccessToken] = useState(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    // Extract access_token from the URL hash
    const hash = window.location.hash;
    const params = new URLSearchParams(hash.replace("#", ""));
    const token = params.get("access_token");
    const type = params.get("type");

    if (token && type === "recovery") {
      setAccessToken(token);
    } else {
      setError(t.invalidLink);
    }
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!password) return setError(t.required);
    if (password.length < 6) return setError(t.short);
    if (password !== confirm) return setError(t.mismatch);

    setIsSubmitting(true);
    setError("");

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/password_rest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ access_token: accessToken, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.detail || "Something went wrong.");
        return;
      }

      setStatusMessage(t.success);
      setTimeout(() => navigate("/login"), 2000);
    } catch (err) {
      console.error(err);
      setError("Server unavailable. Try again later.");
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

        {statusMessage && <p className="form-status-message">{statusMessage}</p>}
        {error && <p className="form-status-message">{error}</p>}

        {accessToken && !statusMessage && (
          <>
            <label>
              {t.password}
              <div className="password-field">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setError(""); }}
                  dir="ltr"
                />
                <button type="button" onClick={() => setShowPassword((p) => !p)}>👁</button>
              </div>
            </label>

            <label>
              {t.confirm}
              <input
                type={showPassword ? "text" : "password"}
                value={confirm}
                onChange={(e) => { setConfirm(e.target.value); setError(""); }}
                dir="ltr"
              />
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
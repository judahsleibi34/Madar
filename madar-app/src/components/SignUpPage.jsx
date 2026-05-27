import { useState } from "react";
import { useNavigate } from "react-router-dom";

const API_URL = import.meta.env.VITE_API_URL || "/api";
console.log("LOGIN API_URL:", API_URL);

const pageText = {
  en: {
    title: "Register",
    firstName: "First Name",
    lastName: "Last Name",
    email: "Email",
    password: "Password",
    confirmPassword: "Confirm Password",
    button: "Create Account",
    loading: "Creating Account...",
    success: "Account created! Redirecting to login...",
    serverError: "Server error",
    required: "This field is required.",
    invalidEmail: "Please enter a valid email address.",
    alreadyRegistered: "This email is already registered. Please log in.", // ✅
    passwordInvalid:
      "Password must be at least 8 characters and include uppercase, lowercase, number, and special character.",
    passwordMismatch: "Passwords do not match.",
  },
  ar: {
    title: "إنشاء حساب",
    firstName: "الاسم الأول",
    lastName: "اسم العائلة",
    email: "البريد الإلكتروني",
    password: "كلمة المرور",
    confirmPassword: "تأكيد كلمة المرور",
    button: "إنشاء الحساب",
    loading: "جاري إنشاء الحساب...",
    success: "تم إنشاء الحساب! جاري التحويل إلى تسجيل الدخول...",
    serverError: "تعذر الاتصال بالخادم.",
    required: "هذا الحقل مطلوب.",
    invalidEmail: "يرجى إدخال بريد إلكتروني صحيح.",
    alreadyRegistered: "هذا البريد مسجل مسبقاً. يرجى تسجيل الدخول.", // ✅
    passwordInvalid:
      "يجب أن تكون كلمة المرور 8 أحرف على الأقل وتحتوي على حرف كبير وحرف صغير ورقم ورمز خاص.",
    passwordMismatch: "كلمتا المرور غير متطابقتين.",
  },
};

export default function SignUpPage({ lang = "en", loginPath = "/login", onSignupSuccess }) {
  const t = pageText[lang] || pageText.en;
  const navigate = useNavigate(); // ✅ THIS WAS MISSING

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

    if (!formData.firstName.trim()) newErrors.firstName = t.required;
    if (!formData.lastName.trim()) newErrors.lastName = t.required;
    if (!formData.email.trim()) newErrors.email = t.required;
    if (!formData.password.trim()) newErrors.password = t.required;
    if (!formData.confirmPassword.trim()) newErrors.confirmPassword = t.required;

    if (formData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = t.invalidEmail;
    }

    const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{8,}$/;
    if (formData.password && !passwordRegex.test(formData.password)) {
      newErrors.password = t.passwordInvalid;
    }

    if (
      formData.password &&
      formData.confirmPassword &&
      formData.password !== formData.confirmPassword
    ) {
      newErrors.confirmPassword = t.passwordMismatch;
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
        newErrors.email = t.invalidEmail;
      }

      if (field === "first_name") {
        newErrors.firstName = t.required;
      }

      if (field === "last_name") {
        newErrors.lastName = t.required;
      }

      if (field === "password") {
        newErrors.password = error.msg || t.required;
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
      setStatusMessage(t.alreadyRegistered);
      return;
    }

    setStatusMessage(
      typeof data.detail === "string" ? data.detail : "Signup failed."
    );
    return;
  }

      setStatusMessage(t.success);
      setTimeout(() => {
        if (onSignupSuccess) {
          onSignupSuccess();
          return;
        }

        navigate(loginPath);
      }, 1500);
    } catch (error) {
      console.error(error);
      setStatusMessage(t.serverError);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="register-page">
      <form className="register-card" onSubmit={handleSubmit}>
        <h1>{t.title}</h1>

        {statusMessage && (
          <p className="form-status-message">{statusMessage}</p>
        )}

        <div className="register-row">
          <label>
            {t.firstName}
            <input
              type="text"
              name="firstName"
              placeholder={t.firstName}
              value={formData.firstName}
              onChange={handleChange}
            />
            {errors.firstName && <span>{errors.firstName}</span>}
          </label>

          <label>
            {t.lastName}
            <input
              type="text"
              name="lastName"
              placeholder={t.lastName}
              value={formData.lastName}
              onChange={handleChange}
            />
            {errors.lastName && <span>{errors.lastName}</span>}
          </label>
        </div>

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

        <label>
          {t.confirmPassword}
          <div className="password-field">
            <input
              type={showConfirmPassword ? "text" : "password"}
              name="confirmPassword"
              placeholder={t.confirmPassword}
              value={formData.confirmPassword}
              onChange={handleChange}
              dir="ltr"
            />
            <button
              type="button"
              onClick={() => setShowConfirmPassword((prev) => !prev)}
              aria-label="Toggle confirm password visibility"
            >
              👁
            </button>
          </div>
          {errors.confirmPassword && <span>{errors.confirmPassword}</span>}
        </label>

        <button
          className="register-submit"
          type="submit"
          disabled={isSubmitting}
        >
          {isSubmitting ? t.loading : t.button}
        </button>
      </form>
    </main>
  );
}

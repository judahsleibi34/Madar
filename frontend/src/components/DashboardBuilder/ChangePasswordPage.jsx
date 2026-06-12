import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Eye, EyeOff, KeyRound } from "lucide-react";

import { apiFetch } from "../../utils/apiClient";

const API_URL = import.meta.env.VITE_API_URL || "/api";

const copy = {
  en: {
    eyebrow: "Account security",
    title: "Change password",
    subtitle:
      "Confirm your current password, then choose and confirm your new password.",
    currentPassword: "Current password",
    newPassword: "New password",
    confirmNewPassword: "Confirm new password",
    cancel: "Cancel",
    updatePassword: "Update password",
    updatingPassword: "Updating...",
    passwordMismatch: "New passwords do not match.",
    passwordTooShort: "Password must be at least 8 characters.",
    passwordFieldsRequired: "Please fill in all password fields.",
    passwordUpdated: "Password updated successfully.",
    passwordUpdateError: "Could not update password.",
    backToSettings: "Back to settings",
    showPassword: "Show password",
    hidePassword: "Hide password",
  },
  ar: {
    eyebrow: "أمان الحساب",
    title: "تغيير كلمة المرور",
    subtitle:
      "أكّد كلمة المرور الحالية، ثم أدخل كلمة المرور الجديدة وأكّدها.",
    currentPassword: "كلمة المرور الحالية",
    newPassword: "كلمة المرور الجديدة",
    confirmNewPassword: "تأكيد كلمة المرور الجديدة",
    cancel: "إلغاء",
    updatePassword: "تحديث كلمة المرور",
    updatingPassword: "جارٍ التحديث...",
    passwordMismatch: "كلمتا المرور الجديدتان غير متطابقتين.",
    passwordTooShort: "يجب أن تكون كلمة المرور 8 أحرف على الأقل.",
    passwordFieldsRequired: "يرجى تعبئة جميع حقول كلمة المرور.",
    passwordUpdated: "تم تحديث كلمة المرور بنجاح.",
    passwordUpdateError: "تعذر تحديث كلمة المرور.",
    backToSettings: "العودة إلى الإعدادات",
    showPassword: "إظهار كلمة المرور",
    hidePassword: "إخفاء كلمة المرور",
  },
};

const getApiErrorMessage = (detail, fallback) => {
  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    return detail
      .map((error) => {
        const field = Array.isArray(error.loc) ? error.loc.at(-1) : "";
        return [field, error.msg].filter(Boolean).join(": ");
      })
      .filter(Boolean)
      .join(" ");
  }

  return fallback;
};

export default function ChangePasswordPage({ lang = "en" }) {
  const navigate = useNavigate();
  const isArabic = lang === "ar";
  const t = copy[isArabic ? "ar" : "en"];

  const [form, setForm] = useState({
    currentPassword: "",
    newPassword: "",
    confirmNewPassword: "",
  });

  const [visibleFields, setVisibleFields] = useState({
    currentPassword: false,
    newPassword: false,
    confirmNewPassword: false,
  });

  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const updateField = (field, value) => {
    setForm((prev) => ({
      ...prev,
      [field]: value,
    }));

    setStatus("");
    setError("");
  };

  const togglePasswordVisibility = (field) => {
    setVisibleFields((prev) => ({
      ...prev,
      [field]: !prev[field],
    }));
  };

  const renderPasswordField = ({
    field,
    label,
    autoComplete,
  }) => {
    const isVisible = visibleFields[field];

    return (
      <label>
        {label}

        <div className="change-password-input-wrap">
          <input
            type={isVisible ? "text" : "password"}
            value={form[field]}
            onChange={(event) => updateField(field, event.target.value)}
            autoComplete={autoComplete}
          />

          <button
            type="button"
            className="change-password-eye"
            onClick={() => togglePasswordVisibility(field)}
            aria-label={isVisible ? t.hidePassword : t.showPassword}
            title={isVisible ? t.hidePassword : t.showPassword}
          >
            {isVisible ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        </div>
      </label>
    );
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    const currentPassword = form.currentPassword.trim();
    const newPassword = form.newPassword.trim();
    const confirmNewPassword = form.confirmNewPassword.trim();

    if (!currentPassword || !newPassword || !confirmNewPassword) {
      setError(t.passwordFieldsRequired);
      return;
    }

    if (newPassword.length < 8) {
      setError(t.passwordTooShort);
      return;
    }

    if (newPassword !== confirmNewPassword) {
      setError(t.passwordMismatch);
      return;
    }

    setIsSubmitting(true);
    setStatus("");
    setError("");

    try {
      const response = await apiFetch(`${API_URL}/auth/password/change`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(getApiErrorMessage(data.detail, t.passwordUpdateError));
      }

      setForm({
        currentPassword: "",
        newPassword: "",
        confirmNewPassword: "",
      });

      setVisibleFields({
        currentPassword: false,
        newPassword: false,
        confirmNewPassword: false,
      });

      setStatus(data.message || t.passwordUpdated);
    } catch (submitError) {
      setError(submitError.message || t.passwordUpdateError);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="change-password-page" dir={isArabic ? "rtl" : "ltr"}>
      <div className="change-password-card">
        <button
          className="change-password-back"
          type="button"
          onClick={() => navigate("/settings")}
        >
          <ArrowLeft size={18} />
          {t.backToSettings}
        </button>

        <div className="change-password-heading">
          <span>{t.eyebrow}</span>
          <h1>{t.title}</h1>
          <p>{t.subtitle}</p>
        </div>

        {status && <div className="change-password-status">{status}</div>}
        {error && <div className="change-password-error">{error}</div>}

        <form className="change-password-form" onSubmit={handleSubmit}>
          {renderPasswordField({
            field: "currentPassword",
            label: t.currentPassword,
            autoComplete: "current-password",
          })}

          {renderPasswordField({
            field: "newPassword",
            label: t.newPassword,
            autoComplete: "new-password",
          })}

          {renderPasswordField({
            field: "confirmNewPassword",
            label: t.confirmNewPassword,
            autoComplete: "new-password",
          })}

          <div className="change-password-actions">
            <button
              className="change-password-cancel"
              type="button"
              onClick={() => navigate("/settings")}
              disabled={isSubmitting}
            >
              {t.cancel}
            </button>

            <button
              className="change-password-submit"
              type="submit"
              disabled={isSubmitting}
            >
              <KeyRound size={18} />
              {isSubmitting ? t.updatingPassword : t.updatePassword}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}

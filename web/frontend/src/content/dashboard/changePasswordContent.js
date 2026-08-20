export const changePasswordContent = {
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

export const getChangePasswordContent = (lang = "en") =>
  changePasswordContent[lang === "ar" ? "ar" : "en"];

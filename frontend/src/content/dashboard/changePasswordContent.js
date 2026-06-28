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
    eyebrow: "ط£ظ…ط§ظ† ط§ظ„ط­ط³ط§ط¨",
    title: "طھط؛ظٹظٹط± ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط±",
    subtitle:
      "ط£ظƒظ‘ط¯ ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط± ط§ظ„ط­ط§ظ„ظٹط©طŒ ط«ظ… ط£ط¯ط®ظ„ ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط± ط§ظ„ط¬ط¯ظٹط¯ط© ظˆط£ظƒظ‘ط¯ظ‡ط§.",
    currentPassword: "ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط± ط§ظ„ط­ط§ظ„ظٹط©",
    newPassword: "ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط± ط§ظ„ط¬ط¯ظٹط¯ط©",
    confirmNewPassword: "طھط£ظƒظٹط¯ ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط± ط§ظ„ط¬ط¯ظٹط¯ط©",
    cancel: "ط¥ظ„ط؛ط§ط،",
    updatePassword: "طھط­ط¯ظٹط« ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط±",
    updatingPassword: "ط¬ط§ط±ظچ ط§ظ„طھط­ط¯ظٹط«...",
    passwordMismatch: "ظƒظ„ظ…طھط§ ط§ظ„ظ…ط±ظˆط± ط§ظ„ط¬ط¯ظٹط¯طھط§ظ† ط؛ظٹط± ظ…طھط·ط§ط¨ظ‚طھظٹظ†.",
    passwordTooShort: "ظٹط¬ط¨ ط£ظ† طھظƒظˆظ† ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط± 8 ط£ط­ط±ظپ ط¹ظ„ظ‰ ط§ظ„ط£ظ‚ظ„.",
    passwordFieldsRequired: "ظٹط±ط¬ظ‰ طھط¹ط¨ط¦ط© ط¬ظ…ظٹط¹ ط­ظ‚ظˆظ„ ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط±.",
    passwordUpdated: "طھظ… طھط­ط¯ظٹط« ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط± ط¨ظ†ط¬ط§ط­.",
    passwordUpdateError: "طھط¹ط°ط± طھط­ط¯ظٹط« ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط±.",
    backToSettings: "ط§ظ„ط¹ظˆط¯ط© ط¥ظ„ظ‰ ط§ظ„ط¥ط¹ط¯ط§ط¯ط§طھ",
    showPassword: "ط¥ط¸ظ‡ط§ط± ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط±",
    hidePassword: "ط¥ط®ظپط§ط، ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط±",
  },
};

export const getChangePasswordContent = (lang = "en") =>
  changePasswordContent[lang === "ar" ? "ar" : "en"];

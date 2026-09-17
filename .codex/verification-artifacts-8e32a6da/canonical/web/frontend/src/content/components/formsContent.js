export const subscriptionModalContent = {
  en: {
    successTitle: "Subscription saved",
    successMessage: "Your subscription was saved successfully.",
    errorTitle: "Subscription failed",
    errorMessage: "Could not save your subscription. Please try again.",
    confirm: "Continue",
  },
  ar: {
    successTitle: "تم حفظ الاشتراك",
    successMessage: "تم حفظ اشتراكك بنجاح.",
    errorTitle: "فشل الاشتراك",
    errorMessage: "تعذر حفظ اشتراكك. يرجى المحاولة مرة أخرى.",
    confirm: "متابعة",
  },
};

export const getSubscriptionModalContent = (lang = "en") =>
  subscriptionModalContent[lang === "ar" ? "ar" : "en"];

export const subdomainModalContent = {
  en: {
    defaultWebsiteName: "my-website",
    defaultDomain: "madarportal.com",
    logoFallback: "M",
    errors: {
      required: "Add a website name first.",
      minLength: "Use at least 3 characters.",
      reserved: "This name is reserved. Try another one.",
    },
    kicker: "One quick step",
    title: "Create your website link",
    description: "Pick a short name people can use to open your website.",
    websiteNameLabel: "Website name",
    websiteNamePlaceholder: "my-business",
    previewLabel: "Your website link",
    note: "After saving, your Login button will open this website login page.",
    action: "Create website link",
  },
  ar: {
    defaultWebsiteName: "my-website",
    defaultDomain: "madarportal.com",
    logoFallback: "م",
    errors: {
      required: "أضف اسم الموقع أولا.",
      minLength: "استخدم 3 أحرف على الأقل.",
      reserved: "هذا الاسم محجوز. جرّب اسما آخر.",
    },
    kicker: "خطوة سريعة",
    title: "أنشئ رابط موقعك",
    description: "اختر اسما قصيرا يمكن للناس استخدامه لفتح موقعك.",
    websiteNameLabel: "اسم الموقع",
    websiteNamePlaceholder: "my-business",
    previewLabel: "رابط موقعك",
    note: "بعد الحفظ، سيفتح زر تسجيل الدخول صفحة الدخول الخاصة بهذا الموقع.",
    action: "إنشاء رابط الموقع",
  },
};

export const getSubdomainModalContent = (lang = "en") =>
  subdomainModalContent[lang] || subdomainModalContent.en;

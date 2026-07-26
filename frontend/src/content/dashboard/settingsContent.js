export const settingsContent = {
  en: {
    eyebrow: "Workspace settings",
    title: "Profile and website settings",
    subtitle:
      "Keep your personal details, brand, and public website information up to date.",

    profileTitle: "Your profile",
    profileDescription:
      "This information helps personalize your workspace and customer-facing pages.",
    uploadProfilePhoto: "Upload photo",
    firstName: "First name",
    lastName: "Last name",
    email: "Email",
    emailChangeUnavailable:
      "Your verified login email cannot be edited here. A secure email-change flow is coming soon.",
    phoneNumber: "Phone number",
    saveProfile: "Save profile",
    changePassword: "Change password",
    saving: "Saving...",

    websiteTitle: "Website details",
    websiteDescription:
      "Set the name, contact details, and logo visitors see on your website.",
    websiteLogoAlt: "Website logo",
    uploadLogo: "Upload logo",
    uploadingLogo: "Uploading...",
    logoUploadUnavailable:
      "Image uploads are not available yet. Use a secure HTTPS image URL for now.",
    subdomainName: "Subdomain name",
    logoUrl: "Logo file",
    brandName: "Brand name",
    footerName: "Footer name",
    contactEmail: "Contact email",
    contactPhone: "Contact phone",
    websiteDescriptionLabel: "Website description",
    saveWebsite: "Save website details",

    accountSaved: "Account settings saved.",
    avatarUploaded: "Profile photo updated.",
    logoUploaded: "Logo uploaded.",
    websiteSaved: "Website settings saved.",
    accountError: "Could not update account settings.",
    avatarUploadError: "Could not upload profile photo.",
    logoUploadError: "Could not upload logo.",
    invalidAvatarType: "Please upload a PNG, JPG, or WebP image.",
    invalidLogoType: "Please upload a PNG, JPG, or WebP image.",
    avatarTooLarge: "Profile photo must be 5MB or smaller.",
    logoTooLarge: "Logo image must be 5MB or smaller.",
    invalidLogoUrl:
      "Use an HTTPS image URL or managed internal path. Data, SVG, JavaScript, and HTTP URLs are not allowed.",
    sessionExpired: "Your session expired. Please log in again.",

    userAlt: "User",
    userFallback: "U",

    firstNameRequired: "First name is required.",
    lastNameRequired: "Last name is required.",
    emailRequired: "Email is required.",
    emailInvalid: "Please enter a valid email address.",
    subdomainRequired: "Subdomain name is required.",
    brandRequired: "Brand name is required.",
    contactEmailInvalid: "Please enter a valid contact email.",
    fixErrors: "Please fix the highlighted fields.",
    closeNotification: "Close notification",
  },

  ar: {
    eyebrow: "إعدادات مساحة العمل",
    title: "إعدادات الملف الشخصي والموقع",
    subtitle: "حدّث بياناتك الشخصية وهوية العلامة ومعلومات الموقع العامة.",

    profileTitle: "ملفك الشخصي",
    profileDescription:
      "تساعد هذه المعلومات في تخصيص مساحة عملك وصفحاتك أمام العملاء.",
    uploadProfilePhoto: "رفع صورة",
    firstName: "الاسم الأول",
    lastName: "اسم العائلة",
    email: "البريد الإلكتروني",
    emailChangeUnavailable:
      "لا يمكن تعديل بريد تسجيل الدخول الموثق من هنا. ستتوفر آلية آمنة لتغيير البريد قريباً.",
    phoneNumber: "رقم الهاتف",
    saveProfile: "حفظ الملف الشخصي",
    changePassword: "تغيير كلمة المرور",
    saving: "جارٍ الحفظ...",

    websiteTitle: "تفاصيل الموقع",
    websiteDescription:
      "حدد الاسم وبيانات التواصل والشعار الذي يراه زوار موقعك.",
    websiteLogoAlt: "شعار الموقع",
    uploadLogo: "رفع الملفات قريباً",
    uploadingLogo: "جارٍ الرفع...",
    logoUploadUnavailable:
      "رفع الصور غير متاح حالياً. استخدم رابط صورة HTTPS آمناً في الوقت الحالي.",
    subdomainName: "اسم النطاق الفرعي",
    logoUrl: "ملف الشعار",
    brandName: "اسم العلامة",
    footerName: "اسم التذييل",
    contactEmail: "بريد التواصل",
    contactPhone: "هاتف التواصل",
    websiteDescriptionLabel: "وصف الموقع",
    saveWebsite: "حفظ تفاصيل الموقع",

    accountSaved: "تم حفظ إعدادات الملف الشخصي.",
    avatarUploaded: "تم تحديث صورة الملف الشخصي.",
    logoUploaded: "تم رفع الشعار.",
    websiteSaved: "تم حفظ تفاصيل الموقع.",
    accountError: "تعذر حفظ إعدادات الملف الشخصي.",
    avatarUploadError: "تعذر رفع صورة الملف الشخصي.",
    logoUploadError: "تعذر رفع الشعار.",
    invalidAvatarType: "يرجى رفع صورة بصيغة PNG أو JPG أو WebP.",
    invalidLogoType: "يرجى رفع صورة بصيغة PNG أو JPG أو WebP.",
    avatarTooLarge: "يجب ألا يتجاوز حجم صورة الملف الشخصي 5MB.",
    logoTooLarge: "يجب ألا يتجاوز حجم الشعار 5MB.",
    invalidLogoUrl:
      "استخدم رابط صورة HTTPS أو مساراً داخلياً مُداراً. روابط data و SVG و JavaScript و HTTP غير مسموحة.",
    sessionExpired: "انتهت جلستك. يرجى تسجيل الدخول مرة أخرى.",

    userAlt: "المستخدم",
    userFallback: "م",

    firstNameRequired: "الاسم الأول مطلوب.",
    lastNameRequired: "اسم العائلة مطلوب.",
    emailRequired: "البريد الإلكتروني مطلوب.",
    emailInvalid: "يرجى إدخال بريد إلكتروني صحيح.",
    subdomainRequired: "اسم النطاق الفرعي مطلوب.",
    brandRequired: "اسم العلامة مطلوب.",
    contactEmailInvalid: "يرجى إدخال بريد تواصل صحيح.",
    fixErrors: "يرجى تصحيح الحقول المحددة.",
    closeNotification: "إغلاق الإشعار",
  },
};

export const getSettingsContent = (lang = "en") =>
  settingsContent[lang === "ar" ? "ar" : "en"];

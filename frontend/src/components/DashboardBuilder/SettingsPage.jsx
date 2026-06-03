import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { ImagePlus, KeyRound, Save, X } from "lucide-react";
import SmartLink from "../SmartLink";
import {
  STORAGE_KEY,
  defaultSiteChrome,
} from "../PageBuilder/PageBuilder.constants";
import { createInitialProject } from "../PageBuilder/PageBuilder.starters";
import {
  getConfiguredProjectSubdomain,
  sanitizeSubdomain,
} from "../PageBuilder/PageBuilder.routing";
import { resolveMediaUrl } from "../../utils/media";

const API_URL = import.meta.env.VITE_API_URL || "/api";
const AVATAR_MAX_BYTES = 5 * 1024 * 1024;
const AVATAR_MIME_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);

const readBuilderProject = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : createInitialProject();
  } catch {
    return createInitialProject();
  }
};

const readApiResponse = async (response) => {
  const text = await response.text();

  if (!text) return {};

  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
};

const getInitialAccountForm = (user) => ({
  first_name: user?.first_name || "",
  last_name: user?.last_name || "",
  email: user?.email || "",
  phone: user?.phone || "",
  avatar: user?.avatar || "",
});

const getAvatarLetter = (accountForm, fallback) => {
  return (accountForm.first_name || accountForm.email || fallback)
    .trim()
    .slice(0, 1)
    .toUpperCase();
};

const getApiErrorMessage = (detail, fallback) => {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail)) {
    const message = detail
      .map((error) => {
        const field = Array.isArray(error.loc) ? error.loc.at(-1) : "";
        return [field, error.msg].filter(Boolean).join(": ");
      })
      .filter(Boolean)
      .join(" ");

    return message || fallback;
  }

  if (detail && typeof detail === "object") {
    return detail.message || detail.error || fallback;
  }

  return fallback;
};

const buildProfilePayload = (form) => {
  const payload = {
    first_name: form.first_name.trim(),
    last_name: form.last_name.trim(),
    phone: form.phone.trim(),
    avatar: form.avatar.trim(),
  };

  const email = form.email.trim();
  if (email) payload.email = email;

  return payload;
};

const isValidEmail = (value) => {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || "").trim());
};

const isDirectImageUrl = (url) => {
  if (!url || typeof url !== "string") return false;

  const cleanUrl = url.trim();

  if (cleanUrl.startsWith("data:image/")) return true;
  if (cleanUrl.startsWith("/")) return true;
  if (cleanUrl.startsWith("http://")) return true;
  if (cleanUrl.startsWith("https://")) return true;

  return /\.(png|jpe?g|webp|gif|svg)(\?.*)?$/i.test(cleanUrl);
};

function SettingsNotification({ notification, isArabic, label, onClose }) {
  if (!notification) return null;

  return createPortal(
    <div
      className={`settings-toast settings-toast-${notification.type} ${
        isArabic ? "settings-toast-rtl" : ""
      }`}
      role="alert"
      aria-live="polite"
    >
      <div className="settings-toast-content">
        <span>{notification.message}</span>
      </div>

      <button type="button" aria-label={label} onClick={onClose}>
        <X size={16} />
      </button>
    </div>,
    document.body
  );
}

const settingsCopy = {
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
    phoneNumber: "Phone number",
    saveProfile: "Save profile",
    changePassword: "Change password",
    saving: "Saving...",

    websiteTitle: "Website details",
    websiteDescription:
      "Set the name, contact details, and logo visitors see on your website.",
    websiteLogoAlt: "Website logo",
    uploadLogo: "Upload logo",
    subdomainName: "Subdomain name",
    logoUrl: "Logo URL",
    brandName: "Brand name",
    footerName: "Footer name",
    contactEmail: "Contact email",
    contactPhone: "Contact phone",
    websiteDescriptionLabel: "Website description",
    saveWebsite: "Save website details",

    accountSaved: "Account settings saved.",
    avatarUploaded: "Profile photo updated.",
    websiteSaved: "Website settings saved.",
    accountError: "Could not update account settings.",
    avatarUploadError: "Could not upload profile photo.",
    invalidAvatarType: "Please upload a PNG, JPG, or WebP image.",
    avatarTooLarge: "Profile photo must be 5MB or smaller.",
    invalidLogoUrl:
      "Please use a direct image URL ending in .png, .jpg, .webp, .gif, or .svg.",
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
    phoneNumber: "رقم الهاتف",
    saveProfile: "حفظ الملف الشخصي",
    changePassword: "تغيير كلمة المرور",
    saving: "جارٍ الحفظ...",

    websiteTitle: "تفاصيل الموقع",
    websiteDescription:
      "حدد الاسم وبيانات التواصل والشعار الذي يراه زوار موقعك.",
    websiteLogoAlt: "شعار الموقع",
    uploadLogo: "رفع الشعار",
    subdomainName: "اسم النطاق الفرعي",
    logoUrl: "رابط الشعار",
    brandName: "اسم العلامة",
    footerName: "اسم التذييل",
    contactEmail: "بريد التواصل",
    contactPhone: "هاتف التواصل",
    websiteDescriptionLabel: "وصف الموقع",
    saveWebsite: "حفظ تفاصيل الموقع",

    accountSaved: "تم حفظ إعدادات الملف الشخصي.",
    avatarUploaded: "تم تحديث صورة الملف الشخصي.",
    websiteSaved: "تم حفظ تفاصيل الموقع.",
    accountError: "تعذر حفظ إعدادات الملف الشخصي.",
    avatarUploadError: "تعذر رفع صورة الملف الشخصي.",
    invalidAvatarType: "يرجى رفع صورة بصيغة PNG أو JPG أو WebP.",
    avatarTooLarge: "يجب ألا يتجاوز حجم صورة الملف الشخصي 5MB.",
    invalidLogoUrl:
      "يرجى استخدام رابط صورة مباشر ينتهي بـ .png أو .jpg أو .webp أو .gif أو .svg.",
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

export default function SettingsPage({ lang = "en", user, onUserUpdated }) {
  const [accountForm, setAccountForm] = useState(() =>
    getInitialAccountForm(user)
  );

  const [project, setProject] = useState(readBuilderProject);
  const [fieldErrors, setFieldErrors] = useState({});
  const [notification, setNotification] = useState(null);

  const [isSavingAccount, setIsSavingAccount] = useState(false);
  const [isUploadingAvatar, setIsUploadingAvatar] = useState(false);
  const [isSavingSite, setIsSavingSite] = useState(false);
  const [avatarLoadFailed, setAvatarLoadFailed] = useState(false);

  const isArabic = lang === "ar";
  const t = settingsCopy[isArabic ? "ar" : "en"];

  const avatarUrl = resolveMediaUrl(accountForm.avatar);
  const shouldShowAvatarImage = Boolean(avatarUrl) && !avatarLoadFailed;

  const siteChrome = {
    ...defaultSiteChrome,
    ...(project.siteChrome || {}),
  };

  const siteForm = useMemo(
    () => ({
      subdomain: getConfiguredProjectSubdomain(project),
      brand: siteChrome.brand || "",
      footerStoreName: siteChrome.footerStoreName || "",
      logoUrl: siteChrome.logoUrl || "",
      contactEmail: siteChrome.contactEmail || "",
      phone: siteChrome.phone || "",
      description: siteChrome.description || "",
    }),
    [
      project,
      siteChrome.brand,
      siteChrome.contactEmail,
      siteChrome.description,
      siteChrome.footerStoreName,
      siteChrome.logoUrl,
      siteChrome.phone,
    ]
  );

  const canShowLogoImage = isDirectImageUrl(siteForm.logoUrl);

  const showNotification = (type, message) => {
    setNotification({ type, message });

    window.clearTimeout(window.__settingsNotificationTimer);
    window.__settingsNotificationTimer = window.setTimeout(() => {
      setNotification(null);
    }, 3500);
  };

  const clearNotification = () => {
    setNotification(null);
    window.clearTimeout(window.__settingsNotificationTimer);
  };

  const updateAccountField = (field, value) => {
    setAccountForm((prev) => ({ ...prev, [field]: value }));
    setFieldErrors((prev) => ({ ...prev, [field]: "" }));

    if (field === "avatar") {
      setAvatarLoadFailed(false);
    }
  };

  const updateSiteField = (field, value) => {
    setProject((prev) => {
      const nextSiteChrome = {
        ...defaultSiteChrome,
        ...(prev.siteChrome || {}),
      };

      if (field === "subdomain") {
        return {
          ...prev,
          publish: {
            ...(prev.publish || {}),
            subdomain: sanitizeSubdomain(value),
          },
        };
      }

      return {
        ...prev,
        siteChrome: {
          ...nextSiteChrome,
          [field]: value,
        },
      };
    });

    setFieldErrors((prev) => ({ ...prev, [field]: "" }));
  };

  const validateAccountForm = () => {
    const errors = {};

    if (!accountForm.first_name.trim()) {
      errors.first_name = t.firstNameRequired;
    }

    if (!accountForm.last_name.trim()) {
      errors.last_name = t.lastNameRequired;
    }

    if (!accountForm.email.trim()) {
      errors.email = t.emailRequired;
    } else if (!isValidEmail(accountForm.email)) {
      errors.email = t.emailInvalid;
    }

    setFieldErrors((prev) => ({
      ...prev,
      first_name: errors.first_name || "",
      last_name: errors.last_name || "",
      email: errors.email || "",
    }));

    return errors;
  };

  const validateWebsiteForm = () => {
    const errors = {};

    if (!siteForm.subdomain.trim()) {
      errors.subdomain = t.subdomainRequired;
    }

    if (!siteForm.brand.trim()) {
      errors.brand = t.brandRequired;
    }

    if (siteForm.contactEmail.trim() && !isValidEmail(siteForm.contactEmail)) {
      errors.contactEmail = t.contactEmailInvalid;
    }

    if (siteForm.logoUrl.trim() && !isDirectImageUrl(siteForm.logoUrl)) {
      errors.logoUrl = t.invalidLogoUrl;
    }

    setFieldErrors((prev) => ({
      ...prev,
      subdomain: errors.subdomain || "",
      brand: errors.brand || "",
      contactEmail: errors.contactEmail || "",
      logoUrl: errors.logoUrl || "",
    }));

    return errors;
  };

  useEffect(() => {
    setAccountForm(getInitialAccountForm(user));
    setAvatarLoadFailed(false);
  }, [user]);

  useEffect(() => {
    setAvatarLoadFailed(false);
  }, [accountForm.avatar]);

  useEffect(() => {
    return () => {
      window.clearTimeout(window.__settingsNotificationTimer);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadAccount = async () => {
      try {
        const response = await fetch(`${API_URL}/user/info`, {
          method: "POST",
          credentials: "include",
        });

        const data = await readApiResponse(response);

        if (!response.ok) {
          if (!cancelled && response.status === 401) {
            showNotification("error", t.sessionExpired);
          } else if (!cancelled) {
            showNotification(
              "error",
              getApiErrorMessage(data.detail, t.accountError)
            );
          }

          return;
        }

        if (!cancelled && data.user) {
          setAccountForm(getInitialAccountForm(data.user));
          setAvatarLoadFailed(false);
          onUserUpdated?.(data.user);
        }
      } catch {
        if (!cancelled) {
          showNotification("error", t.accountError);
        }
      }
    };

    loadAccount();

    return () => {
      cancelled = true;
    };
  }, [onUserUpdated, t.accountError, t.sessionExpired]);

  useEffect(() => {
    let cancelled = false;

    const loadWebsiteSettings = async () => {
      try {
        const response = await fetch(`${API_URL}/website/settings`, {
          method: "GET",
          credentials: "include",
          cache: "no-store",
        });

        const data = await readApiResponse(response);

        if (!response.ok) {
          return;
        }

        const website = data.website || {};

        if (!cancelled) {
          setProject((prev) => ({
            ...prev,
            publish: {
              ...(prev.publish || {}),
              subdomain: sanitizeSubdomain(website.subdomain || ""),
            },
            siteChrome: {
              ...defaultSiteChrome,
              ...(prev.siteChrome || {}),
              brand: website.brand || prev.siteChrome?.brand || "",
              footerStoreName:
                website.footer_store_name || prev.siteChrome?.footerStoreName || "",
              logoUrl: website.logo_url || prev.siteChrome?.logoUrl || "",
              contactEmail: website.contact_email || prev.siteChrome?.contactEmail || "",
              phone: website.phone || prev.siteChrome?.phone || "",
              description: website.description || prev.siteChrome?.description || "",
            },
          }));
        }
      } catch {
        // Keep local settings visible if the backend settings request fails.
      }
    };

    loadWebsiteSettings();

    return () => {
      cancelled = true;
    };
  }, []);

  const readImageFile = (file, callback) => {
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => callback(String(reader.result || ""));
    reader.readAsDataURL(file);
  };

  const uploadAvatar = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";

    if (!file) return;

    if (!AVATAR_MIME_TYPES.has(file.type)) {
      showNotification("error", t.invalidAvatarType);
      return;
    }

    if (file.size > AVATAR_MAX_BYTES) {
      showNotification("error", t.avatarTooLarge);
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setIsUploadingAvatar(true);
    setAvatarLoadFailed(false);

    try {
      const response = await fetch(`${API_URL}/user/avatar`, {
        method: "POST",
        credentials: "include",
        body: formData,
      });

      const data = await readApiResponse(response);

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error(t.sessionExpired);
        }

        throw new Error(getApiErrorMessage(data.detail, t.avatarUploadError));
      }

      const nextUser = data.user || {};
      const nextAvatar = nextUser.avatar || data.avatar || "";

      if (nextAvatar) {
        setAccountForm((prev) => ({ ...prev, avatar: nextAvatar }));
        setAvatarLoadFailed(false);
      }

      onUserUpdated?.(nextUser);
      showNotification("success", data.message || t.avatarUploaded);
    } catch (error) {
      showNotification("error", error.message || t.avatarUploadError);
    } finally {
      setIsUploadingAvatar(false);
    }
  };

  const saveAccount = async (event) => {
    event.preventDefault();

    const errors = validateAccountForm();

    if (Object.keys(errors).length > 0) {
      showNotification("error", t.fixErrors);
      return;
    }

    setIsSavingAccount(true);

    try {
      const response = await fetch(`${API_URL}/user/profile`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildProfilePayload(accountForm)),
      });

      const data = await readApiResponse(response);

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error(t.sessionExpired);
        }

        throw new Error(getApiErrorMessage(data.detail, t.accountError));
      }

      if (data.user) {
        setAccountForm(getInitialAccountForm(data.user));
        setAvatarLoadFailed(false);
        onUserUpdated?.(data.user);
      }

      showNotification("success", data.message || t.accountSaved);
    } catch (error) {
      showNotification("error", error.message || t.accountError);
    } finally {
      setIsSavingAccount(false);
    }
  };

  const saveSiteSettings = async (event) => {
    event.preventDefault();

    const errors = validateWebsiteForm();

    if (Object.keys(errors).length > 0) {
      showNotification("error", t.fixErrors);
      return;
    }

    setIsSavingSite(true);

    const nextProject = {
      ...project,
      publish: {
        ...(project.publish || {}),
        subdomain: sanitizeSubdomain(siteForm.subdomain),
      },
      siteChrome: {
        ...defaultSiteChrome,
        ...(project.siteChrome || {}),
        brand: siteForm.brand,
        footerStoreName: siteForm.footerStoreName,
        logoUrl: siteForm.logoUrl,
        contactEmail: siteForm.contactEmail,
        phone: siteForm.phone,
        description: siteForm.description,
      },
    };

    try {
      const response = await fetch(`${API_URL}/website/settings`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          subdomain: sanitizeSubdomain(siteForm.subdomain),
          brand: siteForm.brand,
          footer_store_name: siteForm.footerStoreName,
          logo_url: siteForm.logoUrl,
          contact_email: siteForm.contactEmail,
          phone: siteForm.phone,
          description: siteForm.description,
        }),
      });

      const data = await readApiResponse(response);

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error(t.sessionExpired);
        }

        throw new Error(getApiErrorMessage(data.detail, t.accountError));
      }

      const savedWebsite = data.website || {};
      const savedProject = {
        ...nextProject,
        publish: {
          ...(nextProject.publish || {}),
          subdomain: sanitizeSubdomain(savedWebsite.subdomain || ""),
        },
      };

      localStorage.setItem(STORAGE_KEY, JSON.stringify(savedProject));
      setProject(savedProject);
      showNotification("success", data.message || t.websiteSaved);
    } catch (error) {
      showNotification("error", error.message || t.accountError);
    } finally {
      setIsSavingSite(false);
    }
  };

  return (
    <section className="settings-page" dir={isArabic ? "rtl" : "ltr"}>
      <SettingsNotification
        notification={notification}
        isArabic={isArabic}
        label={t.closeNotification}
        onClose={clearNotification}
      />

      <header className="settings-header">
        <div>
          <p>{t.eyebrow}</p>
          <h1>{t.title}</h1>
          <span>{t.subtitle}</span>
        </div>
      </header>

      <div className="settings-grid">
        <form
          className="settings-card settings-profile-card"
          onSubmit={saveAccount}
          noValidate
        >
          <div className="settings-profile-cover">
            <div>
              <span>{t.eyebrow}</span>
              <strong>
                {accountForm.first_name || accountForm.email || t.userAlt}
              </strong>
            </div>
          </div>

          <div className="settings-profile-summary">
            <div className="settings-profile-avatar">
              {shouldShowAvatarImage ? (
                <img
                  src={avatarUrl}
                  alt={accountForm.first_name || accountForm.email || t.userAlt}
                  onError={() => setAvatarLoadFailed(true)}
                />
              ) : (
                <span>{getAvatarLetter(accountForm, t.userFallback)}</span>
              )}
            </div>

            <div>
              <h2>{t.profileTitle}</h2>
              <p>{t.profileDescription}</p>
            </div>

            <label className="settings-file-button settings-profile-upload">
              {isUploadingAvatar ? t.saving : t.uploadProfilePhoto}
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                disabled={isUploadingAvatar}
                onChange={uploadAvatar}
              />
            </label>
          </div>

          <div className="settings-profile-body">
            <div className="settings-form-grid">
              <label>
                {t.firstName}
                <input
                  value={accountForm.first_name}
                  className={fieldErrors.first_name ? "field-has-error" : ""}
                  onChange={(event) =>
                    updateAccountField("first_name", event.target.value)
                  }
                />
                {fieldErrors.first_name && (
                  <span className="settings-field-error">
                    {fieldErrors.first_name}
                  </span>
                )}
              </label>

              <label>
                {t.lastName}
                <input
                  value={accountForm.last_name}
                  className={fieldErrors.last_name ? "field-has-error" : ""}
                  onChange={(event) =>
                    updateAccountField("last_name", event.target.value)
                  }
                />
                {fieldErrors.last_name && (
                  <span className="settings-field-error">
                    {fieldErrors.last_name}
                  </span>
                )}
              </label>

              <label>
                {t.email}
                <input
                  type="email"
                  value={accountForm.email}
                  className={fieldErrors.email ? "field-has-error" : ""}
                  onChange={(event) =>
                    updateAccountField("email", event.target.value)
                  }
                />
                {fieldErrors.email && (
                  <span className="settings-field-error">
                    {fieldErrors.email}
                  </span>
                )}
              </label>

              <label>
                {t.phoneNumber}
                <input
                  type="tel"
                  value={accountForm.phone}
                  placeholder="+972 ..."
                  onChange={(event) =>
                    updateAccountField("phone", event.target.value)
                  }
                />
              </label>
            </div>
          </div>

          <div className="settings-profile-actions">
            <SmartLink
              to="/settings/change-password"
              className="settings-reset-password-button"
            >
              <KeyRound size={18} />
              {t.changePassword}
            </SmartLink>

            <button
              className="settings-save-button"
              type="submit"
              disabled={isSavingAccount}
            >
              <Save size={18} />
              {isSavingAccount ? t.saving : t.saveProfile}
            </button>
          </div>
        </form>

        <form
          className="settings-card settings-profile-card settings-website-card"
          onSubmit={saveSiteSettings}
          noValidate
        >
          <div className="settings-profile-cover">
            <div>
              <span>{t.websiteTitle}</span>
              <strong>{siteForm.brand || t.websiteLogoAlt}</strong>
            </div>
          </div>

          <div className="settings-profile-summary">
            <div className="settings-profile-avatar">
              {canShowLogoImage ? (
                <img
                  src={resolveMediaUrl(siteForm.logoUrl)}
                  alt={siteForm.brand || t.websiteLogoAlt}
                  onError={(event) => {
                    event.currentTarget.style.display = "none";
                    event.currentTarget.parentElement?.classList.add(
                      "logo-load-failed"
                    );
                  }}
                />
              ) : (
                <span>
                  {siteForm.brand ? (
                    siteForm.brand.slice(0, 1).toUpperCase()
                  ) : (
                    <ImagePlus size={30} />
                  )}
                </span>
              )}
            </div>

            <div>
              <h2>{t.websiteTitle}</h2>
              <p>{t.websiteDescription}</p>
            </div>

            <label className="settings-file-button settings-profile-upload">
              {t.uploadLogo}
              <input
                type="file"
                accept="image/*"
                onChange={(event) =>
                  readImageFile(event.target.files?.[0], (value) =>
                    updateSiteField("logoUrl", value)
                  )
                }
              />
            </label>
          </div>

          <div className="settings-profile-body">
            <div className="settings-form-grid">
              <label>
                {t.subdomainName}
                <input
                  value={siteForm.subdomain}
                  className={fieldErrors.subdomain ? "field-has-error" : ""}
                  onChange={(event) =>
                    updateSiteField("subdomain", event.target.value)
                  }
                />
                {fieldErrors.subdomain && (
                  <span className="settings-field-error">
                    {fieldErrors.subdomain}
                  </span>
                )}
              </label>

              <label>
                {t.logoUrl}
                <input
                  value={siteForm.logoUrl}
                  className={fieldErrors.logoUrl ? "field-has-error" : ""}
                  onChange={(event) =>
                    updateSiteField("logoUrl", event.target.value)
                  }
                />
                {fieldErrors.logoUrl && (
                  <span className="settings-field-error">
                    {fieldErrors.logoUrl}
                  </span>
                )}
              </label>

              <label>
                {t.brandName}
                <input
                  value={siteForm.brand}
                  className={fieldErrors.brand ? "field-has-error" : ""}
                  onChange={(event) =>
                    updateSiteField("brand", event.target.value)
                  }
                />
                {fieldErrors.brand && (
                  <span className="settings-field-error">
                    {fieldErrors.brand}
                  </span>
                )}
              </label>

              <label>
                {t.footerName}
                <input
                  value={siteForm.footerStoreName}
                  onChange={(event) =>
                    updateSiteField("footerStoreName", event.target.value)
                  }
                />
              </label>

              <label>
                {t.contactEmail}
                <input
                  type="email"
                  value={siteForm.contactEmail}
                  className={fieldErrors.contactEmail ? "field-has-error" : ""}
                  onChange={(event) =>
                    updateSiteField("contactEmail", event.target.value)
                  }
                />
                {fieldErrors.contactEmail && (
                  <span className="settings-field-error">
                    {fieldErrors.contactEmail}
                  </span>
                )}
              </label>

              <label>
                {t.contactPhone}
                <input
                  type="tel"
                  value={siteForm.phone}
                  onChange={(event) =>
                    updateSiteField("phone", event.target.value)
                  }
                />
              </label>

              <label className="settings-wide-field">
                {t.websiteDescriptionLabel}
                <textarea
                  value={siteForm.description}
                  onChange={(event) =>
                    updateSiteField("description", event.target.value)
                  }
                />
              </label>
            </div>
          </div>

          <div className="settings-profile-actions settings-website-profile-actions">
            <div />

            <button
              className="settings-save-button"
              type="submit"
              disabled={isSavingSite}
            >
              <Save size={18} />
              {isSavingSite ? t.saving : t.saveWebsite}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
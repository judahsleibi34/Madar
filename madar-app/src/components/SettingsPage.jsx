import { useEffect, useMemo, useState } from "react";
import { ImagePlus, Save, Store, UserRound } from "lucide-react";
import {
  STORAGE_KEY,
  defaultSiteChrome,
} from "./PageBuilder/PageBuilder.constants";
import { createInitialProject } from "./PageBuilder/PageBuilder.starters";
import {
  getProjectSubdomain,
  sanitizeSubdomain,
} from "./PageBuilder/PageBuilder.routing";

const API_URL = import.meta.env.VITE_API_URL || "/api";

const readBuilderProject = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : createInitialProject();
  } catch {
    return createInitialProject();
  }
};

const getInitialAccountForm = (user) => ({
  first_name: user?.first_name || "",
  last_name: user?.last_name || "",
  email: user?.email || "",
  phone: user?.phone || "",
  avatar: user?.avatar || "",
});

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

const settingsCopy = {
  en: {
    eyebrow: "Workspace settings",
    title: "Profile and website settings",
    subtitle: "Keep your personal details, brand, and public website information up to date.",
    profileTitle: "Your profile",
    profileDescription: "This information helps personalize your workspace and customer-facing pages.",
    profilePhotoUrl: "Profile photo URL",
    uploadProfilePhoto: "Upload photo",
    firstName: "First name",
    lastName: "Last name",
    email: "Email",
    phoneNumber: "Phone number",
    saveProfile: "Save profile",
    saving: "Saving...",
    websiteTitle: "Website details",
    websiteDescription: "Set the name, contact details, and logo visitors see on your website.",
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
    websiteSaved: "Website settings saved.",
    accountError: "Could not update account settings.",
    sessionExpired: "Your session expired. Please log in again.",
    userAlt: "User",
    userFallback: "U",
  },
  ar: {
    eyebrow: "إعدادات مساحة العمل",
    title: "إعدادات الملف الشخصي والموقع",
    subtitle: "حدّث بياناتك الشخصية وهوية العلامة ومعلومات الموقع العامة.",
    profileTitle: "ملفك الشخصي",
    profileDescription: "تساعد هذه المعلومات في تخصيص مساحة عملك وصفحاتك أمام العملاء.",
    profilePhotoUrl: "رابط صورة الملف الشخصي",
    firstName: "الاسم الأول",
    lastName: "اسم العائلة",
    email: "البريد الإلكتروني",
    phoneNumber: "رقم الهاتف",
    saveProfile: "حفظ الملف الشخصي",
    saving: "جارٍ الحفظ...",
    websiteTitle: "تفاصيل الموقع",
    websiteDescription: "حدد الاسم وبيانات التواصل والشعار الذي يراه زوار موقعك.",
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
    websiteSaved: "تم حفظ تفاصيل الموقع.",
    accountError: "تعذر حفظ إعدادات الملف الشخصي.",
    sessionExpired: "انتهت جلستك. يرجى تسجيل الدخول مرة أخرى.",
    userAlt: "المستخدم",
    userFallback: "م",
  },
};

export default function SettingsPage({ lang = "en", user, onUserUpdated }) {
  const [accountForm, setAccountForm] = useState(() => getInitialAccountForm(user));
  const [project, setProject] = useState(readBuilderProject);
  const [status, setStatus] = useState("");
  const [isSavingAccount, setIsSavingAccount] = useState(false);
  const [isSavingSite, setIsSavingSite] = useState(false);
  const isArabic = lang === "ar";
  const t = settingsCopy[isArabic ? "ar" : "en"];
  const uploadProfileLabel = isArabic ? "\u0631\u0641\u0639 \u0635\u0648\u0631\u0629" : t.uploadProfilePhoto;

  const siteChrome = {
    ...defaultSiteChrome,
    ...(project.siteChrome || {}),
  };

  const siteForm = useMemo(() => ({
    subdomain: getProjectSubdomain(project),
    brand: siteChrome.brand || "",
    footerStoreName: siteChrome.footerStoreName || "",
    logoUrl: siteChrome.logoUrl || "",
    contactEmail: siteChrome.contactEmail || "",
    phone: siteChrome.phone || "",
    description: siteChrome.description || "",
  }), [project, siteChrome.brand, siteChrome.contactEmail, siteChrome.description, siteChrome.footerStoreName, siteChrome.logoUrl, siteChrome.phone]);

  const updateAccountField = (field, value) => {
    setAccountForm((prev) => ({ ...prev, [field]: value }));
    setStatus("");
  };

  useEffect(() => {
    setAccountForm(getInitialAccountForm(user));
  }, [user]);

  useEffect(() => {
    let cancelled = false;

    const loadAccount = async () => {
      try {
        const response = await fetch(`${API_URL}/user_info`, {
          method: "POST",
          credentials: "include",
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          if (!cancelled && response.status === 401) {
            setStatus(t.sessionExpired);
          }
          return;
        }

        if (!cancelled && data.user) {
          setAccountForm(getInitialAccountForm(data.user));
          onUserUpdated?.(data.user);
        }
      } catch {
        if (!cancelled) {
          setStatus(t.accountError);
        }
      }
    };

    loadAccount();

    return () => {
      cancelled = true;
    };
  }, [onUserUpdated, t.accountError, t.sessionExpired]);

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
    setStatus("");
  };

  const readImageFile = (file, callback) => {
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => callback(String(reader.result || ""));
    reader.readAsDataURL(file);
  };

  const saveAccount = async (event) => {
    event.preventDefault();
    setIsSavingAccount(true);
    setStatus("");

    try {
      const response = await fetch(`${API_URL}/user_profile`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildProfilePayload(accountForm)),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error(t.sessionExpired);
        }

        throw new Error(getApiErrorMessage(data.detail, t.accountError));
      }

      onUserUpdated?.(data.user);
      setStatus(t.accountSaved);
    } catch (error) {
      setStatus(error.message || t.accountError);
    } finally {
      setIsSavingAccount(false);
    }
  };

  const saveSiteSettings = (event) => {
    event.preventDefault();
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

    localStorage.setItem(STORAGE_KEY, JSON.stringify(nextProject));
    setProject(nextProject);
    setIsSavingSite(false);
    setStatus(t.websiteSaved);
  };

  return (
    <section className="settings-page" dir={isArabic ? "rtl" : "ltr"}>
      <header className="settings-header">
        <div>
          <p>{t.eyebrow}</p>
          <h1>{t.title}</h1>
          <span>{t.subtitle}</span>
        </div>
      </header>

      {status && <div className="settings-status">{status}</div>}

      <div className="settings-grid">
        <form className="settings-card settings-profile-card" onSubmit={saveAccount}>
          <div className="settings-profile-cover">
            <div>
              <span>{t.eyebrow}</span>
              <strong>{accountForm.first_name || accountForm.email || t.userAlt}</strong>
            </div>
          </div>

          <div className="settings-profile-summary">
            <div className="settings-profile-avatar">
              {accountForm.avatar ? (
                <img src={accountForm.avatar} alt={accountForm.first_name || t.userAlt} />
              ) : (
                <span>{(accountForm.first_name || accountForm.email || t.userFallback).trim().slice(0, 1).toUpperCase()}</span>
              )}
            </div>

            <div>
              <h2>{t.profileTitle}</h2>
              <p>{t.profileDescription}</p>
            </div>

            <label className="settings-file-button settings-profile-upload">
              {uploadProfileLabel}
              <input
                type="file"
                accept="image/*"
                onChange={(event) => readImageFile(event.target.files?.[0], (value) => updateAccountField("avatar", value))}
              />
            </label>
          </div>

          <div className="settings-profile-body">
            <div className="settings-form-grid">
              <label>
                {t.firstName}
                <input value={accountForm.first_name} onChange={(event) => updateAccountField("first_name", event.target.value)} />
              </label>
              <label>
                {t.lastName}
                <input value={accountForm.last_name} onChange={(event) => updateAccountField("last_name", event.target.value)} />
              </label>
              <label>
                {t.email}
                <input type="email" value={accountForm.email} onChange={(event) => updateAccountField("email", event.target.value)} />
              </label>
              <label>
                {t.phoneNumber}
                <input type="tel" value={accountForm.phone} placeholder="+972 ..." onChange={(event) => updateAccountField("phone", event.target.value)} />
              </label>
            </div>
          </div>

          <button className="settings-save-button" type="submit" disabled={isSavingAccount}>
            <Save size={18} />
            {isSavingAccount ? t.saving : t.saveProfile}
          </button>
        </form>

        <form className="settings-card settings-card-horizontal" onSubmit={saveSiteSettings}>
          <div className="settings-card-heading">
            <div className="settings-card-icon"><Store size={20} /></div>
            <div>
              <h2>{t.websiteTitle}</h2>
              <p>{t.websiteDescription}</p>
            </div>
          </div>

          <div className="settings-card-content">
            <div className="settings-logo-preview">
              {siteForm.logoUrl ? (
                <img src={siteForm.logoUrl} alt={siteForm.brand || t.websiteLogoAlt} />
              ) : (
                <div><ImagePlus size={26} /></div>
              )}
              <label className="settings-file-button">
                {t.uploadLogo}
                <input
                  type="file"
                  accept="image/*"
                  onChange={(event) => readImageFile(event.target.files?.[0], (value) => updateSiteField("logoUrl", value))}
                />
              </label>
            </div>

            <div className="settings-form-grid">
              <label>
                {t.subdomainName}
                <input value={siteForm.subdomain} onChange={(event) => updateSiteField("subdomain", event.target.value)} />
              </label>
              <label>
                {t.logoUrl}
                <input value={siteForm.logoUrl} onChange={(event) => updateSiteField("logoUrl", event.target.value)} />
              </label>
              <label>
                {t.brandName}
                <input value={siteForm.brand} onChange={(event) => updateSiteField("brand", event.target.value)} />
              </label>
              <label>
                {t.footerName}
                <input value={siteForm.footerStoreName} onChange={(event) => updateSiteField("footerStoreName", event.target.value)} />
              </label>
              <label>
                {t.contactEmail}
                <input type="email" value={siteForm.contactEmail} onChange={(event) => updateSiteField("contactEmail", event.target.value)} />
              </label>
              <label>
                {t.contactPhone}
                <input type="tel" value={siteForm.phone} onChange={(event) => updateSiteField("phone", event.target.value)} />
              </label>
              <label className="settings-wide-field">
                {t.websiteDescriptionLabel}
                <textarea value={siteForm.description} onChange={(event) => updateSiteField("description", event.target.value)} />
              </label>
            </div>
          </div>

          <button className="settings-save-button" type="submit" disabled={isSavingSite}>
            <Save size={18} />
            {isSavingSite ? t.saving : t.saveWebsite}
          </button>
        </form>
      </div>
    </section>
  );
}

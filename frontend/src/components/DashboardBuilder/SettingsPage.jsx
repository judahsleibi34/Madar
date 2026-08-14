import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Bell, Globe2, ImagePlus, KeyRound, MonitorSmartphone, Save, ShieldCheck, UserRound, X } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import SmartLink from "../SmartLink";
import {
  defaultSiteChrome,
  getBuilderStorageKey,
} from "../PageBuilder/core/PageBuilder.constants";
import { createInitialProject } from "../PageBuilder/core/PageBuilder.starters";
import {
  getConfiguredProjectSubdomain,
  sanitizeSubdomain,
} from "../PageBuilder/core/PageBuilder.routing";
import {
  fetchBuilderProject,
  listBuilderProjects,
  updateBuilderProject,
  uploadBuilderAsset,
} from "../PageBuilder/services/PageBuilder.api";
import { getBuilderAssetFileName } from "../PageBuilder/core/PageBuilder.uploadHandlers";
import { apiFetch } from "../../utils/apiClient";
import { resolveMediaUrl } from "../../utils/media";
import { getSettingsContent } from "../../content";
import { buildProfilePayload } from "./profilePayload";
import SecurityMfaPage from "./SecurityMfaPage";
import DeviceSettingsPanel from "./DeviceSettingsPanel";
import NotificationPreferencesPanel from "./NotificationPreferencesPanel";

const API_URL = import.meta.env.VITE_API_URL || "/api";
const AVATAR_MAX_BYTES = 5 * 1024 * 1024;
const AVATAR_MIME_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);
const BUILDER_ASSET_MAX_BYTES = 25 * 1024 * 1024;
const BUILDER_ASSET_MIME_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);
const BLOCKED_STORED_URL_SCHEMES = new Set(["javascript", "data", "vbscript", "file", "ftp"]);
const CONTROL_CHARS_PATTERN = new RegExp(
  `[${String.fromCharCode(0)}-${String.fromCharCode(31)}${String.fromCharCode(127)}]`,
  "u"
);
const URL_SCHEME_PATTERN = /^([a-z][a-z0-9+.-]*):/i;
const MANAGED_UPLOAD_ASSET_PATTERN =
  /^\/uploads\/tenant_[1-9][0-9]*\/builder_assets\/[a-f0-9]{32}\.(?:png|jpg|jpeg|webp)$/;
const accountInfoRequests = new Map();

const syncWebsiteDetailsToActiveBuilderProject = async (nextProject) => {
  const { projects } = await listBuilderProjects({ limit: 1, offset: 0 });
  const projectId = projects[0]?.id;
  if (!projectId) return null;

  const activeRecord = await fetchBuilderProject(projectId);
  if (!activeRecord) return null;

  const draftSchema = activeRecord.draft_schema || {};
  const expectedRevision = Number(activeRecord.draft_revision);
  return updateBuilderProject(projectId, {
    draft_schema: {
      ...draftSchema,
      publish: {
        ...(draftSchema.publish || {}),
        subdomain: getConfiguredProjectSubdomain(nextProject),
      },
      siteChrome: {
        ...defaultSiteChrome,
        ...(draftSchema.siteChrome || {}),
        ...(nextProject.siteChrome || {}),
      },
    },
    ...(Number.isInteger(expectedRevision) && expectedRevision >= 0
      ? { expected_revision: expectedRevision }
      : {}),
  });
};

const deferEffectStateUpdate = (callback) => {
  let cancelled = false;
  queueMicrotask(() => {
    if (!cancelled) callback();
  });
  return () => {
    cancelled = true;
  };
};

const readBuilderProject = (storageKey) => {
  try {
    const raw = localStorage.getItem(storageKey);
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

const loadAccountInfo = (url) => {
  if (!accountInfoRequests.has(url)) {
    const request = apiFetch(url, { method: "GET", cache: "no-store" })
      .then(async (response) => ({ response, data: await readApiResponse(response) }))
      .finally(() => accountInfoRequests.delete(url));
    accountInfoRequests.set(url, request);
  }
  return accountInfoRequests.get(url);
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

const resizeTextareaToContent = (textarea) => {
  if (!textarea) return;

  const minimumHeight = 48;
  const maximumHeight = 240;
  textarea.style.height = "auto";
  const contentHeight = Math.max(textarea.scrollHeight, minimumHeight);
  textarea.style.height = String(Math.min(contentHeight, maximumHeight)) + "px";
  textarea.style.overflowY = contentHeight > maximumHeight ? "auto" : "hidden";
};
const isValidEmail = (value) => {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || "").trim());
};

const isSvgUrlPath = (value) => {
  const path = String(value || "").split(/[?#]/, 1)[0].toLowerCase();
  return path.endsWith(".svg") || path.endsWith(".svgz");
};

const getStoredImageUrlError = (url) => {
  const cleanUrl = String(url || "").trim();

  if (!cleanUrl) return "";
  if (CONTROL_CHARS_PATTERN.test(cleanUrl)) return "invalid";
  if (cleanUrl.startsWith("//")) return "invalid";

  if (cleanUrl.startsWith("/")) {
    if (cleanUrl.includes("\\")) return "invalid";
    if (isSvgUrlPath(cleanUrl)) return "invalid";
    if (cleanUrl.startsWith("/uploads/") && !MANAGED_UPLOAD_ASSET_PATTERN.test(cleanUrl)) {
      return "invalid";
    }
    return "";
  }

  const schemeMatch = cleanUrl.match(URL_SCHEME_PATTERN);
  if (!schemeMatch) return "invalid";

  const scheme = schemeMatch[1].toLowerCase();

  if (BLOCKED_STORED_URL_SCHEMES.has(scheme)) return "invalid";
  if (scheme !== "https") return "invalid";

  try {
    const parsedUrl = new URL(cleanUrl);
    if (!parsedUrl.hostname) return "invalid";
    if (isSvgUrlPath(parsedUrl.pathname)) return "invalid";
  } catch {
    return "invalid";
  }

  return "";
};

const isDirectImageUrl = (url) => {
  const cleanUrl = String(url || "").trim();
  return Boolean(cleanUrl) && !getStoredImageUrlError(cleanUrl);
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

export default function SettingsPage({
  lang = "en",
  user,
  onUserUpdated,
  accountOnly = false,
  accountApiBasePath = "",
  initialTab = "profile",
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [accountForm, setAccountForm] = useState(() =>
    getInitialAccountForm(user)
  );

  const userId = user?.id;
  const scopedStorageKey = getBuilderStorageKey(userId);
  const [project, setProject] = useState(() => readBuilderProject(scopedStorageKey));
  const [fieldErrors, setFieldErrors] = useState({});
  const [notification, setNotification] = useState(null);

  const [isSavingAccount, setIsSavingAccount] = useState(false);
  const [isLoadingAccount, setIsLoadingAccount] = useState(false);
  const [isUploadingAvatar, setIsUploadingAvatar] = useState(false);
  const [isUploadingLogo, setIsUploadingLogo] = useState(false);
  const [isSavingSite, setIsSavingSite] = useState(false);
  const [avatarLoadFailed, setAvatarLoadFailed] = useState(false);

  const isArabic = lang === "ar";
  const t = getSettingsContent(lang);
  const pageCopy = accountOnly
    ? {
        ...t,
        eyebrow: "Admin settings",
        title: "Admin account settings",
        subtitle: "Update the name, photo, and contact details for your admin account.",
        profileTitle: "Admin profile",
        profileDescription: "These details are used for the admin dashboard and your account identity.",
      }
    : {
        ...t,
        title: isArabic ? "الإعدادات" : "Settings",
        subtitle: isArabic
          ? "أدر ملفك الشخصي وتفاصيل الموقع وأمان الحساب من مكان واحد."
          : "Manage your profile, website details, and account security in one place.",
      };
  const requestedTab = new URLSearchParams(location.search).get("tab");
  const initialAllowedTab =
    initialTab === "security" || (!accountOnly && ["website", "devices", "notifications"].includes(initialTab))
      ? initialTab
      : "profile";
  const activeTab = location.pathname.startsWith("/settings/security")
    ? "security"
    : requestedTab === "security"
      ? "security"
      : requestedTab === "website" && !accountOnly
        ? "website"
        : requestedTab === "devices" && !accountOnly
          ? "devices"
          : requestedTab === "notifications" && !accountOnly
            ? "notifications"
        : initialAllowedTab;
  const tabLabels = isArabic
    ? { profile: "الملف الشخصي", website: "الموقع", security: "الأمان", devices: t.devices.tab, notifications: t.notificationPreferences.tab }
    : { profile: "Profile", website: "Website", security: "Security", devices: t.devices.tab, notifications: t.notificationPreferences.tab };
  const settingsTabs = [
    { id: "profile", label: tabLabels.profile, icon: UserRound },
    ...(!accountOnly
      ? [
          { id: "website", label: tabLabels.website, icon: Globe2 },
          { id: "devices", label: tabLabels.devices, icon: MonitorSmartphone },
          { id: "notifications", label: tabLabels.notifications, icon: Bell },
        ]
      : []),
    { id: "security", label: tabLabels.security, icon: ShieldCheck },
  ];
  const selectSettingsTab = (tabId) => {
    if (tabId === "security") {
      navigate("/settings/security");
      return;
    }

    if (tabId === "website") {
      navigate("/settings?tab=website");
      return;
    }

    if (tabId === "devices") {
      navigate("/settings?tab=devices");
      return;
    }
    if (tabId === "notifications") {
      navigate("/settings?tab=notifications");
      return;
    }

    navigate("/settings");
  };
  const onUserUpdatedRef = useRef(onUserUpdated);
  const descriptionTextareaRef = useRef(null);

  useEffect(() => {
    return deferEffectStateUpdate(() => {
      setProject(readBuilderProject(scopedStorageKey));
    });
  }, [scopedStorageKey]);

  useEffect(() => {
    onUserUpdatedRef.current = onUserUpdated;
  }, [onUserUpdated]);

  const userApiPath = useCallback((path) => {
    if (accountApiBasePath) {
      const basePath = accountApiBasePath.startsWith("http")
        ? accountApiBasePath
        : `${API_URL}${accountApiBasePath.startsWith("/") ? "" : "/"}${accountApiBasePath}`;

      return `${basePath}${path}`;
    }

    if (!userId) {
      throw new Error(t.sessionExpired);
    }

    return `${API_URL}/users/${encodeURIComponent(userId)}${path}`;
  }, [accountApiBasePath, t.sessionExpired, userId]);

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

  useEffect(() => {
    resizeTextareaToContent(descriptionTextareaRef.current);
  }, [siteForm.description]);

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

    setFieldErrors((prev) => ({
      ...prev,
      first_name: errors.first_name || "",
      last_name: errors.last_name || "",
      email: "",
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
    return deferEffectStateUpdate(() => {
      setAccountForm(getInitialAccountForm(user));
      setAvatarLoadFailed(false);
    });
  }, [user, userId]);

  useEffect(() => {
    return deferEffectStateUpdate(() => {
      setAvatarLoadFailed(false);
    });
  }, [accountForm.avatar]);

  useEffect(() => {
    return () => {
      window.clearTimeout(window.__settingsNotificationTimer);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadAccount = async () => {
      if (!accountApiBasePath && !userId) return;
      setIsLoadingAccount(true);

      try {
        const { response, data } = await loadAccountInfo(userApiPath("/info"));

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
          onUserUpdatedRef.current?.(data.user);
        }
      } catch {
        if (!cancelled) {
          showNotification("error", t.accountError);
        }
      } finally {
        if (!cancelled) setIsLoadingAccount(false);
      }
    };

    loadAccount();

    return () => {
      cancelled = true;
    };
  }, [accountApiBasePath, t.accountError, t.sessionExpired, userApiPath, userId]);

  useEffect(() => {
    let cancelled = false;

    const loadWebsiteSettings = async () => {
      if (accountOnly) {
        return;
      }

      try {
        const response = await apiFetch(`${API_URL}/website/settings`, {
          method: "GET",
          cache: "no-store",
        });

        const data = await readApiResponse(response);

        if (!response.ok) {
          return;
        }

        const website = data.website || {};

        if (!cancelled) {
          setProject((prev) => {
            const nextProject = {
              ...prev,
              publish: {
                ...(prev.publish || {}),
                subdomain: sanitizeSubdomain(
                  website.standard_path_slug || website.subdomain || ""
                ),
              },
              siteChrome: {
                ...defaultSiteChrome,
                ...(prev.siteChrome || {}),
                brand: website.brand || "",
                footerStoreName: website.footer_store_name || "",
                logoUrl: website.logo_url || "",
                contactEmail: website.contact_email || "",
                phone: website.phone || "",
                description: website.description || "",
              },
            };

            localStorage.setItem(scopedStorageKey, JSON.stringify(nextProject));
            return nextProject;
          });
        }
      } catch {
        // Keep local settings visible if the backend settings request fails.
      }
    };

    loadWebsiteSettings();

    return () => {
      cancelled = true;
    };
  }, [accountOnly, scopedStorageKey]);

  const uploadWebsiteLogo = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";

    if (!file) return;

    if (!BUILDER_ASSET_MIME_TYPES.has(file.type)) {
      showNotification("error", t.invalidLogoType || t.invalidAvatarType);
      return;
    }

    if (file.size > BUILDER_ASSET_MAX_BYTES) {
      showNotification("error", t.logoTooLarge || t.avatarTooLarge);
      return;
    }

    setIsUploadingLogo(true);

    try {
      const assetUrl = await uploadBuilderAsset(file);

      if (!assetUrl) {
        throw new Error(t.logoUploadError);
      }

      updateSiteField("logoUrl", assetUrl);
      showNotification("success", t.logoUploaded);
    } catch (error) {
      showNotification(
        "error",
        error.message || t.logoUploadError
      );
    } finally {
      setIsUploadingLogo(false);
    }
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
      const response = await apiFetch(userApiPath("/avatar"), {
        method: "POST",
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
      const response = await apiFetch(userApiPath("/profile"), {
        method: "PUT",
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
      const response = await apiFetch(`${API_URL}/website/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          standard_path_slug: sanitizeSubdomain(siteForm.subdomain),
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
          subdomain: sanitizeSubdomain(
            savedWebsite.standard_path_slug || savedWebsite.subdomain || ""
          ),
        },
      };

      await syncWebsiteDetailsToActiveBuilderProject(savedProject);
      localStorage.setItem(scopedStorageKey, JSON.stringify(savedProject));
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
          <p>{pageCopy.eyebrow}</p>
          <h1>{pageCopy.title}</h1>
          <span>{pageCopy.subtitle}</span>
        </div>
      </header>

      <nav className="settings-tabs" role="tablist" aria-label={isArabic ? "أقسام الإعدادات" : "Settings sections"}>
        {settingsTabs.map(({ id, label, icon: TabIcon }) => (
          <button
            key={id}
            type="button"
            role="tab"
            className={activeTab === id ? "settings-tab is-active" : "settings-tab"}
            aria-selected={activeTab === id}
            aria-controls={"settings-panel-" + id}
            onClick={() => selectSettingsTab(id)}
          >
            <TabIcon size={18} aria-hidden="true" />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div
        className="settings-grid settings-tab-panel"
        id={"settings-panel-" + activeTab}
        role="tabpanel"
        aria-label={tabLabels[activeTab]}
      >
        {activeTab === "profile" && (
        <form
          className="settings-card settings-profile-card"
          onSubmit={saveAccount}
          noValidate
        >
          <div className="settings-profile-cover">
            <div>
              <span>{pageCopy.eyebrow}</span>
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
              <h2>{pageCopy.profileTitle}</h2>
              <p>{pageCopy.profileDescription}</p>
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
                  disabled={isLoadingAccount}
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
                  disabled={isLoadingAccount}
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
                  readOnly
                  disabled
                  aria-describedby="settings-canonical-email-help"
                />
                <small id="settings-canonical-email-help">
                  {t.emailChangeUnavailable}
                </small>
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
            {!accountOnly && (
              <SmartLink
                to="/settings/change-password"
                className="settings-reset-password-button"
              >
                <KeyRound size={18} />
                {t.changePassword}
              </SmartLink>
            )}

            <button
              className="settings-save-button"
              type="submit"
              disabled={isLoadingAccount || isSavingAccount}
            >
              <Save size={18} />
              {isSavingAccount ? t.saving : t.saveProfile}
            </button>
          </div>
        </form>
        )}

        {activeTab === "website" && !accountOnly && (
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

            <label
              className="settings-file-button settings-profile-upload"
              aria-disabled={isUploadingLogo}
            >
              {isUploadingLogo ? t.uploadingLogo : t.uploadLogo}
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                hidden
                disabled={isUploadingLogo}
                onChange={uploadWebsiteLogo}
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
                <small>
                  Included address: madarportal.com/site/{sanitizeSubdomain(siteForm.subdomain) || "business-name"}.
                  A branded .madarportal.com subdomain requires the separate paid add-on.
                </small>
              </label>

              <label>
                {t.logoUrl}
                <input
                  value={getBuilderAssetFileName(siteForm.logoUrl)}
                  className={fieldErrors.logoUrl ? "field-has-error" : ""}
                  readOnly
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
                  ref={(textarea) => {
                    descriptionTextareaRef.current = textarea;
                    resizeTextareaToContent(textarea);
                  }}
                  rows={1}
                  value={siteForm.description}
                  onChange={(event) => {
                    resizeTextareaToContent(event.currentTarget);
                    updateSiteField("description", event.target.value);
                  }}
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
        )}

        {activeTab === "security" && (
          <div className="settings-security-panel">
            <SecurityMfaPage lang={lang} embedded cacheKey={user?.id} />
          </div>
        )}

        {activeTab === "devices" && !accountOnly && (
          <DeviceSettingsPanel
            lang={lang}
            tenantId={user?.tenant_id}
            copy={t.devices}
            showNotification={showNotification}
          />
        )}
        {activeTab === "notifications" && !accountOnly && (
          <NotificationPreferencesPanel
            copy={t.notificationPreferences}
            showNotification={showNotification}
          />
        )}
      </div>
    </section>
  );
}

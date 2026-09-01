import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { defaultSiteChrome, fieldTypes, viewports } from "../core/PageBuilder.constants";
import {
  fetchPublicFormDraft,
  fetchPublicForm,
  fetchBuilderProject,
  fetchProtectedSitePage,
  fetchPublicSite,
  fetchPublicSiteBootstrap,
  getTenantVisitorStatus,
  loginTenantVisitor,
  logoutTenantVisitor,
  registerTenantVisitor,
  savePublicFormDraft,
  submitPublicBuilderEvent,
  submitPublicFormSubmission,
  startPublicQuizAttempt,
  finalizePublicQuizAttempt,
} from "../services/PageBuilder.api";
import { createFormIdempotencyKey } from "./formSubmission";
import RuntimeFormToast from "./RuntimeFormToast";
import { getRuntimeFieldError } from "./formValidation";
import { getSubmissionErrorGuidance } from "./formSubmissionErrors";
import {
  readRuntimeFormDrafts,
  removeRuntimeFormDraft,
  saveRuntimeFormDraft,
} from "./formDraftStorage";
import {
  addCompletedFormPage,
  completedFormPagesBefore,
  getFormPageNavigationItems,
} from "./formPageNavigation";
import { getFormSections } from "../core/PageBuilder.factories";
import { createElementRenderer } from "../core/PageBuilder.elementRenderer";
import SiteRenderer from "../core/PageBuilder.siteRenderer";
import { getPageBuilderThemeVars } from "../core/PageBuilder.theme";
import {
  getArtboardElementPosition,
  getLiveArtboardProfile,
  getLiveArtboardViewportMode,
  getLivePresentationZoom,
} from "../core/PageBuilder.artboard";
import {
  getContentDirection,
  getDefaultFormLanguage,
  getDirectionForLanguage,
  getLocalizedOptions,
  getLocalizedValue,
  normalizeLanguageMode,
} from "../core/PageBuilder.localization";
import "../../../styles/admin/PageBuilder/index.css";
import ReservationBlock from "../blocks/ReservationBlock";
import PhotoProofingBlock from "../blocks/PhotoProofingBlock";
import { resolveReservationBlockValue } from "../core/PageBuilder.reservations";
import { getResponsiveMediaProps, resolveMediaUrl } from "../../../utils/media";
import { getTenantRuntimeContent } from "../../../content/pageBuilder";
import useWeeklyScreenTime from "../../../hooks/useWeeklyScreenTime";
import { getReservationErrorMessage } from "./reservationSubmission";
import {
  getDefaultPublicPage,
  getStrictPublishedHomepage,
  getPublicPagePath,
  resolvePublicPageByPath,
  resolveStrictPublishedPageByPath,
} from "../core/PageBuilder.routing";
import {
  findPageByNavigationReference,
  getNavigablePages,
  getPageNavigationLabel,
} from "../core/PageBuilder.navigation";
import { runPublicElementAction } from "../core/PageBuilder.actions";
import { getStoredUrlError } from "../core/PageBuilder.url";
import {
  getFooterLinkItems,
  getSafeFooterLinkUrl,
  isExternalFooterLink,
} from "../core/PageBuilder.footerLinks";
import { createSiteChromeRenderers } from "../core/PageBuilder.siteChrome";
import {
  getElementLayoutWidth,
  getElementPlacementMargins,
  normalizeElementAlignSelf,
} from "../core/PageBuilder.elementLayout";
import {
  getBuilderElementStyle,
} from "../core/PageBuilder.styles";

const runtimeFallbackCopy = getTenantRuntimeContent("en");
const MADAR_ATTRIBUTION_URL = "https://madar.app/";
const TENANT_BRAND_CACHE_PREFIX = "madar:tenant-brand:";
const PUBLICATION_VERSION_POLL_MS = 30_000;

// eslint-disable-next-line react-refresh/only-export-components
export const getPublicationSnapshot = (payload) => {
  const publication = payload?.publication || payload?.project;
  const projectId = String(publication?.project_id || "").trim();
  const publishedVersion = Number(publication?.published_version);
  if (!projectId || !Number.isInteger(publishedVersion) || publishedVersion < 0) return null;
  return { projectId, publishedVersion };
};

// eslint-disable-next-line react-refresh/only-export-components
export const hasNewerPublication = (current, next) => {
  if (!current || !next) return false;
  return (
    next.projectId !== current.projectId ||
    next.publishedVersion > current.publishedVersion
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const getTenantBrandFallback = (subdomain) =>
  String(subdomain || "")
    .split("-")
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ") || "Website";

const getTenantBrandCacheKey = (boundary) => {
  if (!boundary || typeof boundary !== "object") return "";
  const hostname = String(boundary.hostname || "").trim().toLowerCase();
  const siteIdentifier = String(boundary.siteIdentifier || "").trim().toLowerCase();
  const siteId = String(boundary.siteId || "").trim();
  const projectId = String(boundary.projectId || "").trim();
  const publishedVersion = Number(boundary.publishedVersion);
  if (!hostname || !siteIdentifier || !siteId || !projectId || !Number.isInteger(publishedVersion)) return "";
  return `${TENANT_BRAND_CACHE_PREFIX}${hostname}:${siteIdentifier}:${siteId}:${projectId}:${publishedVersion}`;
};

// eslint-disable-next-line react-refresh/only-export-components
export const readCachedTenantBrand = (storage, boundary) => {
  try {
    const cacheKey = getTenantBrandCacheKey(boundary);
    if (!cacheKey) return null;
    const value = JSON.parse(storage?.getItem(cacheKey) || "null");
    if (!value || typeof value !== "object") return null;
    const brand = String(value.brand || "").trim().slice(0, 80);
    const logoUrl = String(value.logoUrl || "").trim().slice(0, 2048);
    const loadingImageUrl = String(value.loadingImageUrl || "").trim().slice(0, 2048);
    return brand || logoUrl || loadingImageUrl ? { brand, logoUrl, loadingImageUrl } : null;
  } catch {
    return null;
  }
};

// eslint-disable-next-line react-refresh/only-export-components
export const getTenantLoadingLogoUrl = ({
  settingsLogoUrl = "",
  logoUrl = "",
  loadingImageUrl = "",
} = {}) =>
  String(loadingImageUrl || settingsLogoUrl || logoUrl || "").trim();

// eslint-disable-next-line react-refresh/only-export-components
export const cacheTenantBrand = (storage, boundary, value) => {
  const brand = String(value?.brand || "").trim().slice(0, 80);
  const logoUrl = String(value?.logoUrl || "").trim().slice(0, 2048);
  const loadingImageUrl = String(value?.loadingImageUrl || "").trim().slice(0, 2048);
  const cacheKey = getTenantBrandCacheKey(boundary);
  if (!storage || !cacheKey || (!brand && !logoUrl && !loadingImageUrl)) return;
  try {
    storage.setItem(cacheKey, JSON.stringify({ brand, logoUrl, loadingImageUrl }));
  } catch {
    // Storage may be unavailable in private or restricted browsing contexts.
  }
};

// eslint-disable-next-line react-refresh/only-export-components
export const getVerifiedPublicationBoundary = (payload, siteIdentifier, hostname = "") => {
  const site = payload?.site;
  const publication = payload?.project;
  const cleanIdentifier = String(siteIdentifier || "").trim().toLowerCase();
  if (!site || !publication || String(site.subdomain || "").trim().toLowerCase() !== cleanIdentifier) return null;
  const siteId = String(publication.site_id || "").trim();
  const publicationIdentifier = String(publication.site_identifier || "").trim().toLowerCase();
  const projectId = String(publication.project_id || "").trim();
  const publishedVersion = Number(publication.published_version);
  const publicationKey = String(publication.publication_key || "").trim();
  if (
    !siteId || publicationIdentifier !== cleanIdentifier || !projectId ||
    !Number.isInteger(publishedVersion) || publishedVersion < 0 || !publicationKey
  ) return null;
  return {
    hostname: String(hostname || "").trim().toLowerCase(),
    siteIdentifier: cleanIdentifier,
    siteId,
    projectId,
    publishedVersion,
    publicationKey,
  };
};

const getTenantBrandStorage = () => {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
};

const splitLines = (value) =>
  String(value || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

const isInternalPageReference = (value) =>
  /^page_[a-z0-9-]{8,}$/i.test(String(value || "").trim());

const getRuntimeFieldOptions = (field, lang = "en") =>
  getLocalizedOptions(field, lang).filter((option) =>
    String(option || "").trim()
  );

const getAnswerValue = (answer) =>
  answer && typeof answer === "object" && !Array.isArray(answer) && "value" in answer
    ? answer.value
    : answer;

const normalizeRuntimeAnswerValue = (value) => {
  if (Array.isArray(value)) return value.map(normalizeRuntimeAnswerValue);
  return getAnswerValue(value);
};

const isOptionAnswerChecked = (answer, option, optionIndex) => {
  if (answer && typeof answer === "object" && !Array.isArray(answer)) {
    return answer.optionIndex === optionIndex;
  }

  return answer === option;
};

const isCheckboxOptionChecked = (answers, option, optionIndex) =>
  answers.some((answer) => {
    if (answer && typeof answer === "object" && !Array.isArray(answer)) {
      return answer.optionIndex === optionIndex;
    }

    return answer === option;
  });

const carouselElementTypes = new Set(["card", "carousel", "logoSlider", "carouselCards", "carouselSplit", "carouselSpotlight", "carouselStack", "carouselEditorial", "circularGallery"]);
const authElementTypes = new Set(["loginBlock", "registrationBlock"]);

const getPageElements = (page) =>
  (page?.sections || []).flatMap((section) => [
    ...(section.freeElements || []),
    ...(section.rows || []).flatMap((row) =>
      (row.columns || []).flatMap((column) => column.elements || [])
    ),
  ]);

// eslint-disable-next-line react-refresh/only-export-components
export const getRuntimePageSections = (page) =>
  Array.isArray(page?.sections) ? page.sections : [];

const getPageAuthElements = (page) =>
  getPageElements(page).filter((element) => authElementTypes.has(element.type));

// Runtime routing helpers are exported for focused tests alongside this component.
// eslint-disable-next-line react-refresh/only-export-components
export const getRuntimeAuthFlow = (pages = []) => ({
  entryPage:
    pages.find((page) =>
      getPageAuthElements(page).length > 0
    ) || null,
  destinationPageIds: new Set(
    pages.flatMap((page) =>
      getPageAuthElements(page)
        .filter((element) => element.type === "loginBlock")
        .map((element) => element.auth?.successPageId)
        .filter(Boolean)
    )
  ),
});

// eslint-disable-next-line react-refresh/only-export-components
export const getSafeProtectedReturnPath = (search = "") => {
  const value = new URLSearchParams(search).get("returnTo") || "";
  return value.startsWith("/") && !value.startsWith("//") && value.length <= 2048
    ? value.replace(/\/+$/, "") || "/"
    : "";
};

// eslint-disable-next-line react-refresh/only-export-components
export const runtimePageRequiresAuthentication = (page, destinationPageIds = new Set()) =>
  Boolean(
    page && (
      destinationPageIds.has(page.id) ||
      ["private", "authenticated", "members"].includes(
        String(page.visibility || "").toLowerCase()
      )
    )
  );

// eslint-disable-next-line react-refresh/only-export-components
export const getRuntimeNavigationPages = (pages = []) =>
  getNavigablePages(pages);

// eslint-disable-next-line react-refresh/only-export-components
export const resolveRuntimePage = ({
  pages = [],
  requestedPage = null,
  defaultPage = null,
  allowDefaultFallback = true,
  authEntryPage = null,
  authDestinationPageIds = new Set(),
  isPublicRuntime = true,
  authLoading = false,
  user = null,
} = {}) => {
  const fallbackPage = requestedPage || (allowDefaultFallback ? defaultPage || pages[0] : null);
  if (
    isPublicRuntime &&
    !authLoading &&
    !user &&
    runtimePageRequiresAuthentication(requestedPage, authDestinationPageIds) &&
    authEntryPage
  ) {
    return authEntryPage;
  }
  return fallbackPage;
};

const legacyFieldTypes = {
  money: { id: "money", label: runtimeFallbackCopy.legacyFieldTypes.money.label, group: runtimeFallbackCopy.legacyFieldTypes.money.group, input: "number" },
  phone: { id: "phone", label: runtimeFallbackCopy.legacyFieldTypes.phone.label, group: runtimeFallbackCopy.legacyFieldTypes.phone.group, input: "tel" },
  radio: { id: "radio", label: runtimeFallbackCopy.legacyFieldTypes.radio.label, group: runtimeFallbackCopy.legacyFieldTypes.radio.group, input: "radio" },
  yesNo: { id: "yesNo", label: runtimeFallbackCopy.legacyFieldTypes.yesNo.label, group: runtimeFallbackCopy.legacyFieldTypes.yesNo.group, input: "yesNo" },
  status: { id: "status", label: runtimeFallbackCopy.legacyFieldTypes.status.label, group: runtimeFallbackCopy.legacyFieldTypes.status.group, input: "select" },
};

const getFieldType = (type) => fieldTypes.find((item) => item.id === type) || legacyFieldTypes[type] || fieldTypes[0];

const getModernFieldPlaceholder = (field = {}, copy = runtimeFallbackCopy) => {
  const customPlaceholder = String(field.placeholder || "").trim();
  const genericPlaceholders = new Set(copy.placeholders.generic);

  if (!genericPlaceholders.has(customPlaceholder)) return customPlaceholder;

  const label = String(field.label || "").toLowerCase();

  if (field.type === "email" || label.includes("email")) return copy.placeholders.email;
  if (field.type === "phone" || label.includes("phone")) return copy.placeholders.phone;
  if (field.type === "url" || label.includes("website")) return copy.placeholders.website;
  if (field.type === "money" || label.includes("budget") || label.includes("amount")) return copy.placeholders.money;
  if (field.type === "number" || label.includes("size")) return copy.placeholders.number;
  if (field.type === "date") return copy.placeholders.date;
  if (field.type === "time") return copy.placeholders.time;
  if (field.type === "dropdown" || field.type === "status") return copy.placeholders.select;
  if (field.type === "radio") return copy.placeholders.radio;
  if (field.type === "checkboxes") return copy.placeholders.checkboxes;
  if (field.type === "paragraph" || label.includes("summary") || label.includes("details")) {
    return copy.placeholders.paragraph;
  }
  if (label.includes("name")) return copy.placeholders.name;

  return copy.placeholders.fallback;
};

const getRuntimeFormFields = (form) =>
  getFormSections(form).flatMap((section) => section.fields || []);

const isEmptyAnswer = (value) =>
  value === undefined ||
  value === null ||
  value === "" ||
  (Array.isArray(value) && value.length === 0);

const inputTypeForField = (fieldType) => {
  if (fieldType === "email") return "email";
  if (fieldType === "phone") return "tel";
  if (fieldType === "url") return "url";
  if (fieldType === "number") return "number";
  if (fieldType === "date") return "date";
  if (fieldType === "time") return "time";
  return "text";
};

const focusRuntimeField = (fieldId) => {
  if (!fieldId || typeof document === "undefined") return;
  requestAnimationFrame(() => requestAnimationFrame(() => {
    const field = Array.from(document.querySelectorAll("[data-runtime-field-id]"))
      .find((element) => element.dataset.runtimeFieldId === String(fieldId));
    if (!field) return;
    field.scrollIntoView({ behavior: "smooth", block: "center" });
    const control = field.querySelector("input, select, textarea, button");
    control?.focus({ preventScroll: true });
  }));
};

const unsupportedWorkspacePaths = new Set([
  "/login",
  "/signup",
  "/forgot-password",
  "/dashboard",
]);

const isUnsupportedWorkspacePath = (value = "") =>
  unsupportedWorkspacePaths.has(
    `/${String(value || "").replace(/^\/+/, "").replace(/\/+$/, "")}`
  );

const getCleanSubdomain = (value = "") =>
  String(value)
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9-]/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-+|-+$/g, "") || runtimeFallbackCopy.runtime.subdomain;

// Runtime breakpoints describe device classes, while `viewports` describes
// the logical builder canvases. Keeping those concepts separate prevents
// 412px and 430px phones from being rendered as a scaled-down tablet canvas.
// eslint-disable-next-line react-refresh/only-export-components
export const getRuntimeViewportForWidth = (width) => {
  return getLiveArtboardViewportMode(width);
};

const getRuntimeAvailableWidth = () => {
  if (typeof window === "undefined") return viewports.desktop;
  return Math.max(
    1,
    Number(document.documentElement?.clientWidth) || Number(window.innerWidth) || viewports.desktop
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const getRuntimeCanvasScale = (availableWidth, logicalWidth) => {
  const mode = Number(logicalWidth) === viewports.mobile
    ? "mobile"
    : Number(logicalWidth) === viewports.tablet
      ? "tablet"
      : "desktop";
  return getLivePresentationZoom(availableWidth, mode);
};

// Older projects may not contain all three breakpoint positions. Normalize the
// nearest saved layout instead of applying desktop pixels directly to a phone.
// eslint-disable-next-line react-refresh/only-export-components
export const getRuntimeDirectPosition = (element, viewportName) => {
  return getArtboardElementPosition(element, viewportName);
};

// eslint-disable-next-line react-refresh/only-export-components
export const getRuntimeDirectElements = (elements = []) =>
  Array.isArray(elements) ? elements : [];

const decodePathSegment = (value) => {
  try {
    return decodeURIComponent(value);
  } catch {
    return "";
  }
};

// eslint-disable-next-line react-refresh/only-export-components
export const getBuilderPreviewBasePath = (projectId) =>
  `/page-builder/projects/${encodeURIComponent(String(projectId || ""))}/preview`;

export default function TenantSiteRuntime({ draftPreview = false } = {}) {
  const params = useParams();
  const { projectId = "", subdomain = "my-site" } = params;
  const location = useLocation();
  const navigate = useNavigate();

  const cleanSubdomain = getCleanSubdomain(subdomain);
  const isPublicRuntime = !draftPreview;
  const [runtimeLayout, setRuntimeLayout] = useState(() => {
    const availableWidth = getRuntimeAvailableWidth();
    return { availableWidth, ...getLiveArtboardProfile(availableWidth) };
  });
  const {
    availableWidth: runtimeAvailableWidth,
    viewportMode: runtimeViewport,
    logicalWidth: runtimeLogicalWidth,
    presentationZoom: runtimePresentationZoom,
  } = runtimeLayout;
  const activePath = location.pathname;
  const previewBasePath = getBuilderPreviewBasePath(projectId);
  const runtimeBasePath = draftPreview ? previewBasePath : `/site/${cleanSubdomain}`;
  const directStandaloneFormId = params.formId
    ? decodePathSegment(params.formId)
    : "";
  const routePagePath = directStandaloneFormId
    ? `/forms/${params.formId}`
    : draftPreview
    ? location.pathname.slice(previewBasePath.length)
    : `/${params["*"] || ""}`;
  const standaloneFormMatch = !draftPreview
    ? routePagePath.match(/^\/forms\/([^/]+)\/?$/)
    : null;
  const standaloneFormId = directStandaloneFormId || (standaloneFormMatch
    ? decodePathSegment(standaloneFormMatch[1])
    : "");
  const [project, setProject] = useState(null);
  const effectiveRuntimeLogicalWidth = runtimeLogicalWidth;
  const effectiveRuntimePresentationZoom = runtimePresentationZoom;
  const [publicSiteProfile, setPublicSiteProfile] = useState(null);
  const [publicSiteState, setPublicSiteState] = useState("loading");
  const [publicationBoundary, setPublicationBoundary] = useState(null);
  const [publicationUpdate, setPublicationUpdate] = useState(null);
  const [formAnswers, setFormAnswers] = useState({});
  const [formHoneypots, setFormHoneypots] = useState({});
  const [formStatus, setFormStatus] = useState({});
  const [formFieldErrors, setFormFieldErrors] = useState({});
  const [reservationStatus, setReservationStatus] = useState({});
  const [formPages, setFormPages] = useState({});
  const [completedFormPages, setCompletedFormPages] = useState({});
  const [formLanguages, setFormLanguages] = useState({});
  const [formResumeTokens, setFormResumeTokens] = useState({});
  const [quizAttempts, setQuizAttempts] = useState({});
  const [authPanelModes, setAuthPanelModes] = useState({});
  const [publicActionMessage, setPublicActionMessage] = useState("");
  const [formToast, setFormToast] = useState(null);
  const [tenantAuth, setTenantAuth] = useState({ loading: !draftPreview, user: null, message: "", error: "" });
  useWeeklyScreenTime(draftPreview ? null : tenantAuth.user, {
    endpoint: "/public/sites/" + encodeURIComponent(cleanSubdomain) + "/screen-time/heartbeat",
    scope: "site:" + cleanSubdomain,
  });
  const publicSubmissionStartedAtRef = useRef(Date.now());
  const formIdempotencyKeysRef = useRef({});
  const protectedPageRequestRef = useRef("");
  const pendingProtectedPageRef = useRef("");
  const loadedResumeTokenRef = useRef("");
  const detectedPublicationRef = useRef("");

  const showFormToast = useCallback((title, message) => {
    setFormToast({ id: Date.now(), title, message });
  }, []);

  const dismissFormToast = useCallback(() => setFormToast(null), []);

  useEffect(() => {
    if (draftPreview) return;

    const drafts = readRuntimeFormDrafts(getTenantBrandStorage(), cleanSubdomain);
    const restoredAnswers = {};
    const restoredPages = {};
    const restoredLanguages = {};
    const restoredResumeTokens = {};
    const restoredStatuses = {};
    const restoredCompletedPages = {};

    Object.entries(drafts).forEach(([instanceKey, draft]) => {
      restoredAnswers[instanceKey] = draft.answers || {};
      restoredPages[instanceKey] = Math.max(0, Number(draft.pageIndex) || 0);
      restoredCompletedPages[instanceKey] = completedFormPagesBefore(
        restoredPages[instanceKey],
      );
      restoredLanguages[instanceKey] = draft.language || "en";
      if (draft.resumeToken) {
        restoredResumeTokens[instanceKey] = draft.resumeToken;
      }
      restoredStatuses[instanceKey] = {
        submitting: false,
        error: "",
        success: runtimeFallbackCopy.runtime.resumeLaterRestored,
      };
    });

    setFormAnswers(restoredAnswers);
    setFormPages(restoredPages);
    setCompletedFormPages(restoredCompletedPages);
    setFormLanguages(restoredLanguages);
    setFormResumeTokens(restoredResumeTokens);
    setFormStatus(restoredStatuses);
  }, [cleanSubdomain, draftPreview]);

  useEffect(() => {
    const resumeToken = new URLSearchParams(location.search).get("resume") || "";
    if (draftPreview || !standaloneFormId || !resumeToken || loadedResumeTokenRef.current === resumeToken) return;
    loadedResumeTokenRef.current = resumeToken;
    const instanceKey = `published-form-link_${standaloneFormId}`;
    let cancelled = false;
    fetchPublicFormDraft(cleanSubdomain, standaloneFormId, resumeToken)
      .then((draft) => {
        if (cancelled || !draft) return;
        const answers = draft.answers || {};
        const pageIndex = Math.max(0, Number(draft.pageIndex) || 0);
        const language = draft.language || "en";
        setFormAnswers((current) => ({ ...current, [instanceKey]: answers }));
        setFormPages((current) => ({ ...current, [instanceKey]: pageIndex }));
        setCompletedFormPages((current) => ({
          ...current,
          [instanceKey]: completedFormPagesBefore(pageIndex),
        }));
        setFormLanguages((current) => ({ ...current, [instanceKey]: language }));
        setFormResumeTokens((current) => ({ ...current, [instanceKey]: resumeToken }));
        setFormStatus((current) => ({
          ...current,
          [instanceKey]: { submitting: false, error: "", success: runtimeFallbackCopy.runtime.resumeLaterRestored },
        }));
        saveRuntimeFormDraft(getTenantBrandStorage(), cleanSubdomain, instanceKey, {
          formId: standaloneFormId,
          answers,
          pageIndex,
          language,
          draftId: draft.id,
          resumeToken,
        });
      })
      .catch((error) => {
        if (cancelled) return;
        const guidance = getSubmissionErrorGuidance(error, [], runtimeFallbackCopy);
        showFormToast("Could not resume this form", guidance.message);
      });
    return () => {
      cancelled = true;
    };
  }, [cleanSubdomain, draftPreview, location.search, showFormToast, standaloneFormId]);

  const loadProtectedPage = useCallback(async (pageReference) => {
    const cleanReference = String(pageReference || "").replace(/^\/+/, "");
    if (draftPreview || !cleanReference) return null;
    if (protectedPageRequestRef.current === cleanReference) return null;

    protectedPageRequestRef.current = cleanReference;
    try {
      const result = await fetchProtectedSitePage(cleanSubdomain, cleanReference);
      const nextBoundary = getVerifiedPublicationBoundary(
        result,
        cleanSubdomain,
        window.location.hostname
      );
      if (
        !nextBoundary || !publicationBoundary ||
        nextBoundary.siteId !== publicationBoundary.siteId ||
        nextBoundary.projectId !== publicationBoundary.projectId ||
        nextBoundary.publishedVersion !== publicationBoundary.publishedVersion
      ) throw new Error("Published site changed while loading the page.");
      const schema = result?.project?.published_schema;
      if (!schema || typeof schema !== "object") return null;
      setProject(schema);
      setPublicSiteProfile(result?.site || null);
      setPublicSiteState("ready");
      return (schema.pages || []).find((page) =>
        String(page.id || "") === cleanReference ||
        String(page.slug || "").replace(/^\/+/, "") === cleanReference
      ) || null;
    } finally {
      protectedPageRequestRef.current = "";
    }
  }, [cleanSubdomain, draftPreview, publicationBoundary]);

  useEffect(() => {
    if (draftPreview) return;
    let cancelled = false;

    getTenantVisitorStatus(cleanSubdomain)
      .then((result) => {
        if (!cancelled) setTenantAuth({ loading: false, user: result?.logged_in ? result.user : null, message: "", error: "" });
      })
      .catch(() => {
        if (!cancelled) setTenantAuth({ loading: false, user: null, message: "", error: "" });
      });

    return () => {
      cancelled = true;
    };
  }, [cleanSubdomain, draftPreview]);

  const submitTenantAuth = async (event, isRegistration, authElement) => {
    event.preventDefault();
    if (draftPreview || tenantAuth.loading) return;

    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const password = String(form.get("password") || "");
    const confirmPassword = String(form.get("confirmPassword") || "");

    if (isRegistration && password !== confirmPassword) {
      setTenantAuth((current) => ({ ...current, error: "Passwords do not match.", message: "" }));
      return;
    }

    setTenantAuth((current) => ({ ...current, loading: true, error: "", message: "" }));

    try {
      const result = isRegistration
        ? await registerTenantVisitor(cleanSubdomain, {
            full_name: String(form.get("fullName") || "").trim(),
            email: String(form.get("email") || "").trim(),
            password,
          })
        : await loginTenantVisitor(cleanSubdomain, {
            email: String(form.get("email") || "").trim(),
            password,
          });

      setTenantAuth({
        loading: false,
        user: result?.logged_in ? result.user : null,
        message: result?.message || (result?.logged_in ? "You are logged in." : "Account created. Check your email, then log in."),
        error: "",
      });
      if (isRegistration) {
        setAuthPanelModes((current) => ({ ...current, [authElement.id]: false }));
      }
      formElement.reset();
      if (isRegistration && result?.requires_email_verification) {
        const pageContainsLogin = (page) => (page.sections || []).some((section) =>
          (section.freeElements || []).some((item) => item.type === "loginBlock") ||
          (section.rows || []).some((row) =>
            (row.columns || []).some((column) =>
              (column.elements || []).some((item) => item.type === "loginBlock")
            )
          )
        );
        const currentPageIndex = pages.findIndex((page) => page.id === activePage?.id);
        const destination =
          pages.find((page) => page.id === authElement?.auth?.successPageId) ||
          pages.find(pageContainsLogin) ||
          pages[currentPageIndex + 1];
        if (destination && destination.id !== activePage?.id) goToPage(destination);
      } else if (result?.logged_in) {
        const returnPath =
          pendingProtectedPageRef.current ||
          getSafeProtectedReturnPath(location.search);
        if (returnPath) {
          try {
            const destination = await loadProtectedPage(returnPath);
            pendingProtectedPageRef.current = "";
            if (destination) {
              navigate(getPublicPagePath(runtimeBasePath, destination), { replace: true });
              return;
            }
          } catch (error) {
            pendingProtectedPageRef.current = "";
            if (error?.status === 403) {
              setPublicActionMessage("Your role cannot access this page.");
              navigate(getPublicPagePath(runtimeBasePath, authEntryPage), { replace: true });
              return;
            }
            throw error;
          }
        }
        const currentPageIndex = pages.findIndex((page) => page.id === activePage?.id);
        let destination = pages.find(
          (page) => page.id === authElement?.auth?.successPageId
        );
        if (authElement?.auth?.successPageId && !destination) {
          destination = await loadProtectedPage(authElement.auth.successPageId);
        }
        destination ||= pages[currentPageIndex + 1] || pages[0];
        if (destination && destination.id !== activePage?.id) goToPage(destination);
      }
    } catch (error) {
      setTenantAuth({ loading: false, user: null, message: "", error: error?.message || "Please try again." });
    }
  };

  const logOutTenantVisitor = async () => {
    if (tenantAuth.loading) return;
    setTenantAuth((current) => ({ ...current, loading: true, error: "", message: "" }));
    try {
      await logoutTenantVisitor(cleanSubdomain);
      setTenantAuth({ loading: false, user: null, message: "You are logged out.", error: "" });
    } catch (error) {
      setTenantAuth((current) => ({ ...current, loading: false, error: error?.message || "Please try again." }));
    }
  };

  useEffect(() => {
    if (draftPreview) {
      let cancelled = false;
      setProject(null);
      setPublicationBoundary(null);
      setPublicSiteState("loading");
      if (!projectId) {
        setPublicSiteState("unavailable");
        return undefined;
      }

      fetchBuilderProject(projectId)
        .then((record) => {
          if (cancelled) return;
          const serverDraft = record?.draft_schema;
          if (serverDraft && typeof serverDraft === "object") {
            setProject(serverDraft);
            setPublicSiteState("ready");
          } else {
            setPublicSiteState("unavailable");
          }
        })
        .catch(() => {
          if (!cancelled) setPublicSiteState("unavailable");
        });

      return () => {
        cancelled = true;
      };
    }

    let cancelled = false;
    setProject(null);
    setPublicSiteProfile(null);
    setPublicationBoundary(null);
    setPublicationUpdate(null);
    detectedPublicationRef.current = "";
    setPublicSiteState("loading");

    if (!standaloneFormId) {
      fetchPublicSiteBootstrap(cleanSubdomain)
        .then((bootstrap) => {
          if (!cancelled && bootstrap?.site) {
            setPublicSiteProfile(bootstrap.site);
          }
        })
        .catch(() => {});
    }

    const loadBackendPublicContent = async () => {
      try {
        const publicContent = standaloneFormId
          ? await fetchPublicForm(cleanSubdomain, standaloneFormId)
          : await fetchPublicSite(cleanSubdomain);

        if (cancelled) return;

        if (standaloneFormId) {
          setPublicSiteProfile(publicContent?.site || null);
          const standalonePublication = getPublicationSnapshot(publicContent);
          if (standalonePublication) {
            setPublicationBoundary(standalonePublication);
          }
          if (publicContent?.form && typeof publicContent.form === "object") {
            setProject({
              forms: [publicContent.form],
              pages: [],
              theme: publicContent.theme || {},
              language: publicContent.language || "en",
              siteChrome: {},
              activeFormId: publicContent.form.id,
            });
            setPublicSiteState("ready");
            return;
          }

          setProject(null);
          setPublicSiteState("unavailable");
          return;
        }

        const publishedProject = publicContent?.project?.published_schema;
        const verifiedBoundary = getVerifiedPublicationBoundary(
          publicContent,
          cleanSubdomain,
          window.location.hostname
        );

        if (verifiedBoundary && publishedProject && typeof publishedProject === "object") {
          setPublicationBoundary(verifiedBoundary);
          setPublicSiteProfile(publicContent?.site || null);
          setProject(publishedProject);
          setPublicSiteState("ready");
          return;
        }

        setProject(null);
        setPublicSiteState("unavailable");
      } catch {
        if (cancelled) return;
        setProject(null);
        setPublicSiteState("unavailable");
        if (import.meta.env.DEV) {
          console.warn("Could not load published site from backend.");
        }
      }
    };

    loadBackendPublicContent();

    return () => {
      cancelled = true;
    };
  }, [cleanSubdomain, draftPreview, projectId, standaloneFormId]);
  useEffect(() => {
    if (draftPreview || !publicationBoundary) return undefined;

    let cancelled = false;
    let checking = false;
    const currentPublication = {
      projectId: publicationBoundary.projectId,
      publishedVersion: publicationBoundary.publishedVersion,
    };

    const checkForPublicationUpdate = async () => {
      if (
        cancelled ||
        checking ||
        document.visibilityState === "hidden" ||
        !document.querySelector(".tenant-runtime-page .runtime-form")
      ) return;
      checking = true;
      try {
        const bootstrap = await fetchPublicSiteBootstrap(cleanSubdomain);
        const nextPublication = getPublicationSnapshot(bootstrap);
        if (!cancelled && hasNewerPublication(currentPublication, nextPublication)) {
          const fingerprint = `${nextPublication.projectId}:${nextPublication.publishedVersion}`;
          if (detectedPublicationRef.current !== fingerprint) {
            detectedPublicationRef.current = fingerprint;
            setPublicationUpdate(nextPublication);
          }
        }
      } catch {
        // A temporary version-check failure must not interrupt a form in progress.
      } finally {
        checking = false;
      }
    };

    const interval = window.setInterval(checkForPublicationUpdate, PUBLICATION_VERSION_POLL_MS);
    const checkWhenVisible = () => {
      if (document.visibilityState === "visible") checkForPublicationUpdate();
    };
    window.addEventListener("focus", checkForPublicationUpdate);
    document.addEventListener("visibilitychange", checkWhenVisible);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
      window.removeEventListener("focus", checkForPublicationUpdate);
      document.removeEventListener("visibilitychange", checkWhenVisible);
    };
  }, [cleanSubdomain, draftPreview, publicationBoundary]);


  const site = {
    ...defaultSiteChrome,
    ...(publicSiteProfile
      ? {
          brand: publicSiteProfile.brand || defaultSiteChrome.brand,
          footerStoreName:
            publicSiteProfile.footer_store_name ||
            publicSiteProfile.brand ||
            defaultSiteChrome.footerStoreName,
          logoUrl: publicSiteProfile.logo_url || "",
          loadingImageUrl: publicSiteProfile.loading_image_url || "",
          contactEmail:
            publicSiteProfile.contact_email || defaultSiteChrome.contactEmail,
          phone: publicSiteProfile.phone || defaultSiteChrome.phone,
          description:
            publicSiteProfile.description || defaultSiteChrome.description,
        }
      : {}),
    ...(project?.siteChrome || {}),
  };
  const runtimeLanguage =
    project?.language ||
    project?.lang ||
    site.language ||
    site.lang ||
    "en";
  const runtimeDirection =
    String(runtimeLanguage || "").toLowerCase().startsWith("ar") ? "rtl" : "ltr";
  const runtimeCopy = getTenantRuntimeContent(runtimeDirection === "rtl" ? "ar" : "en");

  const pages = useMemo(
    () => (project?.pages || []),
    [project?.pages]
  );
  const pagePath = routePagePath && routePagePath !== "/" ? routePagePath : "/";
  const normalizedPagePath = pagePath === "/" ? "/" : pagePath.replace(/\/+$/, "");
  const defaultPage = useMemo(
    () => draftPreview
      ? getDefaultPublicPage(pages, project?.defaultPageId)
      : getStrictPublishedHomepage(pages, project?.defaultPageId),
    [draftPreview, pages, project?.defaultPageId]
  );
  const requestedPage = useMemo(() => {
    return draftPreview
      ? resolvePublicPageByPath(pages, pagePath, project?.defaultPageId)
      : resolveStrictPublishedPageByPath(pages, pagePath, project?.defaultPageId);
  }, [draftPreview, pagePath, pages, project?.defaultPageId]);
  const { entryPage: authEntryPage, destinationPageIds: authDestinationPageIds } = useMemo(
    () => getRuntimeAuthFlow(pages),
    [pages]
  );
  const pageRequiresAuthentication = useCallback(
    (page) => runtimePageRequiresAuthentication(page, authDestinationPageIds),
    [authDestinationPageIds]
  );
  const hasBuilderPageForRoute = Boolean(requestedPage);
  const isUnsupportedWorkspaceRoute =
    !hasBuilderPageForRoute &&
    (activePath.endsWith("/login") ||
      activePath.endsWith("/signup") ||
      activePath.endsWith("/forgot-password") ||
      activePath.endsWith("/dashboard"));

  const siteHomePath = getPublicPagePath(runtimeBasePath, defaultPage || { isDefault: true });

  const pageLinks = splitLines(site.footerShopLinks || "");
  const helpLinks = splitLines(site.footerHelpLinks || "");
  const socialLinks = getFooterLinkItems(
    site.footerSocialItems,
    site.footerSocialLinks || ""
  );
  const paymentLinks = getFooterLinkItems(
    site.footerPaymentItems,
    site.footerPaymentMethods || ""
  );
  const footerLinks = [...pageLinks, ...helpLinks].filter((item) => {
    if (isInternalPageReference(item)) {
      return pages.some((page) => String(page.id || "") === String(item));
    }
    if (!isUnsupportedWorkspacePath(item)) return true;

    const normalizedItem = String(item || "").toLowerCase().trim();
    return pages.some((page) => {
      const normalizedName = String(page.name || "").toLowerCase().trim();
      const normalizedSlug = String(page.slug || "")
        .toLowerCase()
        .replace(/^\//, "")
        .replace(/\/+$/, "");

      return (
        normalizedName === normalizedItem ||
        normalizedSlug === normalizedItem.replace(/\s+/g, "-")
      );
    });
  });

  useEffect(() => {
    if (isUnsupportedWorkspaceRoute) {
      navigate(siteHomePath, { replace: true });
    }
  }, [isUnsupportedWorkspaceRoute, navigate, siteHomePath]);

  const brandName = site.brand || runtimeCopy.runtime.brand;
  const footerBrand = site.footerStoreName || brandName;
  const footerInitial = footerBrand.trim().slice(0, 1).toUpperCase() || runtimeCopy.runtime.footerInitial;

  useEffect(() => {
    if (!isPublicRuntime || publicSiteState !== "ready") return;
    const nextBrand = {
      brand: brandName,
      logoUrl: publicSiteProfile?.logo_url || site.logoUrl || "",
      loadingImageUrl: site.loadingImageUrl || "",
    };
    cacheTenantBrand(getTenantBrandStorage(), publicationBoundary, nextBrand);
  }, [brandName, isPublicRuntime, publicationBoundary, publicSiteProfile?.logo_url, publicSiteState, site.loadingImageUrl, site.logoUrl]);

  const getPageDestinationPath = useCallback((page) => {
    if (!page) {
      return siteHomePath;
    }

    const destination =
      isPublicRuntime &&
      !tenantAuth.loading &&
      !tenantAuth.user &&
      pageRequiresAuthentication(page) &&
      authEntryPage
        ? authEntryPage
        : page;
    return getPublicPagePath(runtimeBasePath, destination);
  }, [
    authEntryPage,
    isPublicRuntime,
    pageRequiresAuthentication,
    runtimeBasePath,
    siteHomePath,
    tenantAuth.loading,
    tenantAuth.user,
  ]);

  const goToPage = useCallback((page) => {
    navigate(getPageDestinationPath(page));
  }, [getPageDestinationPath, navigate]);

  useEffect(() => {
    if (
      !isPublicRuntime ||
      publicSiteState !== "ready" ||
      tenantAuth.loading ||
      requestedPage ||
      pagePath === "/"
    ) {
      return;
    }
    loadProtectedPage(pagePath).catch((error) => {
      if (error?.status !== 401 || !authEntryPage || tenantAuth.user) return;
      pendingProtectedPageRef.current = normalizedPagePath;
      const loginPath = getPublicPagePath(runtimeBasePath, authEntryPage);
      navigate(
        loginPath + "?returnTo=" + encodeURIComponent(normalizedPagePath),
        { replace: true }
      );
    });
  }, [
    authEntryPage,
    isPublicRuntime,
    loadProtectedPage,
    navigate,
    normalizedPagePath,
    pagePath,
    publicSiteState,
    requestedPage,
    runtimeBasePath,
    tenantAuth.loading,
    tenantAuth.user,
  ]);

  const runPublicButtonAction = (element) => runPublicElementAction({
    element,
    pages,
    goToPage,
    getStoredUrlError,
    openExternal: (url, openInNewTab) => {
      if (openInNewTab) {
        window.open(url, "_blank", "noopener,noreferrer");
      } else {
        window.location.assign(url);
      }
    },
    showMessage: setPublicActionMessage,
    showUnavailable: setPublicActionMessage,
  });

  const resolveFooterPageLink = (value) => {
    const normalizedValue = String(value || "")
      .toLowerCase()
      .replace(/^\//, "")
      .replace(/\/+$/, "")
      .trim();

    return pages.find((page) => {
      const normalizedId = String(page.id || "").toLowerCase();
      const normalizedName = String(page.name || "").toLowerCase().trim();
      const normalizedSlug = String(page.slug || "")
        .toLowerCase()
        .replace(/^\//, "")
        .replace(/\/+$/, "");

      return (
        normalizedId === normalizedValue ||
        normalizedName === normalizedValue ||
        normalizedSlug === normalizedValue ||
        normalizedSlug === normalizedValue.replace(/\s+/g, "-")
      );
    });
  };

  const goToFooterLink = (label) => {
    const normalizedLabel = label.toLowerCase().trim();
    const target = resolveFooterPageLink(label);

    if (target) {
      goToPage(target);
      return;
    }

    if (normalizedLabel === "home") {
      navigate(siteHomePath);
      return;
    }

    if (isUnsupportedWorkspacePath(normalizedLabel)) {
      navigate(siteHomePath);
    }
  };

  const goToHeaderButton = () => {
    const targetValue = String(site.headerButtonPageId || site.headerButtonHref || site.headerButtonLabel || "").trim();
    if (!targetValue) return;

    const targetPage = findPageByNavigationReference(pages, targetValue);

    if (targetPage) {
      goToPage(targetPage);
    }
  };

  const activePage = resolveRuntimePage({
    pages,
    requestedPage,
    defaultPage,
    allowDefaultFallback: normalizedPagePath === "/",
    authEntryPage,
    authDestinationPageIds,
    isPublicRuntime,
    authLoading: tenantAuth.loading,
    user: tenantAuth.user,
  });

  useEffect(() => {
    setPublicActionMessage("");
  }, [activePage?.id]);

  useEffect(() => {
    if (!isPublicRuntime || publicSiteState !== "ready" || tenantAuth.loading || !pages.length) return;

    const destination =
      activePage && (!requestedPage || activePage.id !== requestedPage.id)
        ? activePage
        : null;

    if (!destination) return;
    const destinationPath = getPublicPagePath(runtimeBasePath, destination);
    if (location.pathname !== destinationPath) navigate(destinationPath, { replace: true });
  }, [
    authEntryPage,
    activePage,
    isPublicRuntime,
    location.pathname,
    navigate,
    pages,
    publicSiteState,
    requestedPage,
    runtimeBasePath,
    tenantAuth.loading,
    tenantAuth.user,
  ]);

  useEffect(() => {
    if (!tenantAuth.user || !activePage) return;
    if (pendingProtectedPageRef.current || getSafeProtectedReturnPath(location.search)) return;

    const loginElement = (activePage.sections || [])
      .flatMap((section) => [
        ...(section.freeElements || []),
        ...(section.rows || []).flatMap((row) =>
          (row.columns || []).flatMap((column) => column.elements || [])
        ),
      ])
      .find((element) => element.type === "loginBlock");

    if (!loginElement) return;

    const currentPageIndex = pages.findIndex((page) => page.id === activePage.id);
    const destination =
      pages.find((page) => page.id === loginElement.auth?.successPageId) ||
      pages[currentPageIndex + 1] ||
      pages[0];

    if (destination && destination.id !== activePage.id) {
      navigate(getPublicPagePath(runtimeBasePath, destination));
    }
  }, [activePage, location.search, navigate, pages, runtimeBasePath, tenantAuth.user]);

  useEffect(() => {
    const syncViewport = () => {
      const availableWidth = getRuntimeAvailableWidth();
      setRuntimeLayout({ availableWidth, ...getLiveArtboardProfile(availableWidth) });
    };
    syncViewport();
    window.addEventListener("resize", syncViewport);
    return () => window.removeEventListener("resize", syncViewport);
  }, []);

  const getElementStyle = (element) => getBuilderElementStyle({
      element,
      selected: { type: "", id: "" },
      carouselElementTypes,
      getElementPlacementMargins,
      getElementLayoutWidth,
      normalizeElementAlignSelf,
    });

  const setFormAnswer = (instanceKey, fieldId, value) => {
    setFormAnswers((prev) => ({
      ...prev,
      [instanceKey]: {
        ...(prev[instanceKey] || {}),
        [fieldId]: value,
      },
    }));
    setFormFieldErrors((prev) => ({
      ...prev,
      [instanceKey]: {
        ...(prev[instanceKey] || {}),
        [fieldId]: "",
      },
    }));
    setFormStatus((prev) => ({
      ...prev,
      [instanceKey]: {
        ...(prev[instanceKey] || {}),
        error: "",
        success: "",
      },
    }));
  };

  const getVisibleFieldsForInstance = (form, fields, instanceKey) => {
    const answers = formAnswers[instanceKey] || {};
    const rules = Array.isArray(form?.logicRules) ? form.logicRules : [];
    if (!rules.length) return fields;

    return fields.filter((field) => {
      const relatedRules = rules.filter((rule) => rule.targetFieldId === field.id);
      if (!relatedRules.length) return true;

      return relatedRules.reduce((visible, rule) => {
        const rawAnswer = normalizeRuntimeAnswerValue(answers[rule.sourceFieldId]);
        const matched = String(rawAnswer ?? "").trim() === String(rule.value ?? "").trim();
        if (rule.action === "show") return matched;
        if (rule.action === "hide") return matched ? false : visible;
        return visible;
      }, true);
    });
  };

  const buildSubmissionAnswers = (form, instanceKey) => {
    const enteredAnswers = formAnswers[instanceKey] || {};

    return getVisibleFieldsForInstance(form, getRuntimeFormFields(form), instanceKey).reduce((acc, field) => {
      const value = normalizeRuntimeAnswerValue(
        enteredAnswers[field.id] !== undefined ? enteredAnswers[field.id] : field.defaultValue
      );

      if (!isEmptyAnswer(value)) {
        acc[field.id] = value;
      }

      return acc;
    }, {});
  };

  const saveRuntimeFormForLater = async (form, instanceKey, formElementId = "") => {
    const formLang = formLanguages[instanceKey] || getDefaultFormLanguage(form, "en");
    const formCopy = getTenantRuntimeContent(formLang);
    const answers = buildSubmissionAnswers(form, instanceKey);
    const locallySaved = saveRuntimeFormDraft(
      getTenantBrandStorage(),
      cleanSubdomain,
      instanceKey,
      {
        formId: form.id,
        answers,
        pageIndex: formPages[instanceKey] || 0,
        language: formLang,
        resumeToken: formResumeTokens[instanceKey] || "",
      }
    );
    setFormStatus((prev) => ({
      ...prev,
      [instanceKey]: { submitting: true, error: "", success: "" },
    }));
    try {
      const savedDraft = await savePublicFormDraft(cleanSubdomain, form.id, {
        answers,
        form_element_id: formElementId,
        page_index: formPages[instanceKey] || 0,
        language: formLang,
        resume_token: formResumeTokens[instanceKey] || null,
        honeypot: formHoneypots[instanceKey] || "",
        submission_elapsed_ms: Math.min(
          86_400_000,
          Math.max(0, Date.now() - publicSubmissionStartedAtRef.current)
        ),
      });
      const resumeToken = savedDraft?.resumeToken || formResumeTokens[instanceKey] || "";
      setFormResumeTokens((current) => ({ ...current, [instanceKey]: resumeToken }));
      saveRuntimeFormDraft(getTenantBrandStorage(), cleanSubdomain, instanceKey, {
        formId: form.id,
        answers,
        pageIndex: formPages[instanceKey] || 0,
        language: formLang,
        draftId: savedDraft?.id,
        resumeToken,
      });
      setFormStatus((prev) => ({
        ...prev,
        [instanceKey]: { submitting: false, error: "", success: formCopy.runtime.resumeLaterSaved },
      }));
    } catch (error) {
      const guidance = getSubmissionErrorGuidance(error, getRuntimeFormFields(form), formCopy);
      const message = locallySaved
        ? `${guidance.message} Your progress is saved on this browser only.`
        : guidance.message;
      showFormToast("Could not save progress online", message);
      setFormStatus((prev) => ({
        ...prev,
        [instanceKey]: { submitting: false, error: message, success: "" },
      }));
    }
  };

  const getRuntimeValidationErrors = (form, fields, instanceKey) => {
    const enteredAnswers = formAnswers[instanceKey] || {};

    return getVisibleFieldsForInstance(form, fields || [], instanceKey).reduce((errors, field) => {
      const value = normalizeRuntimeAnswerValue(
        enteredAnswers[field.id] !== undefined ? enteredAnswers[field.id] : field.defaultValue
      );
      const error = getRuntimeFieldError(field, value);
      if (error) errors[field.id] = error;
      return errors;
    }, {});
  };

  const setRuntimeFormPage = (instanceKey, pageIndex, pageCount = 1) => {
    setFormPages((prev) => ({
      ...prev,
      [instanceKey]: Math.max(0, Math.min(pageIndex, Math.max(pageCount - 1, 0))),
    }));
    setFormStatus((prev) => ({
      ...prev,
      [instanceKey]: {
        ...(prev[instanceKey] || {}),
        error: "",
        success: "",
      },
    }));
    requestAnimationFrame(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  };

  const goToNextFormPage = (form, instanceKey, currentPage, currentPageIndex, pageCount) => {
    const fieldErrors = draftPreview
      ? {}
      : getRuntimeValidationErrors(form, currentPage?.fields || [], instanceKey);
    const firstInvalidFieldId = Object.keys(fieldErrors)[0];

    if (firstInvalidFieldId) {
      const message = fieldErrors[firstInvalidFieldId];
      setFormFieldErrors((prev) => ({ ...prev, [instanceKey]: fieldErrors }));
      showFormToast("Please check the form", message);
      setFormStatus((prev) => ({
        ...prev,
        [instanceKey]: {
          ...(prev[instanceKey] || {}),
          submitting: false,
          success: "",
          error: message,
        },
      }));
      focusRuntimeField(firstInvalidFieldId);
      return;
    }

    setCompletedFormPages((current) => ({
      ...current,
      [instanceKey]: addCompletedFormPage(current[instanceKey], currentPageIndex),
    }));
    setRuntimeFormPage(instanceKey, currentPageIndex + 1, pageCount);
  };

  const submitRuntimeForm = async (event, form, formElementId, instanceKey) => {
    event.preventDefault();

    const answers = buildSubmissionAnswers(form, instanceKey);
    const formLang = formLanguages[instanceKey] || getDefaultFormLanguage(form, "en");
    const formCopy = getTenantRuntimeContent(formLang);
    const fieldErrors = getRuntimeValidationErrors(form, getRuntimeFormFields(form), instanceKey);
    const firstInvalidFieldId = Object.keys(fieldErrors)[0];

    if (firstInvalidFieldId) {
      const message = fieldErrors[firstInvalidFieldId];
      const firstInvalidPage = getFormSections(form).findIndex((section) =>
        (section.fields || []).some((field) => field.id === firstInvalidFieldId)
      );
      setFormFieldErrors((prev) => ({ ...prev, [instanceKey]: fieldErrors }));
      if (firstInvalidPage >= 0) {
        setFormPages((prev) => ({ ...prev, [instanceKey]: firstInvalidPage }));
      }
      showFormToast("Please check the form", message);
      setFormStatus((prev) => ({
        ...prev,
        [instanceKey]: {
          submitting: false,
          success: "",
          error: message,
        },
      }));
      focusRuntimeField(firstInvalidFieldId);
      return;
    }

    setFormStatus((prev) => ({
      ...prev,
      [instanceKey]: { submitting: true, success: "", error: "" },
    }));

    const idempotencyKey = formIdempotencyKeysRef.current[instanceKey]
      || createFormIdempotencyKey();
    formIdempotencyKeysRef.current[instanceKey] = idempotencyKey;

    try {
      const activeAttempt = quizAttempts[instanceKey];
      const response = form.mode === "quiz"
        ? await finalizePublicQuizAttempt(cleanSubdomain, form.id, activeAttempt?.id, answers)
        : await submitPublicFormSubmission(cleanSubdomain, form.id, {
            answers,
            form_element_id: formElementId,
            resume_token: formResumeTokens[instanceKey] || null,
            honeypot: formHoneypots[instanceKey] || "",
            submission_elapsed_ms: Math.min(
              86_400_000,
              Math.max(0, Date.now() - publicSubmissionStartedAtRef.current)
            ),
          }, { idempotencyKey });

      delete formIdempotencyKeysRef.current[instanceKey];
      removeRuntimeFormDraft(getTenantBrandStorage(), cleanSubdomain, instanceKey);
      setFormResumeTokens((prev) => ({ ...prev, [instanceKey]: "" }));
      setFormAnswers((prev) => ({ ...prev, [instanceKey]: {} }));
      setFormFieldErrors((prev) => ({ ...prev, [instanceKey]: {} }));
      setFormHoneypots((prev) => ({ ...prev, [instanceKey]: "" }));
      setFormPages((prev) => ({ ...prev, [instanceKey]: 0 }));
      setCompletedFormPages((prev) => ({ ...prev, [instanceKey]: [] }));
      if (form.mode === "quiz") {
        setQuizAttempts((prev) => ({ ...prev, [instanceKey]: null }));
      }
      setFormStatus((prev) => ({
        ...prev,
        [instanceKey]: {
          submitting: false,
          error: "",
          success: response?.result?.score !== undefined && response?.result?.score !== null
            ? `Score: ${response.result.score}%`
            : getLocalizedValue(form, "successMessage", formLang) || formCopy.runtime.successMessage,
        },
      }));
    } catch (error) {
      if (error?.code === "idempotency_conflict") {
        delete formIdempotencyKeysRef.current[instanceKey];
      }
      const draftSaved = saveRuntimeFormDraft(
        getTenantBrandStorage(),
        cleanSubdomain,
        instanceKey,
        {
          formId: form.id,
          answers: formAnswers[instanceKey] || {},
          pageIndex: formPages[instanceKey] || 0,
          language: formLang,
        }
      );
      const guidance = getSubmissionErrorGuidance(error, getRuntimeFormFields(form), formCopy);
      const message = `${guidance.message} ${draftSaved
        ? "Your progress was saved in this browser."
        : "Keep this page open so you do not lose your answers."}`;
      if (guidance.firstFieldId) {
        const firstInvalidPage = getFormSections(form).findIndex((section) =>
          (section.fields || []).some((field) => field.id === guidance.firstFieldId)
        );
        setFormFieldErrors((prev) => ({
          ...prev,
          [instanceKey]: {
            ...(prev[instanceKey] || {}),
            ...guidance.fieldErrors,
          },
        }));
        if (firstInvalidPage >= 0) {
          setFormPages((prev) => ({ ...prev, [instanceKey]: firstInvalidPage }));
        }
        focusRuntimeField(guidance.firstFieldId);
      }
      showFormToast(guidance.title, message);
      setFormStatus((prev) => ({
        ...prev,
        [instanceKey]: {
          submitting: false,
          success: "",
          error: message,
        },
      }));
    }
  };

  const startRuntimeQuiz = async (form, instanceKey) => {
    const formLang = formLanguages[instanceKey] || getDefaultFormLanguage(form, "en");
    const formCopy = getTenantRuntimeContent(formLang);
    setFormStatus((prev) => ({ ...prev, [instanceKey]: { submitting: true, success: "", error: "" } }));
    try {
      const response = await startPublicQuizAttempt(cleanSubdomain, form.id, {
        honeypot: formHoneypots[instanceKey] || "",
        submission_elapsed_ms: Math.min(86_400_000, Math.max(0, Date.now() - publicSubmissionStartedAtRef.current)),
      });
      setQuizAttempts((prev) => ({ ...prev, [instanceKey]: response?.attempt || null }));
      setFormStatus((prev) => ({ ...prev, [instanceKey]: { submitting: false, success: "", error: "" } }));
    } catch (error) {
      const guidance = getSubmissionErrorGuidance(error, getRuntimeFormFields(form), formCopy);
      showFormToast(guidance.title, guidance.message);
      setFormStatus((prev) => ({
        ...prev,
        [instanceKey]: { submitting: false, success: "", error: guidance.message },
      }));
    }
  };

  const submitRuntimeReservation = async (
    element,
    values,
    idempotencyKey,
    honeypot = "",
    submissionElapsedMs = null
  ) => {
    const instanceKey = element.id || "reservation";
    const reservation = element.reservation || {};

    setReservationStatus((prev) => ({
      ...prev,
      [instanceKey]: { submitting: true, success: "", error: "" },
    }));

    if (draftPreview) {
      setReservationStatus((prev) => ({
        ...prev,
        [instanceKey]: {
          submitting: false,
          success: "Reservation request captured in preview.",
          error: "",
        },
      }));
      return true;
    }

    try {
      await submitPublicBuilderEvent(
        cleanSubdomain,
        {
          block_type: "reservationBlock",
          block_id: element.id,
          event_type: "builder.reservation_requested",
          title: "New reservation request",
          honeypot,
          ...(Number.isFinite(submissionElapsedMs)
            ? { submission_elapsed_ms: Math.min(86_400_000, Math.max(0, submissionElapsedMs)) }
            : {}),
          payload: {
            ...values,
            reservation_title: reservation.title || "",
            timezone:
              Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
          },
        },
        { idempotencyKey }
      );

      setReservationStatus((prev) => ({
        ...prev,
        [instanceKey]: {
          submitting: false,
          success: "Reservation request sent.",
          error: "",
        },
      }));
      return true;
    } catch (error) {
      setReservationStatus((prev) => ({
        ...prev,
        [instanceKey]: {
          submitting: false,
          success: "",
          error: getReservationErrorMessage(error),
        },
      }));
      return error?.code === "idempotency_conflict"
        ? "reset_idempotency"
        : false;
    }
  };

  const renderRuntimeField = (field, form, instanceKey, disabled, formLang = "en") => {
    const formCopy = getTenantRuntimeContent(formLang);
    const meta = getFieldType(field.type);
    const placeholder = field.showDetailsEditor === true
      ? getLocalizedValue(field, "placeholder", formLang) || getModernFieldPlaceholder(field, formCopy)
      : "";
    const currentValue = formAnswers[instanceKey]?.[field.id] ?? field.defaultValue ?? "";
    const baseId = `${instanceKey}_${field.id}`;
    const fieldDirection = getContentDirection(
      `${getLocalizedValue(field, "label", formLang)} ${getLocalizedValue(field, "helpText", formLang)} ${getRuntimeFieldOptions(field, formLang).join(" ")}`,
      getDirectionForLanguage(formLang)
    );

    if (field.type === "file") {
      const selectedFile = currentValue && typeof currentValue === "object" ? currentValue : null;
      const maxBytes = Number(field.maxFileSizeMb || 0) > 0 ? Number(field.maxFileSizeMb) * 1024 * 1024 : 0;
      return (
        <div className="runtime-file-upload">
          <input
            type="file"
            accept={field.accept || undefined}
            disabled={disabled}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file && maxBytes && file.size > maxBytes) {
                const message = formCopy.errors.fileTooLarge.replace("{size}", field.maxFileSizeMb);
                showFormToast("File is too large", message);
                setFormStatus((prev) => ({
                  ...prev,
                  [instanceKey]: {
                    ...(prev[instanceKey] || {}),
                    error: message,
                  },
                }));
                event.target.value = "";
                return;
              }
              setFormAnswer(instanceKey, field.id, file ? { name: file.name, size: file.size, type: file.type } : "");
            }}
          />
          {selectedFile && <small>{selectedFile.name}</small>}
          <p className="runtime-form-note">
            {formCopy.runtime.fileStorageNote}
          </p>
        </div>
      );
    }

    if (field.type === "dropdown" || field.type === "status" || field.type === "yesNo") {
      const options = field.type === "yesNo" ? [formCopy.runtime.yes, formCopy.runtime.no] : getRuntimeFieldOptions(field, formLang);
      return (
        <select
          dir={fieldDirection}
          value={currentValue}
          onChange={(event) => setFormAnswer(instanceKey, field.id, event.target.value)}
          disabled={disabled}
        >
          <option value="">{placeholder}</option>
          {options.map((option, optionIndex) => (
            <option key={`${option}_${optionIndex}`} value={option}>{option}</option>
          ))}
        </select>
      );
    }

    if (field.type === "radio") {
      return (
        <div className="runtime-choice-list">
          {getRuntimeFieldOptions(field, formLang).map((option, optionIndex) => {
            const optionId = `${baseId}_${optionIndex}`;

            return (
            <label
              className="runtime-choice"
              key={optionId}
              htmlFor={optionId}
              dir={getContentDirection(option, fieldDirection)}
            >
              <input
                id={optionId}
                type="radio"
                name={baseId}
                value={option}
                checked={isOptionAnswerChecked(currentValue, option, optionIndex)}
                onChange={(event) =>
                  setFormAnswer(instanceKey, field.id, {
                    value: event.target.value,
                    optionIndex,
                  })
                }
                disabled={disabled}
              />
              <span dir={getContentDirection(option, fieldDirection)}>{option}</span>
            </label>
            );
          })}
        </div>
      );
    }

    if (field.type === "checkboxes") {
      const selectedValues = Array.isArray(currentValue) ? currentValue : [];
      return (
        <div className="runtime-choice-list">
          {getRuntimeFieldOptions(field, formLang).map((option, optionIndex) => {
            const optionId = `${baseId}_${optionIndex}`;

            return (
            <label
              className="runtime-choice"
              key={optionId}
              htmlFor={optionId}
              dir={getContentDirection(option, fieldDirection)}
            >
              <input
                id={optionId}
                type="checkbox"
                value={option}
                checked={isCheckboxOptionChecked(selectedValues, option, optionIndex)}
                onChange={(event) => {
                  const nextValue = event.target.checked
                    ? [...selectedValues, { value: option, optionIndex }]
                    : selectedValues.filter((item) => {
                        if (item && typeof item === "object" && !Array.isArray(item)) {
                          return item.optionIndex !== optionIndex;
                        }

                        return item !== option;
                      });
                  setFormAnswer(instanceKey, field.id, nextValue);
                }}
                disabled={disabled}
              />
              <span dir={getContentDirection(option, fieldDirection)}>{option}</span>
            </label>
            );
          })}
        </div>
      );
    }

    if (field.type === "linearScale" || field.type === "rating") {
      const max = field.type === "rating" ? Number(field.maxRating || 5) : Number(field.scaleMax || 5);
      const min = field.type === "rating" ? 1 : Number(field.scaleMin || 1);
      const values = Array.from({ length: Math.max(1, max - min + 1) }, (_, index) => min + index);
      return (
        <div className="runtime-choice-list runtime-choice-inline">
          {values.map((value) => (
            <label className="runtime-choice" key={value} htmlFor={`${baseId}_${value}`}>
              <input
                id={`${baseId}_${value}`}
                type="radio"
                name={baseId}
                value={value}
                checked={String(currentValue) === String(value)}
                onChange={(event) => setFormAnswer(instanceKey, field.id, Number(event.target.value))}
                disabled={disabled}
              />
              <span>{value}</span>
            </label>
          ))}
        </div>
      );
    }

    if (meta.input === "textarea" || field.type === "paragraph") {
      return (
        <textarea
          dir={fieldDirection}
          placeholder={placeholder}
          value={currentValue}
          onChange={(event) => setFormAnswer(instanceKey, field.id, event.target.value)}
          disabled={disabled}
        />
      );
    }

    return (
      <input
        dir={fieldDirection}
        type={inputTypeForField(field.type)}
        placeholder={placeholder}
        value={currentValue}
        onChange={(event) => setFormAnswer(instanceKey, field.id, event.target.value)}
        disabled={disabled}
      />
    );
  };

  const renderConnectedForm = (formId, formElementId = "") => {
    const form = project?.forms?.find((item) => String(item.id) === String(formId || ""));
    if (!form) return <div className="empty-connected">{runtimeCopy.runtime.noFormSelected}</div>;

    const instanceKey = `${formElementId || "form"}_${form.id}`;
    const status = formStatus[instanceKey] || {};
    const isSubmitting = Boolean(status.submitting);
    const isQuiz = form.mode === "quiz";
    const quizAttempt = quizAttempts[instanceKey];
    const languageMode = normalizeLanguageMode(form.languageMode || form.localeMode || form.defaultLanguage || "en");
    const formLang = formLanguages[instanceKey] || getDefaultFormLanguage(form, "en");
    const formCopy = getTenantRuntimeContent(formLang);
    const formDir = getDirectionForLanguage(formLang);
    const formSections = getFormSections(form);
    const isPagedForm = formSections.length > 1;
    const currentPageIndex = Math.max(
      0,
      Math.min(Number(formPages[instanceKey] || 0), Math.max(formSections.length - 1, 0))
    );
    const currentPage = formSections[currentPageIndex];
    const validCompletedPages = (completedFormPages[instanceKey] || []).filter(
      (pageIndex) =>
        Object.keys(
          getRuntimeValidationErrors(
            form,
            formSections[pageIndex]?.fields || [],
            instanceKey,
          ),
        ).length === 0,
    );
    const pageNavigationItems = getFormPageNavigationItems(
      formSections.length,
      currentPageIndex,
      validCompletedPages,
    );
    const renderRuntimeFormPage = (section) => {
      const visibleFields = getVisibleFieldsForInstance(form, section.fields || [], instanceKey);
      return (
      <div className="runtime-form-section" key={section.id}>
        <div className="runtime-form-section-header">
          <h1 className="form-page-title" dir={section.titleStyle?.direction} style={{ ...(section.titleStyle || {}), textStyle: undefined }}>{getLocalizedValue(section, "title", formLang) || section.title}</h1>
          {(getLocalizedValue(section, "description", formLang) || section.description) && (
            <h2 className="form-page-description" dir={section.descriptionStyle?.direction} style={{ ...(section.descriptionStyle || {}), textStyle: undefined }}>{getLocalizedValue(section, "description", formLang) || section.description}</h2>
          )}
        </div>

        {visibleFields.map((field) => {
          const fieldError = formFieldErrors[instanceKey]?.[field.id] || "";
          const label = getLocalizedValue(field, "label", formLang) || field.label;
          const helpText = field.showDetailsEditor === true
            ? getLocalizedValue(field, "helpText", formLang) || field.helpText
            : "";
          const fieldDirection = getContentDirection(
            `${label || ""} ${helpText || ""} ${getRuntimeFieldOptions(field, formLang).join(" ")}`,
            formDir
          );

          return (
            <div
              className={`runtime-question ${fieldError ? "has-error" : ""}`}
              data-runtime-field-id={field.id}
              key={field.id}
            >
              <div
                className="runtime-question-field"
                dir={fieldDirection}
                aria-invalid={fieldError ? "true" : undefined}
              >
                <span className="runtime-question-title" dir={fieldDirection}>
                  {label}
                  {field.required && <span className="form-required-marker" aria-hidden="true"> *</span>}
                </span>
                {helpText && (
                  <small dir={getContentDirection(helpText, fieldDirection)}>
                    {helpText}
                  </small>
                )}
                {renderRuntimeField(field, form, instanceKey, isSubmitting, formLang)}
                {fieldError && <strong className="runtime-field-error" role="alert">{fieldError}</strong>}
              </div>
            </div>
          );
        })}
      </div>
      );
    };

    if (isQuiz && !quizAttempt) {
      return (
        <div className="runtime-form" dir={formDir}>
          <div className="quiz-start-panel">
            <strong>Ready to start?</strong>
            <p>Timing and scoring are enforced by the server. Focus detection is browser advisory.</p>
            {status.error && <p className="runtime-form-message runtime-form-error">{status.error}</p>}
            {status.success && <p className="runtime-form-message runtime-form-success">{status.success}</p>}
            <button type="button" className="runtime-submit" disabled={isSubmitting} onClick={() => startRuntimeQuiz(form, instanceKey)}>
              {isSubmitting ? formCopy.runtime.submitting : "Start quiz"}
            </button>
          </div>
        </div>
      );
    }

    return (
      <form
        className="runtime-form"
        dir={formDir}
        noValidate
        onSubmit={(event) => submitRuntimeForm(event, form, formElementId, instanceKey)}
      >
        <label className="runtime-honeypot" aria-hidden="true">
          Website
          <input
            type="text"
            name="website"
            value={formHoneypots[instanceKey] || ""}
            tabIndex={-1}
            autoComplete="off"
            onChange={(event) =>
              setFormHoneypots((prev) => ({
                ...prev,
                [instanceKey]: event.target.value,
              }))
            }
          />
        </label>
        <div className="runtime-form-header">
          {languageMode === "bilingual" && (
            <div className="runtime-language-switch" role="group" aria-label={formCopy.runtime.formLanguage}>
              <button type="button" className={formLang === "en" ? "active" : ""} onClick={() => setFormLanguages((prev) => ({ ...prev, [instanceKey]: "en" }))}>{formCopy.runtime.english}</button>
              <button type="button" className={formLang === "ar" ? "active" : ""} onClick={() => setFormLanguages((prev) => ({ ...prev, [instanceKey]: "ar" }))}>{formCopy.runtime.arabic}</button>
            </div>
          )}
          {isPagedForm && (
            <div className="runtime-form-progress" aria-label={formCopy.runtime.formProgress}>
              <span style={{ width: `${Math.round(((currentPageIndex + 1) / formSections.length) * 100)}%` }} />
            </div>
          )}
        </div>

        {isPagedForm ? (
          <>
            <div className="form-page-counter-title">
              {formCopy.runtime.pageCount
                .replace("{current}", currentPageIndex + 1)
                .replace("{total}", formSections.length)}
            </div>
            {currentPage ? renderRuntimeFormPage(currentPage) : null}
          </>
        ) : formSections.map((section) => renderRuntimeFormPage(section))}

        {status.error && <p className="runtime-form-message runtime-form-error">{status.error}</p>}
        {status.success && <p className="runtime-form-message runtime-form-success">{status.success}</p>}

        <div className="runtime-form-pagination">
          {isPagedForm ? (
            <button
              type="button"
              disabled={currentPageIndex === 0 || isSubmitting}
              onClick={() => setRuntimeFormPage(instanceKey, currentPageIndex - 1, formSections.length)}
            >
              {formCopy.runtime.previous}
            </button>
          ) : (
            <span />
          )}

<div className="runtime-form-page-navigation">
            <span className="runtime-form-page-count">
              {isPagedForm
                ? formCopy.runtime.pageCount
                    .replace("{current}", currentPageIndex + 1)
                    .replace("{total}", formSections.length)
                : ""}
            </span>
            {isPagedForm && (
              <div className="runtime-form-page-numbers" role="navigation" aria-label="Form pages">
                {pageNavigationItems.map((item) => (
                  <button
                    key={item.index}
                    type="button"
                    className={
                      "runtime-form-page-number" +
                      (item.isCurrent ? " is-current" : "") +
                      (item.isCompleted ? " is-completed" : "")
                    }
                    aria-current={item.isCurrent ? "page" : undefined}
                    aria-label={`Page ${item.index + 1}`}
                    disabled={item.isDisabled || isSubmitting}
                    onClick={() =>
                      setRuntimeFormPage(instanceKey, item.index, formSections.length)
                    }
                  >
                    {item.index + 1}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="runtime-form-actions">
            {!isQuiz && form.resumeLaterEnabled !== false && (
              <button
                type="button"
                className="runtime-resume-later"
                disabled={isSubmitting || draftPreview}
                onClick={() => saveRuntimeFormForLater(form, instanceKey, formElementId)}
              >
                {formCopy.runtime.resumeLater}
              </button>
            )}
            {isPagedForm && currentPageIndex < formSections.length - 1 ? (
              <button
                type="button"
                disabled={isSubmitting}
                onClick={() => goToNextFormPage(form, instanceKey, currentPage, currentPageIndex, formSections.length)}
              >
                {formCopy.runtime.next}
              </button>
            ) : (
              <button type="submit" className="runtime-submit" disabled={isSubmitting}>
                {isSubmitting ? formCopy.runtime.submitting : formCopy.runtime.submit}
              </button>
            )}
          </div>
        </div>
      </form>
    );
  };

  const renderRuntimeElementOverride = (element, { commonProps: props }) => {
    if (element.type === "loginBlock" || element.type === "registrationBlock") {
      const defaultRegistrationMode = element.type === "registrationBlock";
      const isRegistration = authPanelModes[element.id] ?? defaultRegistrationMode;
      const auth = element.auth || {};
      const useConfiguredCopy = isRegistration === defaultRegistrationMode;
      const switchAuthMode = () => {
        setAuthPanelModes((current) => ({ ...current, [element.id]: !isRegistration }));
        setTenantAuth((current) => ({ ...current, error: "", message: "" }));
      };

      if (tenantAuth.user) {
        return (
          <div key={element.id} {...props}>
            <div className="builder-auth-component tenant-auth-account">
              <div className="builder-auth-heading">
                <h3>Welcome, {tenantAuth.user.first_name || tenantAuth.user.email}</h3>
                <p>You are signed in to this website.</p>
              </div>

              <button type="button" className="runtime-submit" disabled={tenantAuth.loading} onClick={logOutTenantVisitor}>
                {tenantAuth.loading ? "Please wait…" : "Log out"}
              </button>
            </div>
          </div>
        );
      }

      return (
        <div key={element.id} {...props}>
          <form className="builder-auth-component" autoComplete="on" onSubmit={(event) => submitTenantAuth(event, isRegistration, element)}>
            <div className="builder-auth-heading">
              <h3>{(useConfiguredCopy && auth.title) || (isRegistration ? runtimeCopy.runtime.createAccount : runtimeCopy.runtime.login)}</h3>
              <p>{(useConfiguredCopy && auth.subtitle) || (isRegistration ? runtimeCopy.runtime.createAccountSubtitle : runtimeCopy.runtime.loginSubtitle)}</p>
            </div>
            {isRegistration && (
              <label>
                {runtimeCopy.runtime.fullName}
                <input type="text" name="fullName" autoComplete="name" required placeholder={runtimeCopy.runtime.yourName} />
              </label>
            )}
            <label>
              {runtimeCopy.runtime.emailAddress}
              <input type="email" name="email" autoComplete="email" required placeholder={runtimeCopy.runtime.emailPlaceholder} />
            </label>
            <label>
              {runtimeCopy.runtime.password}
              <input type="password" name="password" minLength={8} autoComplete={isRegistration ? "new-password" : "current-password"} required placeholder={runtimeCopy.runtime.passwordPlaceholder} />
            </label>
            {isRegistration && (
              <label>
                {runtimeCopy.runtime.confirmPassword}
                <input type="password" name="confirmPassword" minLength={8} autoComplete="new-password" required placeholder={runtimeCopy.runtime.confirmPasswordPlaceholder} />
              </label>
            )}
            {tenantAuth.error && <p className="runtime-form-error" role="alert">{tenantAuth.error}</p>}
            {tenantAuth.message && <p className="runtime-form-success" role="status">{tenantAuth.message}</p>}
            <button type="submit" className="runtime-submit" disabled={tenantAuth.loading || draftPreview}>
              {tenantAuth.loading ? "Please wait…" : (useConfiguredCopy && auth.buttonText) || (isRegistration ? runtimeCopy.runtime.createAccount : runtimeCopy.runtime.login)}
            </button>
            <p className="builder-auth-switch">
              {isRegistration ? "Already registered?" : "Don't have an account?"}{" "}
              <button type="button" onClick={switchAuthMode}>
                {isRegistration ? runtimeCopy.runtime.login : runtimeCopy.runtime.createAccount}
              </button>
            </p>
          </form>
        </div>
      );
    }
    if (element.type === "formBlock") return <div key={element.id} {...props}>{renderConnectedForm(element.connectedFormId, element.id)}</div>;
    if (element.type === "photoProofing") return <div key={element.id} {...props}><PhotoProofingBlock content={element.content} settings={element.proofing} /></div>;
    if (element.type === "reservationBlock") {
      const reservation = resolveReservationBlockValue(element, project?.pages) || {};
      const status = reservationStatus[element.id] || {};

      return (
        <div key={element.id} {...props}>
          <ReservationBlock
            title={reservation.title}
            description={reservation.description}
            services={reservation.services}
            fields={reservation.fields}
            formItems={reservation.formItems}
            bookingMode={reservation.bookingMode}
            availableDates={reservation.availableDates}
            timeSlots={reservation.timeSlots}
            timeSlotsByDate={reservation.timeSlotsByDate}
            submitLabel={reservation.submitLabel}
            disabled={Boolean(status.submitting)}
            onSubmit={(values, idempotencyKey, honeypot, submissionElapsedMs) =>
              submitRuntimeReservation(
                { ...element, reservation },
                values,
                idempotencyKey,
                honeypot,
                submissionElapsedMs
              )
            }
          />
          {status.error && <p className="runtime-form-message runtime-form-error">{status.error}</p>}
          {status.success && <p className="runtime-form-message runtime-form-success">{status.success}</p>}
        </div>
      );
    }
    if (element.type === "responsesTable") return null;

    return undefined;
  };

  const renderElement = createElementRenderer({
    carouselElementTypes,
    selected: { type: "", id: "" },
    preview: true,
    renderMode: "runtime",
    getFreeElementStyle: getElementStyle,
    getElementStyle,
    startDrag: () => {},
    findElementLocation: () => null,
    setInsertTarget: () => {},
    setSelected: () => {},
    captureCanvasTextSelection: () => {},
    shouldIgnoreInlineTextBlur: () => false,
    updateElementInlineText: () => {},
    runElementAction: runPublicButtonAction,
    renderConnectedForm,
    getReservationBlockValue: (element) => resolveReservationBlockValue(element, project?.pages),
    renderElementOverride: renderRuntimeElementOverride,
  });

  const selectCanvasPage = (pageId) => {
    const targetPage = pages.find((page) => String(page.id) === String(pageId));
    if (targetPage) navigate(getPageDestinationPath(targetPage));
  };

  const {
    renderSiteHeader: renderCanvasHeader,
    renderSiteFooter: renderCanvasFooter,
  } = createSiteChromeRenderers({
    project: project
      ? {
          ...project,
          // A legacy snapshot without chrome must not acquire Madar's factory
          // header/footer at public runtime. Absence is safer than a hybrid.
          siteChrome: project.siteChrome || { showHeader: false, showFooter: false },
        }
      : { pages: [], siteChrome: { showHeader: false, showFooter: false } },
    activePage,
    selected: { type: "", id: "" },
    preview: true,
    publicRuntime: true,
    selectPage: selectCanvasPage,
    setSelected: () => {},
  });

  const renderUnavailableState = (title, body, state = "unavailable") => (
    <main className="tenant-runtime-main">
      <section className={`tenant-runtime-card tenant-runtime-status-${state}`}>
        {state === "loading" && <span className="tenant-runtime-loader" aria-hidden="true" />}
        <h1>{title}</h1>
        <p>{body}</p>
        {state === "unavailable" && (
          <button type="button" className="tenant-runtime-retry" onClick={() => window.location.reload()}>
            Try again
          </button>
        )}
      </section>
    </main>
  );

  const renderLoadingState = () => {
    const resolvedBrand = publicSiteProfile
      ? {
          brand: brandName,
          logoUrl: publicSiteProfile.logo_url || site.logoUrl || "",
          loadingImageUrl: site.loadingImageUrl || "",
        }
      : publicSiteState === "ready"
        ? {
            brand: brandName,
            logoUrl: site.logoUrl || "",
            loadingImageUrl: site.loadingImageUrl || "",
          }
        : readCachedTenantBrand(getTenantBrandStorage(), publicationBoundary);
    const loadingBrand = resolvedBrand?.brand || getTenantBrandFallback(cleanSubdomain);
    const loadingLogoProps = getResponsiveMediaProps(getTenantLoadingLogoUrl({
      settingsLogoUrl: publicSiteProfile?.logo_url,
      logoUrl: resolvedBrand?.logoUrl,
      loadingImageUrl: resolvedBrand?.loadingImageUrl,
    }), {
      widths: [320, 480, 768, 1024, 1440],
      fallbackWidth: 1024,
      sizes: "(max-width: 720px) 70vw, 650px",
    });
    const loadingInitial = loadingBrand.trim().slice(0, 1).toUpperCase() || "M";

    return (
      <main className="tenant-runtime-main tenant-runtime-loading-screen" aria-busy="true">
        <div className="tenant-brand-loader" role="status" aria-live="polite">
          <div className="tenant-brand-loader-mark" aria-hidden="true">
            <span>{loadingInitial}</span>
            {loadingLogoProps.src && (
              <img
                {...loadingLogoProps}
                alt=""
                decoding="async"
                fetchPriority="high"
                loading="eager"
                onError={(event) => { event.currentTarget.hidden = true; }}
              />
            )}
          </div>
          <p className="tenant-brand-loader-name">{loadingBrand}</p>
          <span className="tenant-brand-loader-progress" aria-hidden="true" />
          <span className="sr-only">{runtimeCopy.runtime.loadingTitle}</span>
        </div>
      </main>
    );
  };

  const renderPublishedPage = () => {
    if (isPublicRuntime && (publicSiteState === "loading" || tenantAuth.loading)) {
      return renderLoadingState();
    }

    if (!project) {
      if (standaloneFormId) {
        return renderUnavailableState(
          "Form not found",
          "This saved form is unavailable. Check the form link and try again."
        );
      }

      return renderUnavailableState(
        runtimeCopy.runtime.noPublishedTitle,
        runtimeCopy.runtime.noPublishedBody
      );
    }

    if (standaloneFormId) {
      const publishedForm = project.forms?.find(
        (form) => String(form.id) === String(standaloneFormId)
      );

      if (!publishedForm) {
        return renderUnavailableState(
          "Form not found",
          "This saved form is unavailable. Check the form link and try again.",
          "not-found"
        );
      }

      return (
        <main className="tenant-runtime-page tenant-runtime-form-page" data-form-id={publishedForm.id}>
          {renderConnectedForm(publishedForm.id, "published-form-link")}
        </main>
      );
    }

    if (!activePage) {
      return renderUnavailableState(
        "Page not found",
        "This page is not part of the published website.",
        "not-found"
      );
    }

    const filterElement = (element) =>
      tenantAuth.user ||
      activePage?.id !== authEntryPage?.id ||
      authElementTypes.has(element.type);

    return (
      <main key={activePage.id} className="tenant-runtime-page" data-page-id={activePage.id}>
        <SiteRenderer
          project={project}
          activePage={activePage}
          viewportMode={runtimeViewport}
          presentationZoom={effectiveRuntimePresentationZoom}
          availablePresentationWidth={runtimeAvailableWidth}
          renderElement={renderElement}
          renderSiteHeader={renderCanvasHeader}
          renderSiteFooter={renderCanvasFooter}
          carouselElementTypes={carouselElementTypes}
          filterElement={filterElement}
          getDirectElementPosition={(element) => getRuntimeDirectPosition(element, runtimeViewport)}
          canvasStyle={{ "--site-runtime-logical-width": `${effectiveRuntimeLogicalWidth}px` }}
        />
      </main>
    );
  };

  // eslint-disable-next-line no-unused-vars
  const renderHeader = () => (
    <header className="tenant-site-header">
      <div className="tenant-site-header-inner">
        <Link className="tenant-site-brand" to={siteHomePath}>
          {resolveMediaUrl(site.logoUrl) ? (
            <img src={resolveMediaUrl(site.logoUrl)} alt={runtimeCopy.runtime.logoAlt.replace("{brand}", brandName)} />
          ) : (
            <span className="tenant-logo-fallback">
              {brandName.slice(0, 1).toUpperCase() || "M"}
            </span>
          )}

          <span>{brandName}</span>
        </Link>

        <nav className="tenant-site-nav">
          {getNavigablePages(pages, {
            excludePageIds: [
              findPageByNavigationReference(
                pages,
                site.headerButtonPageId || site.headerButtonHref || site.headerButtonLabel
              )?.id,
            ],
          }).map((page) => {
            const pagePath = getPublicPagePath(runtimeBasePath, page);

            return (
              <Link
                key={page.id}
                className={activePath.replace(/\/+$/, "") === pagePath.replace(/\/+$/, "") ? "active" : ""}
                to={getPageDestinationPath(page)}
                aria-current={activePath.replace(/\/+$/, "") === pagePath.replace(/\/+$/, "") ? "page" : undefined}
              >
                {getPageNavigationLabel(page)}
              </Link>
            );
          })}
        </nav>

        {findPageByNavigationReference(pages, site.headerButtonPageId || site.headerButtonHref || site.headerButtonLabel) ? (
          <Link
            className="tenant-site-cta"
            to={getPageDestinationPath(findPageByNavigationReference(pages, site.headerButtonPageId || site.headerButtonHref || site.headerButtonLabel))}
          >
            {site.headerButtonLabel || runtimeCopy.runtime.contact}
          </Link>
        ) : (
          <button type="button" className="tenant-site-cta" onClick={goToHeaderButton}>
            {site.headerButtonLabel || runtimeCopy.runtime.contact}
          </button>
        )}
      </div>
    </header>
  );

  // eslint-disable-next-line no-unused-vars
  const renderFooter = () => (
    <footer className="tenant-site-footer">
      <div className="tenant-footer-grid">
        <div className="tenant-footer-brand">
          <div className="tenant-footer-logo-row">
            {resolveMediaUrl(site.logoUrl) ? (
              <img
                className="tenant-footer-logo"
                src={resolveMediaUrl(site.logoUrl)}
                alt={runtimeCopy.runtime.logoAlt.replace("{brand}", footerBrand)}
              />
            ) : (
              <div className="tenant-footer-logo tenant-footer-logo-fallback">
                {footerInitial}
              </div>
            )}

            <h3>{footerBrand}</h3>
          </div>

          <p>
            {site.description ||
              runtimeCopy.runtime.defaultDescription}
          </p>

          <div className="tenant-social-row">
            {socialLinks.map((item) => {
              const href = getSafeFooterLinkUrl(item.url, item.label);
              return href ? (
                <a
                  href={href}
                  key={`${item.label}-${href}`}
                  aria-label={item.label}
                  target={isExternalFooterLink(href) ? "_blank" : undefined}
                  rel={isExternalFooterLink(href) ? "noopener noreferrer" : undefined}
                >
                  {item.label.slice(0, 2).toUpperCase()}
                </a>
              ) : (
                <span key={item.label} aria-label={item.label}>
                  {item.label.slice(0, 2).toUpperCase()}
                </span>
              );
            })}
          </div>
        </div>

        <div className="tenant-footer-column">
          <h4>{runtimeCopy.runtime.links}</h4>

          <div className="tenant-footer-links-grid">
            {footerLinks.map((item) => {
              const targetPage = resolveFooterPageLink(item);
              const normalizedItem = item.toLowerCase().trim();
              const targetPath = targetPage
                ? getPageDestinationPath(targetPage)
                : normalizedItem === "home" || isUnsupportedWorkspacePath(normalizedItem)
                  ? siteHomePath
                  : "";

              return targetPath ? (
                <Link key={item} to={targetPath}>{targetPage?.name || item}</Link>
              ) : (
                <button type="button" key={item} onClick={() => goToFooterLink(item)}>{item}</button>
              );
            })}
          </div>
        </div>

        <div className="tenant-footer-contact">
          <h4>{runtimeCopy.runtime.contact}</h4>

          <div className="tenant-language-pill">
            <span>{runtimeCopy.runtime.languageIcon}</span>
            <strong>{site.footerLanguageLabel || runtimeCopy.runtime.defaultLanguageLabel}</strong>
          </div>

          <p>{site.contactEmail || runtimeCopy.runtime.email}</p>
          <p dir="ltr">{site.phone || runtimeCopy.runtime.phone}</p>
          {paymentLinks.length > 0 && (
            <div className="tenant-payment-row">
              {paymentLinks.map((item) => {
                const href = getSafeFooterLinkUrl(item.url, item.label);
                return href ? (
                  <a
                    href={href}
                    key={`${item.label}-${href}`}
                    target={isExternalFooterLink(href) ? "_blank" : undefined}
                    rel={isExternalFooterLink(href) ? "noopener noreferrer" : undefined}
                  >
                    {item.label}
                  </a>
                ) : <span key={item.label}>{item.label}</span>;
              })}
            </div>
          )}
        </div>
      </div>

      <div className="tenant-footer-bottom">
        <p>
          {runtimeCopy.runtime.copyright} 2026 {footerBrand}. {site.rights || runtimeCopy.runtime.rights}
        </p>

        <a href={MADAR_ATTRIBUTION_URL}>
          {runtimeCopy.runtime.poweredBy}
        </a>
      </div>
    </footer>
  );

  const renderMainContent = () => {
    if (isUnsupportedWorkspaceRoute) {
      return null;
    }

    return renderPublishedPage();
  };

  return (
    <div
      className={`tenant-site-runtime ${draftPreview ? "tenant-site-draft-preview" : ""} ${standaloneFormId ? "tenant-site-standalone-form" : ""}`}
      style={getPageBuilderThemeVars(project?.theme)}
    >
      {draftPreview && (
        <div className="tenant-draft-preview-bar">
          <strong>{runtimeCopy.runtime.draftPreview}</strong>
          <Link to={`/page-builder/projects/${encodeURIComponent(projectId)}`}>
            {runtimeCopy.runtime.backToBuilder}
          </Link>
        </div>
      )}
      {renderMainContent()}
      {publicationUpdate && (
        <div className="tenant-publication-warning-backdrop">
          <section
            className="tenant-publication-warning"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="tenant-publication-warning-title"
          >
            <h2 id="tenant-publication-warning-title">Refresh to use the latest form</h2>
            <p>
              This form was updated while you had it open. Save any unfinished work,
              then refresh the page to load the new version.
            </p>
            <div className="tenant-publication-warning-actions">
              <button type="button" className="page-primary-action" onClick={() => window.location.reload()}>
                Refresh page
              </button>
              <button type="button" className="secondary-button" onClick={() => setPublicationUpdate(null)}>
                Keep working
              </button>
            </div>
          </section>
        </div>
      )}

      <RuntimeFormToast toast={formToast} onDismiss={dismissFormToast} />
      {publicActionMessage && (
        <div className="tenant-runtime-action-message" role="status" aria-live="polite">
          <span>{publicActionMessage}</span>
          <button type="button" onClick={() => setPublicActionMessage("")} aria-label="Dismiss message">×</button>
        </div>
      )}
    </div>
  );
}

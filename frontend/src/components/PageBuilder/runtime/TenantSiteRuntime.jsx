import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { defaultSiteChrome, fieldTypes, viewports } from "../core/PageBuilder.constants";
import {
  fetchPublicForm,
  fetchBuilderProject,
  fetchProtectedSitePage,
  fetchPublicSite,
  getTenantVisitorStatus,
  loginTenantVisitor,
  logoutTenantVisitor,
  registerTenantVisitor,
  submitPublicBuilderEvent,
  submitPublicFormSubmission,
} from "../services/PageBuilder.api";
import { createFormIdempotencyKey } from "./formSubmission";
import { getFormSections } from "../core/PageBuilder.factories";
import { getPageBuilderThemeVars } from "../core/PageBuilder.theme";
import {
  getContentDirection,
  getDefaultFormLanguage,
  getDirectionForLanguage,
  getLocalizedOptions,
  getLocalizedValue,
  normalizeLanguageMode,
} from "../core/PageBuilder.localization";
import "../../../styles/admin/PageBuilder/index.css";
import PageBuilderCarousel from "../ui/PageBuilderCarousel";
import AutoFitDirectText from "../core/PageBuilder.autoFitText";
import CountUpText from "../ui/CountUpText";
import ReservationBlock from "../blocks/ReservationBlock";
import { resolveReservationBlockValue } from "../core/PageBuilder.reservations";
import { resolveMediaUrl } from "../../../utils/media";
import { getTenantRuntimeContent } from "../../../content/pageBuilder";
import { getReservationErrorMessage } from "./reservationSubmission";
import {
  getDefaultPublicPage,
  getPublicPagePath,
  resolvePublicPageByPath,
} from "../core/PageBuilder.routing";
import {
  findPageByNavigationReference,
  getNavigablePages,
  getPageNavigationLabel,
} from "../core/PageBuilder.navigation";
import { normalizeElementAction, runPublicElementAction } from "../core/PageBuilder.actions";
import { getStoredUrlError } from "../core/PageBuilder.url";

const runtimeFallbackCopy = getTenantRuntimeContent("en");
const MADAR_ATTRIBUTION_URL = "https://madar.app/";

const splitLines = (value) =>
  String(value || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

const getListItems = (element) =>
  Array.isArray(element?.listItems) && element.listItems.length
    ? element.listItems
    : splitLines(element?.content);

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

const getRichTextRanges = (element, field, itemIndex = null) =>
  [
    ...(element?.richTextColors || []),
    ...(element?.richTextSizes || []),
    ...(element?.richTextStyles || []),
  ].filter((range) => range.field === field && (range.itemIndex ?? null) === itemIndex);

const renderRichText = (value, ranges = []) => {
  const text = String(value ?? "");
  const parts = [];
  let runStart = 0;
  let runColor = null;
  let runFontSize = null;
  let runFontWeight = null;
  let runFontStyle = null;
  let runTextDecoration = null;

  for (let index = 0; index <= text.length; index += 1) {
    const activeRanges =
      index < text.length
        ? [...ranges].reverse().filter((range) => index >= range.start && index < range.end)
        : [];
    const color = activeRanges.find((range) => range.color)?.color || null;
    const fontSize = activeRanges.find((range) => range.fontSize)?.fontSize || null;
    const fontWeight = activeRanges.find((range) => range.fontWeight)?.fontWeight || null;
    const fontStyle = activeRanges.find((range) => range.fontStyle)?.fontStyle || null;
    const textDecoration = activeRanges.find((range) => range.textDecoration)?.textDecoration || null;

    if (index === 0) {
      runColor = color;
      runFontSize = fontSize;
      runFontWeight = fontWeight;
      runFontStyle = fontStyle;
      runTextDecoration = textDecoration;
    }
    if (
      color === runColor &&
      fontSize === runFontSize &&
      fontWeight === runFontWeight &&
      fontStyle === runFontStyle &&
      textDecoration === runTextDecoration &&
      index < text.length
    ) continue;

    const content = text.slice(runStart, index);
    if (content) {
      const style = {
        ...(runColor ? { color: runColor } : {}),
        ...(runFontSize ? { fontSize: runFontSize } : {}),
        ...(runFontWeight ? { fontWeight: runFontWeight } : {}),
        ...(runFontStyle ? { fontStyle: runFontStyle } : {}),
        ...(runTextDecoration ? { textDecoration: runTextDecoration } : {}),
      };

      parts.push(
        Object.keys(style).length ? (
          <span style={style} key={`${runStart}_${runColor || ""}_${runFontSize || ""}_${runFontWeight || ""}_${runFontStyle || ""}_${runTextDecoration || ""}`}>{content}</span>
        ) : (
          content
        )
      );
    }
    runStart = index;
    runColor = color;
    runFontSize = fontSize;
    runFontWeight = fontWeight;
    runFontStyle = fontStyle;
    runTextDecoration = textDecoration;
  }

  return parts.length ? parts : text;
};

const carouselElementTypes = new Set(["card", "carousel", "carouselCards", "carouselSplit", "carouselSpotlight", "carouselStack", "carouselEditorial", "circularGallery"]);
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
      getPageAuthElements(page).some((element) => element.type === "loginBlock")
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

const getSubmissionErrorMessage = (error, copy = runtimeFallbackCopy) => {
  const detail = error?.data?.detail;
  const code = detail?.code || error?.code || "";

  if (code === "submission_rejected") {
    return "This submission could not be accepted. Review it and try again.";
  }

  if (typeof detail === "string") return detail;

  if (detail?.message === "Required field is missing") {
    return `${detail.field_label || copy.errors.requiredFallback} ${copy.errors.requiredSuffix}`;
  }

  if (detail?.message === "Submission contains unknown fields") {
    return copy.errors.unknownFields;
  }

  if (error?.status === 404) return copy.errors.unavailable;
  if (error?.status === 429) return copy.errors.tooMany;

  if (!navigator.onLine) return copy.errors.offline;

  return copy.errors.generic;
};

const normalizeElementAlignSelf = (value) => {
  if (!value || value === "auto") return undefined;
  if (value === "left") return "flex-start";
  if (value === "right") return "flex-end";
  return value;
};

const getElementLayoutWidth = (value, alignSelf = "auto") => {
  const placement = normalizeElementAlignSelf(alignSelf);

  if (placement === "stretch") return "100%";

  if (!value || value === "auto") return undefined;
  return value;
};

const getComponentPositionClass = (position) => {
  const normalized = normalizeElementAlignSelf(position);
  if (position === "Left" || normalized === "flex-start") return "justify-start";
  if (position === "Center" || normalized === "center") return "justify-center";
  if (position === "Right" || normalized === "flex-end") return "justify-end";
  return "justify-center";
};

const getCarouselWidthValue = (element) => {
  const width = element.styles?.width;
  if (!width || width === "auto") return "100%";
  return width;
};

const getElementPlacementMargins = (value) => {
  const placement = normalizeElementAlignSelf(value);

  if (placement === "center") {
    return { marginLeft: "auto", marginRight: "auto" };
  }

  if (placement === "flex-end") {
    return { marginLeft: "auto", marginRight: "0" };
  }

  if (placement === "flex-start") {
    return { marginLeft: "0", marginRight: "auto" };
  }

  return { marginLeft: undefined, marginRight: undefined };
};

const getCarouselVariant = (element) => {
  if (element.carouselVariant) return element.carouselVariant;
  if (element.type === "card") return "cards";
  if (element.type === "carouselCards") return "cards";
  if (element.type === "carouselSplit") return "split";
  if (element.type === "carouselSpotlight") return "spotlight";
  if (element.type === "carouselStack") return "stack";
  if (element.type === "carouselEditorial") return "editorial";
  if (element.type === "circularGallery") return "circular";
  return "lightswind";
};

const getRowCarouselElements = (row) =>
  (row.columns || []).flatMap((column) =>
    (column.elements || []).filter((element) => carouselElementTypes.has(element.type))
  );

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

const getScreenViewport = () => {
  if (typeof window === "undefined") return "desktop";
  if (window.innerWidth <= viewports.mobile) return "mobile";
  if (window.innerWidth <= viewports.tablet) return "tablet";
  return "desktop";
};

const getMetricItems = (element) => {
  if (Array.isArray(element?.metrics) && element.metrics.length) return element.metrics;
  const lines = String(element?.content || "").split("\n").map((line) => line.trim()).filter(Boolean);
  const items = [];
  for (let index = 0; index < lines.length; index += 2) {
    items.push({
      label: lines[index] || runtimeFallbackCopy.runtime.metricCountLabel.replace("{number}", items.length + 1),
      value: lines[index + 1] || runtimeFallbackCopy.runtime.metricFallbackValue,
    });
  }
  return items.length ? items : [{ label: runtimeFallbackCopy.runtime.metricLabel, value: runtimeFallbackCopy.runtime.metricFallbackValue }];
};

const getSectionCanvasHeight = (section, viewportName) =>
  Number(section?.layout?.minHeightByViewport?.[viewportName]) ||
  Number(section?.layout?.minHeight) ||
  560;

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
  const [runtimeViewport, setRuntimeViewport] = useState(getScreenViewport);
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
  const [publicSiteProfile, setPublicSiteProfile] = useState(null);
  const [publicSiteState, setPublicSiteState] = useState("loading");
  const [formAnswers, setFormAnswers] = useState({});
  const [formHoneypots, setFormHoneypots] = useState({});
  const [formStatus, setFormStatus] = useState({});
  const [reservationStatus, setReservationStatus] = useState({});
  const [formPages, setFormPages] = useState({});
  const [formLanguages, setFormLanguages] = useState({});
  const [authPanelModes, setAuthPanelModes] = useState({});
  const [publicActionMessage, setPublicActionMessage] = useState("");
  const [tenantAuth, setTenantAuth] = useState({ loading: !draftPreview, user: null, message: "", error: "" });
  const publicSubmissionStartedAtRef = useRef(Date.now());
  const formIdempotencyKeysRef = useRef({});
  const protectedPageRequestRef = useRef("");

  const loadProtectedPage = useCallback(async (pageReference) => {
    const cleanReference = String(pageReference || "").replace(/^\/+/, "");
    if (draftPreview || !cleanReference) return null;
    if (protectedPageRequestRef.current === cleanReference) return null;

    protectedPageRequestRef.current = cleanReference;
    try {
      const result = await fetchProtectedSitePage(cleanSubdomain, cleanReference);
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
  }, [cleanSubdomain, draftPreview]);

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
    setPublicSiteState("loading");

    const loadBackendPublicContent = async () => {
      try {
        const publicContent = standaloneFormId
          ? await fetchPublicForm(cleanSubdomain, standaloneFormId)
          : await fetchPublicSite(cleanSubdomain);

        if (cancelled) return;

        setPublicSiteProfile(publicContent?.site || null);

        if (standaloneFormId) {
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

        if (publishedProject && typeof publishedProject === "object") {
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
    () => getDefaultPublicPage(pages, project?.defaultPageId),
    [pages, project?.defaultPageId]
  );
  const requestedPage = useMemo(() => {
    return resolvePublicPageByPath(pages, pagePath, project?.defaultPageId);
  }, [pagePath, pages, project?.defaultPageId]);
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

  const pageLinks = splitLines(site.footerShopLinks || runtimeCopy.runtime.footerShopLinks);
  const helpLinks = splitLines(site.footerHelpLinks || runtimeCopy.runtime.footerHelpLinks);
  const socialLinks = splitLines(site.footerSocialLinks || runtimeCopy.runtime.footerSocialLinks);
  const footerLinks = [...pageLinks, ...helpLinks].filter((item) => {
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
      !tenantAuth.user ||
      requestedPage ||
      pagePath === "/"
    ) {
      return;
    }
    loadProtectedPage(pagePath).catch(() => undefined);
  }, [
    isPublicRuntime,
    loadProtectedPage,
    pagePath,
    publicSiteState,
    requestedPage,
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

  const getPublicButtonLink = (element) => {
    const action = normalizeElementAction(element?.action);

    if (action.type === "goToPage") {
      const targetPage = pages.find((page) => String(page?.id || "") === action.pageId);
      return targetPage ? { to: getPageDestinationPath(targetPage) } : null;
    }

    if (action.type === "openUrl" && !getStoredUrlError(action.url, {
      fieldName: "Button action URL",
      allowRelative: false,
      allowEmpty: false,
    })) {
      return {
        href: action.url,
        target: action.openInNewTab === false ? undefined : "_blank",
        rel: action.openInNewTab === false ? undefined : "noopener noreferrer",
      };
    }

    return null;
  };

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
  const activePageSections = getRuntimePageSections(activePage);

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
  }, [activePage, navigate, pages, runtimeBasePath, tenantAuth.user]);

  useEffect(() => {
    const syncViewport = () => setRuntimeViewport(getScreenViewport());
    syncViewport();
    window.addEventListener("resize", syncViewport);
    return () => window.removeEventListener("resize", syncViewport);
  }, []);

  const getElementStyle = (element, isFree = false, section = null) => {
    if (isFree) {
      const position = element.position?.[runtimeViewport] || element.position?.desktop || {};
      const viewportWidth = viewports[runtimeViewport] || viewports.desktop;
      const sectionHeight = getSectionCanvasHeight(section, runtimeViewport);
      const left = `${((Number(position.x) || 0) / viewportWidth) * 100}%`;
      const top = `${((Number(position.y) || 0) / sectionHeight) * 100}%`;
      const width = `${((Number(position.width) || 240) / viewportWidth) * 100}%`;
      const minHeight = `${((Number(position.height) || 80) / sectionHeight) * 100}%`;

      return {
        ...element.styles,
        "--builder-element-color": element.styles?.color || "inherit",
        "--builder-element-bg": element.styles?.backgroundColor || "transparent",
        "--builder-element-radius": element.styles?.borderRadius || "0",
        "--builder-element-font-size": element.styles?.fontSize || "inherit",
        "--builder-element-text-align": element.styles?.textAlign || "inherit",
        position: "absolute",
        left,
        top,
        width,
        minHeight,
        maxWidth: `calc(100% - ${left})`,
      };
    }
    const placementMargins = getElementPlacementMargins(element.styles?.alignSelf);
    const layoutWidth =
      getElementLayoutWidth(element.styles?.width, element.styles?.alignSelf) ||
      (carouselElementTypes.has(element.type) ? "100%" : undefined);

    return {
      ...element.styles,
      "--builder-element-width": layoutWidth || "auto",
      "--builder-element-align": normalizeElementAlignSelf(element.styles?.alignSelf) || "auto",
      "--builder-element-color": element.styles?.color || "inherit",
      "--builder-element-bg": element.styles?.backgroundColor || "transparent",
      "--builder-element-radius": element.styles?.borderRadius || "0",
      "--builder-element-font-size": element.styles?.fontSize || "inherit",
      "--builder-element-text-align": element.styles?.textAlign || "inherit",
      position: "relative",
      transform: undefined,
      width: layoutWidth,
      minHeight: element.styles?.minHeight || undefined,
      maxWidth: "100%",
      alignSelf: normalizeElementAlignSelf(element.styles?.alignSelf),
      ...placementMargins,
    };
  };

  const getDirectElementFrameStyle = (element, section) => {
    const position = element.position?.[runtimeViewport] || element.position?.desktop || {};
    const viewportWidth = viewports[runtimeViewport] || viewports.desktop;
    const sectionHeight = getSectionCanvasHeight(section, runtimeViewport);
    const left = `${((Number(position.x) || 0) / viewportWidth) * 100}%`;
    const top = `${((Number(position.y) || 0) / sectionHeight) * 100}%`;
    const width = `${((Number(position.width) || 240) / viewportWidth) * 100}%`;
    const height = `${((Number(position.height) || 80) / sectionHeight) * 100}%`;

    return {
      position: "absolute",
      left,
      top,
      width,
      height,
      maxWidth: `calc(100% - ${left})`,
    };
  };

  const setFormAnswer = (instanceKey, fieldId, value) => {
    setFormAnswers((prev) => ({
      ...prev,
      [instanceKey]: {
        ...(prev[instanceKey] || {}),
        [fieldId]: value,
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

  const getMissingFieldForSection = (form, section, instanceKey) => {
    const enteredAnswers = formAnswers[instanceKey] || {};

    return getVisibleFieldsForInstance(form, section?.fields || [], instanceKey).find((field) => {
      if (!field.required) return false;

      const value = normalizeRuntimeAnswerValue(
        enteredAnswers[field.id] !== undefined ? enteredAnswers[field.id] : field.defaultValue
      );

      return isEmptyAnswer(value);
    });
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
    const missingField = draftPreview
      ? null
      : getMissingFieldForSection(form, currentPage, instanceKey);

    if (missingField) {
      setFormStatus((prev) => ({
        ...prev,
        [instanceKey]: {
          ...(prev[instanceKey] || {}),
          submitting: false,
          success: "",
          error: `${getLocalizedValue(missingField, "label", formLanguages[instanceKey] || "en") || runtimeCopy.errors.requiredFallback} ${runtimeCopy.errors.requiredSuffix}`,
        },
      }));
      return;
    }

    setRuntimeFormPage(instanceKey, currentPageIndex + 1, pageCount);
  };

  const submitRuntimeForm = async (event, form, formElementId, instanceKey) => {
    event.preventDefault();

    const answers = buildSubmissionAnswers(form, instanceKey);
    const formLang = formLanguages[instanceKey] || getDefaultFormLanguage(form, "en");
    const formCopy = getTenantRuntimeContent(formLang);
    const missingField = getVisibleFieldsForInstance(form, getRuntimeFormFields(form), instanceKey).find(
      (field) => field.required && isEmptyAnswer(answers[field.id])
    );

    if (missingField) {
      setFormStatus((prev) => ({
        ...prev,
        [instanceKey]: {
          submitting: false,
          success: "",
          error: `${getLocalizedValue(missingField, "label", formLang) || formCopy.errors.requiredFallback} ${formCopy.errors.requiredSuffix}`,
        },
      }));
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
      await submitPublicFormSubmission(cleanSubdomain, form.id, {
        answers,
        form_element_id: formElementId,
        honeypot: formHoneypots[instanceKey] || "",
        submission_elapsed_ms: Math.min(
          86_400_000,
          Math.max(0, Date.now() - publicSubmissionStartedAtRef.current)
        ),
      }, { idempotencyKey });

      delete formIdempotencyKeysRef.current[instanceKey];
      setFormAnswers((prev) => ({ ...prev, [instanceKey]: {} }));
      setFormHoneypots((prev) => ({ ...prev, [instanceKey]: "" }));
      setFormPages((prev) => ({ ...prev, [instanceKey]: 0 }));
      setFormStatus((prev) => ({
        ...prev,
        [instanceKey]: {
          submitting: false,
          error: "",
          success: getLocalizedValue(form, "successMessage", formLang) || formCopy.runtime.successMessage,
        },
      }));
    } catch (error) {
      if (error?.code === "idempotency_conflict") {
        delete formIdempotencyKeysRef.current[instanceKey];
      }
      setFormStatus((prev) => ({
        ...prev,
        [instanceKey]: {
          submitting: false,
          success: "",
          error: getSubmissionErrorMessage(error, formCopy),
        },
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
                setFormStatus((prev) => ({
                  ...prev,
                  [instanceKey]: {
                    ...(prev[instanceKey] || {}),
                    error: formCopy.errors.fileTooLarge.replace("{size}", field.maxFileSizeMb),
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
          const label = getLocalizedValue(field, "label", formLang) || field.label;
          const helpText = field.showDetailsEditor === true
            ? getLocalizedValue(field, "helpText", formLang) || field.helpText
            : "";
          const fieldDirection = getContentDirection(
            `${label || ""} ${helpText || ""} ${getRuntimeFieldOptions(field, formLang).join(" ")}`,
            formDir
          );

          return (
            <div className="runtime-question" key={field.id}>
              <div className="runtime-question-field" dir={fieldDirection}>
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
              </div>
            </div>
          );
        })}
      </div>
      );
    };

    return (
      <form
        className="runtime-form"
        dir={formDir}
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

          <span className="runtime-form-page-count">
            {isPagedForm
              ? formCopy.runtime.pageCount
                  .replace("{current}", currentPageIndex + 1)
                  .replace("{total}", formSections.length)
              : ""}
          </span>

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
      </form>
    );
  };

  const renderElement = (element, isFree = false, section = null) => {
    const props = {
      className: `builder-element builder-element-${element.type}`,
      style: getElementStyle(element, isFree, section),
    };

    if (element.type === "heading") return <AutoFitDirectText as="h1" fitKey={`${element.content}:${element.styles?.fontSize || ""}:${element.styles?.lineHeight || ""}:${JSON.stringify(element.richTextSizes || [])}:${JSON.stringify(element.richTextStyles || [])}`} key={element.id} {...props}>{renderRichText(element.content, getRichTextRanges(element, "content"))}</AutoFitDirectText>;
    if (element.type === "text") return <AutoFitDirectText as="p" fitKey={`${element.content}:${element.styles?.fontSize || ""}:${element.styles?.lineHeight || ""}:${JSON.stringify(element.richTextSizes || [])}:${JSON.stringify(element.richTextStyles || [])}`} key={element.id} {...props}>{renderRichText(element.content, getRichTextRanges(element, "content"))}</AutoFitDirectText>;
    if (element.type === "button") {
      const link = getPublicButtonLink(element);
      const fitKey = `${element.content}:${element.styles?.fontSize || ""}:${JSON.stringify(element.richTextSizes || [])}:${JSON.stringify(element.richTextStyles || [])}`;
      const content = renderRichText(element.content, getRichTextRanges(element, "content"));

      if (link?.to) return <AutoFitDirectText as={Link} fitKey={fitKey} key={element.id} {...props} to={link.to}>{content}</AutoFitDirectText>;
      if (link?.href) return <AutoFitDirectText as="a" fitKey={fitKey} key={element.id} {...props} {...link}>{content}</AutoFitDirectText>;
      return <AutoFitDirectText as="button" fitKey={fitKey} key={element.id} type="button" {...props} onClick={() => runPublicButtonAction(element)}>{content}</AutoFitDirectText>;
    }
    if (element.type === "image") {
      const imageSrc = resolveMediaUrl(element.content);
      return imageSrc ? (
        <img key={element.id} {...props} src={imageSrc} alt={element.name || ""} />
      ) : null;
    }
    if (carouselElementTypes.has(element.type)) {
      const carouselWidth = getCarouselWidthValue(element);
      const carouselFrameStyle = {
        ...props.style,
        width: "100%",
        maxWidth: "100%",
        alignSelf: "stretch",
        marginLeft: undefined,
        marginRight: undefined,
        "--builder-element-width": "100%",
        "--builder-element-align": "stretch",
      };

      return (
        <div
          key={element.id}
          {...props}
          className={`${props.className} carousel-position-frame ${getComponentPositionClass(element.styles?.alignSelf)}`}
          style={carouselFrameStyle}
        >
          <div
            className="carousel-position-inner"
            style={{ width: carouselWidth, maxWidth: carouselWidth }}
          >
            <PageBuilderCarousel
              autoScroll={Boolean(element.autoScroll)}
              autoScrollMs={element.autoScrollMs}
              content={element.content}
              name={element.name}
              variant={getCarouselVariant(element)}
            />
          </div>
        </div>
      );
    }
    if (element.type === "list") {
      return (
        <div key={element.id} {...props} className={`${props.className} list-style-${element.listStyle || "disc"}`} style={{ ...props.style, "--list-count": Math.max(1, getListItems(element).length) }}>
          {element.listTitle && <h3 className="builder-list-title">{renderRichText(element.listTitle, getRichTextRanges(element, "listTitle"))}</h3>}
          <ul>
            {getListItems(element).map((item, index) => <li key={`${item}_${index}`} style={{ "--list-index": index }}>{renderRichText(item, getRichTextRanges(element, "listItem", index))}</li>)}
          </ul>
        </div>
      );
    }
    if (element.type === "divider") return <hr key={element.id} {...props} />;
    if (element.type === "embed") {
      return (
        <div key={element.id} {...props}>
          <strong>{runtimeCopy.runtime.embed}</strong>
          <a href={element.content} target="_blank" rel="noreferrer">{element.content}</a>
        </div>
      );
    }
    if (element.type === "metric") {
      const metrics = getMetricItems(element);
      const columns = Math.max(2, Math.min(4, Number(element.metricColumns) || 2));
      return (
        <div key={element.id} {...props} className={`${props.className} metric-group`} style={{ ...props.style, "--metric-columns": columns, "--metric-text-color": element.styles?.metricTextColor || "var(--theme-text)", "--metric-symbol-color": element.styles?.metricSymbolColor || "var(--theme-warning)" }}>
          {metrics.map((metric, index) => (
            <div className="metric-group-item" key={`${element.id}_${index}`}>
              <strong className="metric-value"><CountUpText value={metric.value} /></strong>
              <span className="metric-label">{metric.label}</span>
              {metric.description && <span className="metric-description">{metric.description}</span>}
            </div>
          ))}
        </div>
      );
    }
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
            bookingMode={reservation.bookingMode}
            availableDates={reservation.availableDates}
            timeSlots={reservation.timeSlots}
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

    return <div key={element.id} {...props}>{element.content}</div>;
  };

  const renderUnavailableState = (title, body, state = "unavailable") => (
    <main className="tenant-runtime-main">
      <section className={`tenant-runtime-card tenant-runtime-status-${state}`}>
        {state === "loading" && <span className="tenant-runtime-loader" aria-hidden="true" />}
        <p className="tenant-eyebrow">madarportal.com/site/{cleanSubdomain}</p>
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

  const renderPublishedPage = () => {
    if (isPublicRuntime && (publicSiteState === "loading" || tenantAuth.loading)) {
      return renderUnavailableState(
        runtimeCopy.runtime.loadingTitle,
        runtimeCopy.runtime.loadingBody,
        "loading"
      );
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

    return (
      <main key={activePage.id} className="tenant-runtime-page" data-page-id={activePage.id}>
        <div className={`builder-canvas viewport-${runtimeViewport}`}>
          {activePageSections.map((section) => {
            if (section.mode === "free" || section.mode === "direct") {
              return (
                <section
                  key={section.id}
                  className={`site-section direct-layout-section width-${section.layout.width}`}
                  style={{ backgroundColor: section.layout.background, minHeight: getSectionCanvasHeight(section, runtimeViewport) }}
                >
                  <div
                    className="direct-layout-frame"
                    style={{
                      width: `min(100%, ${viewports[runtimeViewport] || viewports.desktop}px)`,
                      minHeight: `${getSectionCanvasHeight(section, runtimeViewport)}px`,
                    }}
                  >
                    {(section.freeElements || [])
                      .filter((element) =>
                        tenantAuth.user ||
                        activePage?.id !== authEntryPage?.id ||
                        authElementTypes.has(element.type)
                      )
                      .map((element) => (
                      <div
                        key={element.id}
                        className={`direct-element-frame direct-element-frame-${element.type}`}
                        style={getDirectElementFrameStyle(element, section)}
                      >
                        <div className="direct-element-content">
                          {renderElement(element, false)}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              );
            }

            return (
              <section
                key={section.id}
                className={`site-section width-${section.layout.width} padding-${section.layout.paddingY}`}
                style={{ backgroundColor: section.layout.background }}
              >
                {(section.rows || []).map((row) => (
                  <div
                    key={row.id}
                    className={`site-row columns-${row.layout.columns} align-${row.layout.align} gap-${row.layout.gap}`}
                  >
                    {(row.columns || []).map((column) => (
                      <div
                        key={column.id}
                        className={`site-column column-align-${column.layout.align}`}
                      >
                        {(column.elements || [])
                          .filter((element) =>
                            tenantAuth.user ||
                            activePage?.id !== authEntryPage?.id ||
                            authElementTypes.has(element.type)
                          )
                          .filter((element) => !carouselElementTypes.has(element.type))
                          .map((element) => renderElement(element, false))}
                      </div>
                    ))}
                    {getRowCarouselElements(row).map((element) => renderElement(element, false))}
                  </div>
                ))}
              </section>
            );
          })}
        </div>
      </main>
    );
  };

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
            {socialLinks.map((item) => (
              <button type="button" key={item} aria-label={item}>
                {item.slice(0, 2).toUpperCase()}
              </button>
            ))}
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
      {!standaloneFormId &&
        (draftPreview || isPublicRuntime) &&
        site.showHeader !== false &&
        renderHeader()}
      {renderMainContent()}
      {publicActionMessage && (
        <div className="tenant-runtime-action-message" role="status" aria-live="polite">
          <span>{publicActionMessage}</span>
          <button type="button" onClick={() => setPublicActionMessage("")} aria-label="Dismiss message">×</button>
        </div>
      )}
      {!standaloneFormId &&
        (draftPreview || isPublicRuntime) &&
        site.showFooter !== false &&
        renderFooter()}
    </div>
  );
}

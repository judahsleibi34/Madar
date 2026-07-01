import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { STORAGE_KEY, defaultSiteChrome, fieldTypes, viewports } from "../core/PageBuilder.constants";
import { fetchPublicSite, submitPublicFormSubmission } from "../services/PageBuilder.api";
import { getFormSections } from "../core/PageBuilder.factories";
import { getPageBuilderThemeVars } from "../core/PageBuilder.theme";
import {
  getContentDirection,
  getDirectionForLanguage,
  getLocalizedOptions,
  getLocalizedValue,
  getRuntimeLanguage,
  normalizeLanguageMode,
} from "../core/PageBuilder.localization";
import "../../../styles/admin/PageBuilder/index.css";
import PageBuilderCarousel from "../ui/PageBuilderCarousel";
import CountUpText from "../ui/CountUpText";
import { resolveMediaUrl } from "../../../utils/media";
import { getTenantRuntimeContent } from "../../../content/pageBuilder";

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
  (element?.richTextColors || []).filter(
    (range) => range.field === field && (range.itemIndex ?? null) === itemIndex
  );

const renderRichText = (value, ranges = []) => {
  const text = String(value ?? "");
  const parts = [];
  let runStart = 0;
  let runColor = null;

  for (let index = 0; index <= text.length; index += 1) {
    const color = index < text.length
      ? [...ranges].reverse().find((range) => index >= range.start && index < range.end)?.color || null
      : null;
    if (index === 0) runColor = color;
    if (color === runColor && index < text.length) continue;
    const content = text.slice(runStart, index);
    if (content) parts.push(runColor ? <span style={{ color: runColor }} key={`${runStart}_${runColor}`}>{content}</span> : content);
    runStart = index;
    runColor = color;
  }

  return parts.length ? parts : text;
};

const carouselElementTypes = new Set(["card", "carousel", "carouselCards", "carouselSplit", "carouselSpotlight", "carouselStack", "carouselEditorial", "circularGallery"]);

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

const loadDraftPreviewProject = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

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

export default function TenantSiteRuntime({ draftPreview = false } = {}) {
  const params = useParams();
  const { subdomain = "my-site" } = params;
  const location = useLocation();
  const navigate = useNavigate();

  const cleanSubdomain = getCleanSubdomain(subdomain);
  const isPublicRuntime = !draftPreview;
  const [runtimeViewport, setRuntimeViewport] = useState(getScreenViewport);
  const [project, setProject] = useState(() => (draftPreview ? loadDraftPreviewProject() : null));
  const [publicSiteState, setPublicSiteState] = useState(() => (draftPreview ? "ready" : "loading"));
  const [formAnswers, setFormAnswers] = useState({});
  const [formStatus, setFormStatus] = useState({});
  const [formPages, setFormPages] = useState({});
  const [formLanguages, setFormLanguages] = useState({});

  useEffect(() => {
    if (draftPreview) {
      setProject(loadDraftPreviewProject());
      setPublicSiteState("ready");
      return;
    }

    let cancelled = false;
    setProject(null);
    setPublicSiteState("loading");

    const loadBackendPublishedSite = async () => {
      try {
        const publicSite = await fetchPublicSite(cleanSubdomain);
        const publishedProject = publicSite?.project?.published_schema;

        if (cancelled) return;

        if (publishedProject && typeof publishedProject === "object") {
          setProject(publishedProject);
          setPublicSiteState("ready");
          return;
        }

        setProject(null);
        setPublicSiteState("unavailable");
      } catch (error) {
        if (cancelled) return;
        setProject(null);
        setPublicSiteState("unavailable");
        console.warn("Could not load published site from backend:", error);
      }
    };

    loadBackendPublishedSite();

    return () => {
      cancelled = true;
    };
  }, [cleanSubdomain, draftPreview]);
  const site = {
    ...defaultSiteChrome,
    ...(project?.siteChrome || {}),
  };
  const runtimeLanguage =
    project?.language ||
    project?.lang ||
    site.language ||
    site.lang ||
    site.footerLanguageLabel;
  const runtimeDirection =
    String(runtimeLanguage || "").toLowerCase().startsWith("ar") ? "rtl" : "ltr";
  const runtimeCopy = getTenantRuntimeContent(runtimeDirection === "rtl" ? "ar" : "en");

  const pages = useMemo(
    () => (project?.pages || []),
    [project?.pages]
  );
  const activePath = location.pathname;
  const pagePath = `/${params["*"] || ""}`;
  const normalizedPagePath = pagePath === "/" ? "/" : pagePath.replace(/\/+$/, "");
  const hasBuilderPageForRoute = pages.some((page) => {
    const normalizedSlug = page.slug === "/" ? "/" : String(page.slug || "").replace(/\/+$/, "");
    return normalizedSlug === normalizedPagePath;
  });
  const isUnsupportedWorkspaceRoute =
    !hasBuilderPageForRoute &&
    (activePath.endsWith("/login") ||
      activePath.endsWith("/signup") ||
      activePath.endsWith("/forgot-password") ||
      activePath.endsWith("/dashboard"));

  const siteHomePath = `/site/${cleanSubdomain}`;

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

  const goToPage = (page) => {
    if (!page) {
      navigate(siteHomePath);
      return;
    }

    const slug = page.slug === "/" ? "" : page.slug;
    navigate(`/site/${cleanSubdomain}${slug}`);
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

    const normalizedTarget = targetValue.toLowerCase().replace(/^\//, "").trim();
    const targetPage = pages.find((page) => {
      const normalizedId = String(page.id || "").toLowerCase();
      const normalizedName = String(page.name || "").toLowerCase().trim();
      const normalizedSlug = String(page.slug || "").toLowerCase().replace(/^\//, "").trim();
      return normalizedId === normalizedTarget || normalizedName === normalizedTarget || normalizedSlug === normalizedTarget;
    });

    if (targetPage) {
      goToPage(targetPage);
    }
  };

  const activePage = useMemo(() => {
    const normalizedPath = pagePath === "/" ? "/" : pagePath.replace(/\/+$/, "");
    return (
      pages.find((page) => page.slug === normalizedPath) ||
      pages.find((page) => page.slug === "/" && normalizedPath === "/") ||
      pages[0]
    );
  }, [pagePath, pages]);

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
  };

  const goToNextFormPage = (form, instanceKey, currentPage, currentPageIndex, pageCount) => {
    const missingField = getMissingFieldForSection(form, currentPage, instanceKey);

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
    const formLang = formLanguages[instanceKey] || getRuntimeLanguage(form, runtimeDirection === "rtl" ? "ar" : "en");
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

    try {
      await submitPublicFormSubmission(cleanSubdomain, form.id, {
        answers,
        form_element_id: formElementId,
      });

      setFormAnswers((prev) => ({ ...prev, [instanceKey]: {} }));
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

  const renderRuntimeField = (field, form, instanceKey, disabled, formLang = "en") => {
    const formCopy = getTenantRuntimeContent(formLang);
    const meta = getFieldType(field.type);
    const placeholder = getLocalizedValue(field, "placeholder", formLang) || getModernFieldPlaceholder(field, formCopy);
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
    const form = project?.forms?.find((item) => item.id === formId) || project?.forms?.[0];
    if (!form) return <div className="empty-connected">{runtimeCopy.runtime.noFormSelected}</div>;

    const instanceKey = `${formElementId || "form"}_${form.id}`;
    const status = formStatus[instanceKey] || {};
    const isSubmitting = Boolean(status.submitting);
    const languageMode = normalizeLanguageMode(form.languageMode || form.localeMode || runtimeDirection);
    const formLang = formLanguages[instanceKey] || getRuntimeLanguage(form, runtimeDirection === "rtl" ? "ar" : "en");
    const formCopy = getTenantRuntimeContent(formLang);
    const formDir = getDirectionForLanguage(formLang);
    const formSections = getFormSections(form);
    const isPagedForm = (form.pageMode || "paged") === "paged" && formSections.length > 1;
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
          <h4>{getLocalizedValue(section, "title", formLang) || section.title}</h4>
          {(getLocalizedValue(section, "description", formLang) || section.description) && (
            <p>{getLocalizedValue(section, "description", formLang) || section.description}</p>
          )}
        </div>

        {visibleFields.map((field) => {
          const label = getLocalizedValue(field, "label", formLang) || field.label;
          const helpText = getLocalizedValue(field, "helpText", formLang) || field.helpText;
          const fieldDirection = getContentDirection(
            `${label || ""} ${helpText || ""} ${getRuntimeFieldOptions(field, formLang).join(" ")}`,
            formDir
          );

          return (
            <div className="runtime-question" key={field.id}>
              <div className="runtime-question-field" dir={fieldDirection}>
                <span className="runtime-question-title" dir={fieldDirection}>
                  {label}
                  {field.required ? " *" : ""}
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
        <div className="runtime-form-header">
          {languageMode === "bilingual" && (
            <div className="runtime-language-switch" role="group" aria-label={formCopy.runtime.formLanguage}>
              <button type="button" className={formLang === "en" ? "active" : ""} onClick={() => setFormLanguages((prev) => ({ ...prev, [instanceKey]: "en" }))}>{formCopy.runtime.english}</button>
              <button type="button" className={formLang === "ar" ? "active" : ""} onClick={() => setFormLanguages((prev) => ({ ...prev, [instanceKey]: "ar" }))}>{formCopy.runtime.arabic}</button>
            </div>
          )}
          <h3>{getLocalizedValue(form, "title", formLang) || form.title}</h3>
          <p>{getLocalizedValue(form, "description", formLang) || form.description}</p>
          {isPagedForm && (
            <div className="runtime-form-progress" aria-label={formCopy.runtime.formProgress}>
              <span style={{ width: `${Math.round(((currentPageIndex + 1) / formSections.length) * 100)}%` }} />
            </div>
          )}
        </div>

        {isPagedForm
          ? currentPage
            ? renderRuntimeFormPage(currentPage)
            : null
          : formSections.map((section) => renderRuntimeFormPage(section))}

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
                  ? formLang === "ar"
                    ? formCopy.runtime.pageCount
                        .replace("{current}", currentPageIndex + 1)
                        .replace("{total}", formSections.length)
                    : formCopy.runtime.pageCount
                        .replace("{current}", currentPageIndex + 1)
                        .replace("{total}", formSections.length)
                  : formCopy.runtime.sectionsCount.replace("{count}", formSections.length)}
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

    if (element.type === "heading") return <h1 key={element.id} {...props}>{renderRichText(element.content, getRichTextRanges(element, "content"))}</h1>;
    if (element.type === "text") return <p key={element.id} {...props}>{renderRichText(element.content, getRichTextRanges(element, "content"))}</p>;
    if (element.type === "button") return <button key={element.id} type="button" {...props}>{renderRichText(element.content, getRichTextRanges(element, "content"))}</button>;
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
      const isRegistration = element.type === "registrationBlock";
      const auth = element.auth || {};

      return (
        <div key={element.id} {...props}>
          <form className="builder-auth-component" onSubmit={(event) => event.preventDefault()}>
            <div className="builder-auth-heading">
              <h3>{auth.title || (isRegistration ? runtimeCopy.runtime.createAccount : runtimeCopy.runtime.login)}</h3>
              <p>{auth.subtitle || (isRegistration ? runtimeCopy.runtime.createAccountSubtitle : runtimeCopy.runtime.loginSubtitle)}</p>
            </div>
            {isRegistration && <label>{runtimeCopy.runtime.fullName}<input type="text" placeholder={runtimeCopy.runtime.yourName} /></label>}
            <label>{runtimeCopy.runtime.emailAddress}<input type="email" placeholder={runtimeCopy.runtime.emailPlaceholder} /></label>
            <label>{runtimeCopy.runtime.password}<input type="password" placeholder={runtimeCopy.runtime.passwordPlaceholder} /></label>
            {isRegistration && (
              <label>
                {runtimeCopy.runtime.confirmPassword}
                <input type="password" placeholder={runtimeCopy.runtime.confirmPasswordPlaceholder} />
              </label>
            )}
            <button type="submit" className="runtime-submit">
              {auth.buttonText || (isRegistration ? runtimeCopy.runtime.createAccount : runtimeCopy.runtime.login)}
            </button>
            <p className="builder-auth-switch">
              {auth.switchText} <strong>{auth.switchActionText}</strong>
            </p>
          </form>
        </div>
      );
    }
    if (element.type === "formBlock") return <div key={element.id} {...props}>{renderConnectedForm(element.connectedFormId, element.id)}</div>;
    if (element.type === "responsesTable") return null;

    return <div key={element.id} {...props}>{element.content}</div>;
  };

  const renderUnavailableState = (title, body) => (
    <main className="tenant-runtime-main">
      <section className="tenant-runtime-card">
        <p className="tenant-eyebrow">{cleanSubdomain}.madar.app</p>
        <h1>{title}</h1>
        <p>{body}</p>
      </section>
    </main>
  );

  const renderPublishedPage = () => {
    if (isPublicRuntime && publicSiteState === "loading") {
      return renderUnavailableState(
        runtimeCopy.runtime.loadingTitle,
        runtimeCopy.runtime.loadingBody
      );
    }

    if (!project || !activePage) {
      return renderUnavailableState(
        runtimeCopy.runtime.noPublishedTitle,
        runtimeCopy.runtime.noPublishedBody
      );
    }

    return (
      <main className="tenant-runtime-page">
        <div className={`builder-canvas viewport-${runtimeViewport}`}>
          {(activePage.sections || []).map((section) => {
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
                    {(section.freeElements || []).map((element) => renderElement(element, true, section))}
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
        <button
          type="button"
          className="tenant-site-brand"
          onClick={() => navigate(siteHomePath)}
        >
          {resolveMediaUrl(site.logoUrl) ? (
            <img src={resolveMediaUrl(site.logoUrl)} alt={runtimeCopy.runtime.logoAlt.replace("{brand}", brandName)} />
          ) : (
            <span className="tenant-logo-fallback">
              {brandName.slice(0, 1).toUpperCase() || "M"}
            </span>
          )}

          <span>{brandName}</span>
        </button>

        <nav className="tenant-site-nav">
          {pages.map((page) => {
            const pagePath =
              page.slug === "/"
                ? siteHomePath
                : `/site/${cleanSubdomain}${page.slug}`;

            return (
              <button
                type="button"
                key={page.id}
                className={activePath === pagePath ? "active" : ""}
                onClick={() => goToPage(page)}
              >
                {page.name}
              </button>
            );
          })}
        </nav>

        <button type="button" className="tenant-site-cta" onClick={goToHeaderButton}>
          {site.headerButtonLabel || runtimeCopy.runtime.contact}
        </button>
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
            {footerLinks.map((item) => (
              <button
                type="button"
                key={item}
                onClick={() => goToFooterLink(item)}
              >
                {resolveFooterPageLink(item)?.name || item}
              </button>
            ))}
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

        <button type="button" onClick={() => { window.location.href = MADAR_ATTRIBUTION_URL; }}>
          {runtimeCopy.runtime.poweredBy}
        </button>
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
      className={`tenant-site-runtime ${draftPreview ? "tenant-site-draft-preview" : ""}`}
      style={getPageBuilderThemeVars(project?.theme)}
    >
      {draftPreview && (
        <div className="tenant-draft-preview-bar">
          <strong>{runtimeCopy.runtime.draftPreview}</strong>
          <button type="button" onClick={() => navigate("/page-builder")}>
            {runtimeCopy.runtime.backToBuilder}
          </button>
        </div>
      )}
      {(draftPreview || publicSiteState === "ready") && renderHeader()}
      {renderMainContent()}
      {(draftPreview || publicSiteState === "ready") && renderFooter()}
    </div>
  );
}

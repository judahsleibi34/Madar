import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { STORAGE_KEY, defaultSiteChrome, fieldTypes, viewports } from "./PageBuilder.constants";
import { fetchPublicSite, submitPublicFormSubmission } from "./PageBuilder.api";
import { getFormSections } from "./PageBuilder.factories";
import "../../styles/admin/PageBuilder/index.css";
import PageBuilderCarousel from "./PageBuilderCarousel";
import CountUpText from "./CountUpText";
import { resolveMediaUrl } from "../../utils/media";

const splitLines = (value) =>
  String(value || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

const getListItems = (element) =>
  Array.isArray(element?.listItems) && element.listItems.length
    ? element.listItems
    : splitLines(element?.content);

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

const getFieldType = (type) => fieldTypes.find((item) => item.id === type) || fieldTypes[0];

const getModernFieldPlaceholder = (field = {}) => {
  const customPlaceholder = String(field.placeholder || "").trim();
  const genericPlaceholders = new Set([
    "",
    "Short answer",
    "Paragraph",
    "Email",
    "Phone number",
    "Website URL",
    "Number",
    "Money amount",
    "Date",
    "Time",
    "Dropdown",
    "Single choice",
    "Checkboxes",
    "Yes / No",
    "Linear scale",
    "Rating",
    "Status",
    "File upload",
  ]);

  if (!genericPlaceholders.has(customPlaceholder)) return customPlaceholder;

  const label = String(field.label || "").toLowerCase();

  if (field.type === "email" || label.includes("email")) return "name@company.com";
  if (field.type === "phone" || label.includes("phone")) return "+972 50 123 4567";
  if (field.type === "url" || label.includes("website")) return "https://yourcompany.com";
  if (field.type === "money" || label.includes("budget") || label.includes("amount")) return "Example: 7,500";
  if (field.type === "number" || label.includes("size")) return "Example: 12";
  if (field.type === "date") return "Select a date";
  if (field.type === "time") return "Select a time";
  if (field.type === "dropdown" || field.type === "status") return "Select an option";
  if (field.type === "radio") return "Choose one option";
  if (field.type === "checkboxes") return "Select all that apply";
  if (field.type === "paragraph" || label.includes("summary") || label.includes("details")) {
    return "Briefly describe what you need...";
  }
  if (label.includes("name")) return "e.g. Sarah Haddad";

  return "Type your answer";
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

const getSubmissionErrorMessage = (error) => {
  const detail = error?.data?.detail;

  if (typeof detail === "string") return detail;

  if (detail?.message === "Required field is missing") {
    return `${detail.field_label || "A required field"} is required.`;
  }

  if (detail?.message === "Submission contains unknown fields") {
    return "This form changed after the page loaded. Refresh and try again.";
  }

  if (error?.status === 404) return "This form is no longer available.";
  if (error?.status === 429) return "Too many submissions. Please wait and try again.";

  if (!navigator.onLine) return "Network connection lost. Please try again.";

  return "Could not submit the form. Please try again.";
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
    .replace(/^-+|-+$/g, "") || "my-site";

const loadPublishedProject = () => {
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
    items.push({ label: lines[index] || `Metric ${items.length + 1}`, value: lines[index + 1] || "0" });
  }
  return items.length ? items : [{ label: "Metric", value: "0" }];
};

const getSectionCanvasHeight = (section, viewportName) =>
  Number(section?.layout?.minHeightByViewport?.[viewportName]) ||
  Number(section?.layout?.minHeight) ||
  560;

export default function TenantSiteRuntime() {
  const params = useParams();
  const { subdomain = "my-site" } = params;
  const location = useLocation();
  const navigate = useNavigate();

  const cleanSubdomain = getCleanSubdomain(subdomain);
  const [runtimeViewport, setRuntimeViewport] = useState(getScreenViewport);
  const [project, setProject] = useState(() => loadPublishedProject());
  const [formAnswers, setFormAnswers] = useState({});
  const [formStatus, setFormStatus] = useState({});

  useEffect(() => {
    let cancelled = false;

    const loadBackendPublishedSite = async () => {
      try {
        const publicSite = await fetchPublicSite(cleanSubdomain);
        const publishedProject = publicSite?.project?.published_schema;

        if (!cancelled && publishedProject && typeof publishedProject === "object") {
          setProject(publishedProject);
        }
      } catch (error) {
        console.warn("Could not load published site from backend:", error);
      }
    };

    loadBackendPublishedSite();

    return () => {
      cancelled = true;
    };
  }, [cleanSubdomain]);
  const site = {
    ...defaultSiteChrome,
    ...(project?.siteChrome || {}),
  };

  const pages = useMemo(
    () => (project?.pages || []).filter((page) => !isUnsupportedWorkspacePath(page.slug)),
    [project?.pages]
  );
  const activePath = location.pathname;
  const isUnsupportedWorkspaceRoute =
    activePath.endsWith("/login") ||
    activePath.endsWith("/signup") ||
    activePath.endsWith("/forgot-password") ||
    activePath.endsWith("/dashboard");
  const pagePath = `/${params["*"] || ""}`;

  const siteHomePath = `/site/${cleanSubdomain}`;

  const pageLinks = splitLines(site.footerShopLinks || "Home\nSubmit Request\nReports");
  const helpLinks = splitLines(site.footerHelpLinks || "About Us\nPolicies\nContact");
  const socialLinks = splitLines(site.footerSocialLinks || "Facebook\nLinkedIn\nX\nInstagram");
  const footerLinks = [...pageLinks, ...helpLinks].filter(
    (item) => !isUnsupportedWorkspacePath(item)
  );

  useEffect(() => {
    if (isUnsupportedWorkspaceRoute) {
      navigate(siteHomePath, { replace: true });
    }
  }, [isUnsupportedWorkspaceRoute, navigate, siteHomePath]);

  const brandName = site.brand || "Madar";
  const footerBrand = site.footerStoreName || brandName;
  const footerInitial = footerBrand.trim().slice(0, 1).toUpperCase() || "M";

  const goToPage = (page) => {
    if (!page) {
      navigate(siteHomePath);
      return;
    }

    const slug = page.slug === "/" ? "" : page.slug;
    navigate(`/site/${cleanSubdomain}${slug}`);
  };

  const goToFooterLink = (label) => {
    const normalizedLabel = label.toLowerCase().trim();

    const target = pages.find((page) => {
      const normalizedName = String(page.name || "").toLowerCase().trim();
      const normalizedSlug = String(page.slug || "")
        .toLowerCase()
        .replace(/^\//, "");

      return (
        normalizedName === normalizedLabel ||
        normalizedSlug === normalizedLabel.replace(/\s+/g, "-")
      );
    });

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

  const buildSubmissionAnswers = (form, instanceKey) => {
    const enteredAnswers = formAnswers[instanceKey] || {};

    return getRuntimeFormFields(form).reduce((acc, field) => {
      const value = enteredAnswers[field.id] !== undefined ? enteredAnswers[field.id] : field.defaultValue;

      if (!isEmptyAnswer(value)) {
        acc[field.id] = value;
      }

      return acc;
    }, {});
  };

  const submitRuntimeForm = async (event, form, formElementId, instanceKey) => {
    event.preventDefault();

    const answers = buildSubmissionAnswers(form, instanceKey);
    const missingField = getRuntimeFormFields(form).find(
      (field) => field.required && isEmptyAnswer(answers[field.id])
    );

    if (missingField) {
      setFormStatus((prev) => ({
        ...prev,
        [instanceKey]: {
          submitting: false,
          success: "",
          error: `${missingField.label || "A required field"} is required.`,
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
      setFormStatus((prev) => ({
        ...prev,
        [instanceKey]: {
          submitting: false,
          error: "",
          success: form.successMessage || "Thank you. Your response has been submitted.",
        },
      }));
    } catch (error) {
      setFormStatus((prev) => ({
        ...prev,
        [instanceKey]: {
          submitting: false,
          success: "",
          error: getSubmissionErrorMessage(error),
        },
      }));
    }
  };

  const renderRuntimeField = (field, form, instanceKey, disabled) => {
    const meta = getFieldType(field.type);
    const placeholder = getModernFieldPlaceholder(field);
    const currentValue = formAnswers[instanceKey]?.[field.id] ?? field.defaultValue ?? "";
    const baseId = `${instanceKey}_${field.id}`;

    if (field.type === "file") {
      return <p className="runtime-form-note">File uploads are not supported yet.</p>;
    }

    if (field.type === "dropdown" || field.type === "status" || field.type === "yesNo") {
      const options = field.type === "yesNo" ? ["Yes", "No"] : field.options || [];
      return (
        <select
          value={currentValue}
          onChange={(event) => setFormAnswer(instanceKey, field.id, event.target.value)}
          disabled={disabled}
        >
          <option value="">{placeholder}</option>
          {options.map((option) => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
      );
    }

    if (field.type === "radio") {
      return (
        <div className="runtime-choice-list">
          {(field.options || []).map((option) => (
            <label className="runtime-choice" key={option} htmlFor={`${baseId}_${option}`}>
              <input
                id={`${baseId}_${option}`}
                type="radio"
                name={baseId}
                value={option}
                checked={currentValue === option}
                onChange={(event) => setFormAnswer(instanceKey, field.id, event.target.value)}
                disabled={disabled}
              />
              <span>{option}</span>
            </label>
          ))}
        </div>
      );
    }

    if (field.type === "checkboxes") {
      const selectedValues = Array.isArray(currentValue) ? currentValue : [];
      return (
        <div className="runtime-choice-list">
          {(field.options || []).map((option) => (
            <label className="runtime-choice" key={option} htmlFor={`${baseId}_${option}`}>
              <input
                id={`${baseId}_${option}`}
                type="checkbox"
                value={option}
                checked={selectedValues.includes(option)}
                onChange={(event) => {
                  const nextValue = event.target.checked
                    ? [...selectedValues, option]
                    : selectedValues.filter((item) => item !== option);
                  setFormAnswer(instanceKey, field.id, nextValue);
                }}
                disabled={disabled}
              />
              <span>{option}</span>
            </label>
          ))}
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
          placeholder={placeholder}
          value={currentValue}
          onChange={(event) => setFormAnswer(instanceKey, field.id, event.target.value)}
          disabled={disabled}
        />
      );
    }

    return (
      <input
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
    if (!form) return <div className="empty-connected">No form selected.</div>;

    const instanceKey = `${formElementId || "form"}_${form.id}`;
    const status = formStatus[instanceKey] || {};
    const isSubmitting = Boolean(status.submitting);

    return (
      <form className="runtime-form" onSubmit={(event) => submitRuntimeForm(event, form, formElementId, instanceKey)}>
        <div className="runtime-form-header">
          <h3>{form.title}</h3>
          <p>{form.description}</p>
        </div>

        {getFormSections(form).map((section) => (
          <div className="runtime-form-section" key={section.id}>
            <div className="runtime-form-section-header">
              <h4>{section.title}</h4>
              {section.description && <p>{section.description}</p>}
            </div>

            {(section.fields || []).map((field) => (
              <div className="runtime-question" key={field.id}>
                <div className="runtime-question-field">
                  <span>
                    {field.label}
                    {field.required ? " *" : ""}
                  </span>
                  {field.helpText && <small>{field.helpText}</small>}
                  {renderRuntimeField(field, form, instanceKey, isSubmitting)}
                </div>
              </div>
            ))}
          </div>
        ))}

        {status.error && <p className="runtime-form-message runtime-form-error">{status.error}</p>}
        {status.success && <p className="runtime-form-message runtime-form-success">{status.success}</p>}

        <button type="submit" className="runtime-submit" disabled={isSubmitting}>
          {isSubmitting ? "Submitting..." : "Submit"}
        </button>
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
          <strong>Embed</strong>
          <a href={element.content} target="_blank" rel="noreferrer">{element.content}</a>
        </div>
      );
    }
    if (element.type === "metric") {
      const metrics = getMetricItems(element);
      const columns = Math.max(2, Math.min(4, Number(element.metricColumns) || 2));
      return (
        <div key={element.id} {...props} className={`${props.className} metric-group`} style={{ ...props.style, "--metric-columns": columns, "--metric-text-color": element.styles?.metricTextColor || "#172b4d", "--metric-symbol-color": element.styles?.metricSymbolColor || "#f1f66b" }}>
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
              <h3>{auth.title || (isRegistration ? "Create account" : "Log in")}</h3>
              <p>{auth.subtitle || (isRegistration ? "Create your account." : "Access your account.")}</p>
            </div>
            {isRegistration && <label>Full name<input type="text" placeholder="Your name" /></label>}
            <label>Email address<input type="email" placeholder="name@example.com" /></label>
            <label>Password<input type="password" placeholder="Enter password" /></label>
            <button type="submit" className="runtime-submit">
              {auth.buttonText || (isRegistration ? "Create account" : "Log in")}
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

  const renderPublishedPage = () => {
    if (!project || !activePage) {
      return (
        <main className="tenant-runtime-main">
          <section className="tenant-runtime-card">
            <p className="tenant-eyebrow">{cleanSubdomain}.madar.app</p>
            <h1>No published site found</h1>
            <p>Save the project in Page Builder, then use Go Live again.</p>
          </section>
        </main>
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
            <img src={resolveMediaUrl(site.logoUrl)} alt={`${brandName} logo`} />
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
                alt={`${footerBrand} logo`}
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
              "An adaptive business management platform for creating and managing digital systems."}
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
          <h4>Links</h4>

          <div className="tenant-footer-links-grid">
            {footerLinks.map((item) => (
              <button
                type="button"
                key={item}
                onClick={() => goToFooterLink(item)}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        <div className="tenant-footer-contact">
          <h4>Contact</h4>

          <div className="tenant-language-pill">
            <span>◎</span>
            <strong>{site.footerLanguageLabel || "AR"}</strong>
          </div>

          <p>{site.contactEmail || "info@madar.com"}</p>
          <p dir="ltr">{site.phone || "+972599203857"}</p>
        </div>
      </div>

      <div className="tenant-footer-bottom">
        <p>
          © 2026 {footerBrand}. {site.rights || "All rights reserved."}
        </p>

        <button type="button" onClick={() => navigate("/")}>
          Powered by Madar
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
    <div className="tenant-site-runtime">
      {renderHeader()}
      {renderMainContent()}
      {renderFooter()}
    </div>
  );
}

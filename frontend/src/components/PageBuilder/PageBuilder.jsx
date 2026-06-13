import { useEffect, useMemo, useState } from "react";
import "../../styles/admin/PageBuilder/index.css";
import {
  STORAGE_KEY,
  viewports,
  builderTabs,
  designPanels,
  sectionWidths,
  spacingOptions,
  columnOptions,
  alignmentOptions,
  elementTypes,
  fieldTypes,
  workflowStepTypes,
  permissionGroups,
  defaultSiteChrome,
  starterSystems,
} from "./PageBuilder.constants";

import {
  createId,
} from "./PageBuilder.constants";

import {
  createField,
  createForm,
  getFormSections,
  getFormFields,
  createElement,
  createColumn,
  createRow,
  createSection,
  createPage,
  createRole,
  createUser,
  createWorkflow,
  cloneWithNewIds,
  createPosition,
} from "./PageBuilder.factories";

import {
  heroSection,
  formSection,
  responsesSection,
  sectionLibrary,
  buildStarterProject,
  createInitialProject,
} from "./PageBuilder.starters";
import BuilderResponsesPage from "./BuilderResponsesPage";
import DataAnalysisWorkspace from "./DataAnalysisWorkspace";
import { sanitizeSubdomain } from "./PageBuilder.routing";
import PageBuilderCarousel from "./PageBuilderCarousel";
import PageBuilderTopbar from "./PageBuilderTopbar";
import PageBuilderSubbar from "./PageBuilderSubbar";
import PageBuilderThemeTab from "./PageBuilderThemeTab";
import PageBuilderPublishTab from "./PageBuilderPublishTab";
import PageBuilderUsersTab from "./PageBuilderUsersTab";
import PageBuilderWorkflowsTab from "./PageBuilderWorkflowsTab";
import {
  createBuilderProject,
  fetchBuilderProject,
  fetchWebsiteSettings,
  listBuilderProjects,
  publishBuilderProject,
  updateBuilderProject,
} from "./PageBuilder.api";

import {
  applyThemeModeToProject,
  getPageBuilderThemeClassName,
  getPageBuilderThemeVars,
} from "./PageBuilder.theme";

const splitLines = (value) =>
  String(value || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

const carouselElementTypes = new Set(["carousel", "carouselCards", "carouselSplit", "circularGallery"]);
const blockedStoredUrlSchemes = new Set(["javascript", "data", "vbscript", "file", "ftp"]);
const urlLikeSiteChromeKeys = new Set(["href", "image", "imageUrl", "logoUrl", "madarLink", "src", "url"]);
const controlCharacterPattern = /[\u0000-\u001f\u007f]/;
const urlSchemePattern = /^([a-z][a-z0-9+.-]*):/i;
const assetUploadUnavailableMessage =
  "Asset uploads are not available yet. Use an HTTPS image URL or managed internal path.";

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

const getElementAlignControlValue = (value) =>
  normalizeElementAlignSelf(value) || "auto";

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

const isDirectionalElementPlacement = (value) =>
  ["flex-start", "center", "flex-end", "left", "right"].includes(value);

const getClosestColumnIdFromEvent = (event) => {
  const columns = Array.from(event.currentTarget.querySelectorAll("[data-column-id]"));
  if (columns.length === 0) return "";

  const point = { x: event.clientX, y: event.clientY };
  let closest = { id: "", distance: Number.POSITIVE_INFINITY };

  columns.forEach((column) => {
    const rect = column.getBoundingClientRect();
    const center = {
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2,
    };
    const distance = Math.hypot(point.x - center.x, point.y - center.y);

    if (distance < closest.distance) {
      closest = { id: column.dataset.columnId || "", distance };
    }
  });

  return closest.id;
};

const getCarouselVariant = (element) => {
  if (element.carouselVariant) return element.carouselVariant;
  if (element.type === "carouselCards") return "cards";
  if (element.type === "carouselSplit") return "split";
  if (element.type === "circularGallery") return "circular";
  return "lightswind";
};

const getRowCarouselElements = (row) =>
  (row.columns || []).flatMap((column) =>
    (column.elements || []).filter((element) => carouselElementTypes.has(element.type))
  );

const getFieldType = (type) => fieldTypes.find((item) => item.id === type) || fieldTypes[0];
const singleAnswerQuizTypes = new Set(["dropdown", "radio", "status", "yesNo", "linearScale", "rating"]);
const textAnswerQuizTypes = new Set(["shortText", "paragraph", "email", "phone", "url", "number", "money"]);
const correctableQuizTypes = new Set([...singleAnswerQuizTypes, "checkboxes", ...textAnswerQuizTypes]);

const normalizeQuizAnswer = (value) => String(value ?? "").trim().toLowerCase();

const hasQuizAnswerKey = (field = {}) => {
  if (!correctableQuizTypes.has(field.type)) return false;
  if (field.type === "checkboxes") return Array.isArray(field.quizCorrectAnswer) && field.quizCorrectAnswer.length > 0;
  if (textAnswerQuizTypes.has(field.type)) {
    return Array.isArray(field.quizCorrectAnswer)
      ? field.quizCorrectAnswer.some((answer) => String(answer || "").trim())
      : Boolean(String(field.quizCorrectAnswer || "").trim());
  }
  return Boolean(String(field.quizCorrectAnswer || "").trim());
};

const isQuizAnswerCorrect = (field = {}, answer) => {
  if (!hasQuizAnswerKey(field)) return null;

  if (field.type === "checkboxes") {
    const expected = Array.isArray(field.quizCorrectAnswer) ? field.quizCorrectAnswer.map(normalizeQuizAnswer).sort() : [];
    const received = Array.isArray(answer) ? answer.map(normalizeQuizAnswer).sort() : [];
    return expected.length === received.length && expected.every((item, index) => item === received[index]);
  }

  if (textAnswerQuizTypes.has(field.type)) {
    const expectedAnswers = Array.isArray(field.quizCorrectAnswer)
      ? field.quizCorrectAnswer
      : splitLines(field.quizCorrectAnswer);
    const received = normalizeQuizAnswer(answer);
    return expectedAnswers.map(normalizeQuizAnswer).includes(received);
  }

  return normalizeQuizAnswer(field.quizCorrectAnswer) === normalizeQuizAnswer(answer);
};

const gradeQuizResponse = (form = {}, answers = {}) => {
  const settings = getQuizSettings(form);
  const fields = getFormFields(form);

  if (settings.scoring === "completion") {
    const answered = fields.filter((field) => {
      const value = answers[field.id];
      return value !== undefined && value !== null && value !== "" && (!Array.isArray(value) || value.length > 0);
    }).length;
    const score = fields.length ? Math.round((answered / fields.length) * 100) : 0;
    return {
      mode: "completion",
      correct: answered,
      total: fields.length,
      score,
      passed: score >= Number(settings.passingScore || 0),
      passingScore: Number(settings.passingScore || 0),
    };
  }

  if (settings.scoring === "manual") {
    return {
      mode: "manual",
      correct: 0,
      total: 0,
      score: null,
      passed: null,
      passingScore: Number(settings.passingScore || 0),
    };
  }

  const keyedFields = fields.filter(hasQuizAnswerKey);
  const correct = keyedFields.filter((field) => isQuizAnswerCorrect(field, answers[field.id])).length;
  const score = keyedFields.length ? Math.round((correct / keyedFields.length) * 100) : null;

  return {
    mode: "automatic",
    correct,
    total: keyedFields.length,
    score,
    passed: score === null ? null : score >= Number(settings.passingScore || 0),
    passingScore: Number(settings.passingScore || 0),
  };
};

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
const getFieldOptions = (field) => (field.options || []).filter(Boolean);
const scaleRange = (field) => {
  const min = Number(field.scaleMin || 1);
  const max = Math.max(min, Number(field.scaleMax || 5));
  return Array.from({ length: max - min + 1 }, (_, index) => String(min + index));
};

const formatQuizTime = (seconds = 0) => {
  const safeSeconds = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(safeSeconds / 60);
  const remainder = safeSeconds % 60;
  return `${minutes}:${String(remainder).padStart(2, "0")}`;
};

const getQuizSettings = (form = {}) => ({
  lockScreen: false,
  totalTimeLimitSec: 0,
  questionTimeLimitSec: 0,
  showQuestionTimer: true,
  showTotalTimer: true,
  scoring: "automatic",
  passingScore: 70,
  showResults: true,
  allowRetakes: true,
  maxRetakes: 0,
  ...(form.quiz || {}),
});

const mainBuilderHiddenTabs = ["data", "responses"];
const builderWorkspaceCopy = {
  en: {
    projectNames: {
      "Madar Builder Demo": "Madar Builder Demo",
    },
    topbar: {
      templates: "Templates",
      preview: "Preview",
      exitPreview: "Exit Preview",
      save: "Save",
      goLive: "Go Live",
    },
    tabs: {
      design: {
        label: "Pages",
        helper: "Design screens, sections, layout, and visual elements.",
      },
      forms: {
        label: "Forms",
        helper: "Create forms and place them on pages.",
      },
      users: {
        label: "Users",
        helper: "Manage team members, roles, and permissions.",
      },
      theme: {
        label: "Theme",
        helper: "Control global colors, typography, spacing, and radius.",
      },
      publish: {
        label: "Publish",
        helper: "Preview, save locally, export JSON, and publish status.",
      },
      responses: {
        label: "Responses",
        helper: "Review submitted form answers.",
      },
      data: {
        label: "Data",
        helper: "Review, clean, and analyze your collected data.",
      },
    },
  },
  ar: {
    projectNames: {
      "Madar Builder Demo": "عرض منشئ مدار",
    },
    topbar: {
      templates: "القوالب",
      preview: "معاينة",
      exitPreview: "إنهاء المعاينة",
      save: "حفظ",
      goLive: "نشر",
    },
    tabs: {
      design: {
        label: "الصفحات",
        helper: "صمم الشاشات والأقسام والتخطيط والعناصر المرئية.",
      },
      forms: {
        label: "النماذج",
        helper: "أنشئ النماذج وضعها داخل الصفحات.",
      },
      users: {
        label: "المستخدمون",
        helper: "أدر أعضاء الفريق والأدوار والصلاحيات.",
      },
      theme: {
        label: "الثيم",
        helper: "تحكم في الألوان والخطوط والمسافات والزوايا.",
      },
      publish: {
        label: "النشر",
        helper: "عاين واحفظ وصدّر JSON وانشر الحالة.",
      },
      responses: {
        label: "الردود",
        helper: "راجع إجابات النماذج المرسلة.",
      },
      data: {
        label: "البيانات",
        helper: "راجع ونظف وحلل البيانات التي تم جمعها.",
      },
    },
  },
};
const mobileBlockerCopy = {
  en: {
    design: {
      title: "Desktop builder only",
      message:
        "The page builder is designed for tablet and desktop editing. Use a wider screen to build layouts, forms, workflows, and themes comfortably.",
    },
    data: {
      title: "Data workspace needs more room",
      message:
        "Data review, cleaning, and reporting are designed for tablet and desktop screens. Use a wider screen to inspect tables and generate reports comfortably.",
    },
    responses: {
      title: "Submissions are easier on a wider screen",
      message:
        "Response review is designed for tablet and desktop screens. Use a wider screen to scan submissions, compare answers, and export data comfortably.",
    },
    default: {
      title: "Desktop workspace only",
      message:
        "This workspace is designed for tablet and desktop screens. Use a wider screen for the best editing experience.",
    },
  },
  ar: {
    design: {
      title: "المنشئ مخصص للشاشات الكبيرة",
      message:
        "منشئ الصفحات مصمم للتحرير على الأجهزة اللوحية وشاشات سطح المكتب. استخدم شاشة أوسع لبناء الصفحات والنماذج وسير العمل والثيمات بسهولة.",
    },
    data: {
      title: "مساحة البيانات تحتاج شاشة أوسع",
      message:
        "مراجعة البيانات وتنظيفها وإنشاء التقارير مصممة للأجهزة اللوحية وشاشات سطح المكتب. استخدم شاشة أوسع لقراءة الجداول والعمل براحة.",
    },
    responses: {
      title: "مراجعة الردود أسهل على شاشة أوسع",
      message:
        "مراجعة الردود مصممة للأجهزة اللوحية وشاشات سطح المكتب. استخدم شاشة أوسع لمقارنة الإجابات وتصدير البيانات براحة.",
    },
    default: {
      title: "مساحة العمل مخصصة للشاشات الكبيرة",
      message:
        "مساحة العمل هذه مصممة للأجهزة اللوحية وشاشات سطح المكتب. استخدم شاشة أوسع للحصول على أفضل تجربة.",
    },
  },
};
const templateModalText = {
  en: {
    eyebrow: "Template library",
    title: "Choose a builder template",
    description:
      "Start from a focused operating system, then edit pages, forms, data, roles, workflows, and theme values.",
    close: "Close",
  },
  ar: {
    eyebrow: "مكتبة القوالب",
    title: "اختر قالبا للمنشئ",
    description:
      "ابدأ من نظام عمل جاهز، ثم عدل الصفحات والنماذج والبيانات والأدوار وسير العمل والثيم.",
    close: "إغلاق",
  },
};

const starterArabicText = {
  showcase: {
    category: "تجربة",
    title: "عرض شامل للمنشئ",
    subtitle: "قالب افتراضي كامل يعرض الصفحات والنماذج والبيانات والوسائط وتسجيل الدخول وسير العمل.",
    tags: ["كل الميزات", "تجربة"],
  },
  cms: {
    category: "إدارة محتوى",
    title: "مركز إدارة المحتوى",
    subtitle: "صفحات تحريرية، نماذج استقبال، سير نشر، سجلات محتوى، وأدوار فريق.",
    tags: ["محتوى", "نشر", "موافقات"],
  },
  ecommerce: {
    category: "تجارة",
    title: "واجهة متجر إلكتروني",
    subtitle: "عرض منتجات، استقبال طلبات، سجلات عملاء، حالة تنفيذ، وعمليات جاهزة للحجز.",
    tags: ["منتجات", "طلبات", "عملاء"],
  },
  hrFinance: {
    category: "عمليات",
    title: "بوابة الموارد البشرية والمالية",
    subtitle: "طلبات موظفين، موافقات ميزانية، تعويضات، دعم رواتب، ومراجعة حسب الأدوار.",
    tags: ["موارد بشرية", "مالية", "موافقات"],
  },
  meal: {
    category: "مشاريع",
    title: "تنسيق مشاريع المتابعة والتقييم",
    subtitle: "متابعة وتقييم ومساءلة وتعلم وتقارير ميدانية ومؤشرات ومتابعة الشركاء.",
    tags: ["متابعة وتقييم", "مشاريع", "تقارير"],
  },
  website: {
    title: "موقع ونموذج تواصل",
    subtitle: "موقع، نموذج تواصل، ردود، وأدوار أساسية.",
  },
  requests: {
    title: "بوابة طلبات وموافقات",
    subtitle: "موارد بشرية ومالية ومشتريات وموافقات داخلية.",
  },
  reports: {
    title: "مركز متابعة وتقارير",
    subtitle: "تقارير نشاط ولوحات متابعة وسير مراجعة.",
  },
  orders: {
    title: "نظام طلبات وحجوزات",
    subtitle: "طلبات عملاء وحجوزات خدمات وتتبع حالة.",
  },
  blank: {
    title: "نظام فارغ مخصص",
    subtitle: "ابدأ من صفحة واحدة ونموذج واحد ودور مدير.",
  },
};
const internalPageNames = new Set([
  "review responses",
  "responses",
  "reports",
  "orders",
  "submit request",
  "submit report",
  "place order",
]);

const getSectionElements = (section) => {
  const autoElements = (section.rows || []).flatMap((row) =>
    (row.columns || []).flatMap((column) => column.elements || [])
  );

  return [...autoElements, ...(section.freeElements || [])];
};

const isSvgUrlPath = (value) => {
  const path = String(value || "").split(/[?#]/, 1)[0].toLowerCase();
  return path.endsWith(".svg") || path.endsWith(".svgz");
};

const getStoredUrlError = (
  value,
  { fieldName = "URL", allowRelative = false, allowEmpty = true } = {}
) => {
  const cleanValue = String(value ?? "").trim();

  if (!cleanValue) {
    return allowEmpty ? "" : `${fieldName} is required.`;
  }

  if (controlCharacterPattern.test(cleanValue)) {
    return `${fieldName} contains invalid characters.`;
  }

  if (cleanValue.startsWith("//")) {
    return `${fieldName} cannot be protocol-relative.`;
  }

  if (cleanValue.startsWith("/")) {
    if (!allowRelative) return `${fieldName} must use an HTTPS URL.`;
    if (cleanValue.includes("\\")) return `${fieldName} contains invalid characters.`;
    if (isSvgUrlPath(cleanValue)) return `${fieldName} cannot be an SVG URL.`;
    return "";
  }

  const schemeMatch = cleanValue.match(urlSchemePattern);
  if (!schemeMatch) {
    return allowRelative
      ? `${fieldName} must be an HTTPS URL or managed internal path.`
      : `${fieldName} must be an HTTPS URL.`;
  }

  const scheme = schemeMatch[1].toLowerCase();

  if (blockedStoredUrlSchemes.has(scheme)) {
    return `${fieldName} cannot use ${scheme}: URLs.`;
  }

  if (scheme === "http") {
    return `${fieldName} must use HTTPS instead of HTTP.`;
  }

  if (scheme !== "https") {
    return `${fieldName} cannot use ${scheme}: URLs.`;
  }

  try {
    const parsedUrl = new URL(cleanValue);
    if (!parsedUrl.hostname) return `${fieldName} must include a host.`;
    if (isSvgUrlPath(parsedUrl.pathname)) return `${fieldName} cannot be an SVG URL.`;
  } catch {
    return `${fieldName} must be a valid HTTPS URL.`;
  }

  return "";
};

const collectBuilderElements = (project) =>
  (project?.pages || []).flatMap((page) =>
    (page.sections || []).flatMap((section) => getSectionElements(section))
  );

const collectSiteChromeUrlErrors = (siteChrome = {}) =>
  Object.entries(siteChrome).flatMap(([key, value]) => {
    if (!urlLikeSiteChromeKeys.has(key) || typeof value !== "string") return [];

    const error = getStoredUrlError(value, {
      fieldName: `Site ${key}`,
      allowRelative: true,
    });

    return error ? [error] : [];
  });

const collectCarouselImageUrlErrors = (content, fieldName) =>
  String(content || "")
    .split("\n\n")
    .map((block) => block.trim())
    .filter(Boolean)
    .flatMap((block, index) => {
      const lines = block.split("\n").map((line) => line.trim());
      const imageUrl = lines[2] || "";
      const error = getStoredUrlError(imageUrl, {
        fieldName: `${fieldName} slide ${index + 1} image URL`,
        allowRelative: true,
      });

      return error ? [error] : [];
    });

const collectBuilderUrlErrors = (project) => {
  const errors = collectSiteChromeUrlErrors(project?.siteChrome || {});

  collectBuilderElements(project).forEach((element) => {
    const elementName = element?.name || element?.type || "Element";

    if (element?.type === "image") {
      const error = getStoredUrlError(element.content, {
        fieldName: `${elementName} image URL`,
        allowRelative: true,
      });
      if (error) errors.push(error);
    }

    if (element?.type === "embed") {
      const error = getStoredUrlError(element.content, {
        fieldName: `${elementName} embed URL`,
      });
      if (error) errors.push(error);
    }

    if (carouselElementTypes.has(element?.type)) {
      errors.push(...collectCarouselImageUrlErrors(element.content, elementName));
    }

    if (element?.action?.url) {
      const error = getStoredUrlError(element.action.url, {
        fieldName: `${elementName} action URL`,
        allowRelative: true,
      });
      if (error) errors.push(error);
    }
  });

  return errors;
};

const isMetricsSection = (section) =>
  section?.name?.toLowerCase().includes("metric") ||
  getSectionElements(section).some((element) => element.type === "metric");

const isResponsesSection = (section) =>
  getSectionElements(section).some((element) => element.type === "responsesTable");

const hasFormSection = (page) =>
  (page.sections || []).some((section) =>
    getSectionElements(section).some((element) => element.type === "formBlock")
  );

const removeDuplicateFormHeadings = (section) => ({
  ...section,
  rows: (section.rows || []).map((row) => ({
    ...row,
    columns: (row.columns || []).map((column) => {
      const hasFormBlock = (column.elements || []).some((element) => element.type === "formBlock");
      if (!hasFormBlock) return column;

      return {
        ...column,
        elements: column.elements.filter(
          (element) =>
            !(
              element.type === "heading" &&
              String(element.content || "").trim().toLowerCase() === "submit your information"
            )
        ),
      };
    }),
  })),
});

const normalizeBuilderProjectShape = (project) => {
  const fallback = createInitialProject();
  const source =
    project && typeof project === "object" && !Array.isArray(project)
      ? project
      : {};

  const pages =
    Array.isArray(source.pages) && source.pages.length > 0
      ? source.pages
      : fallback.pages;

  const forms =
    Array.isArray(source.forms) && source.forms.length > 0
      ? source.forms
      : fallback.forms;

  const workflows = Array.isArray(source.workflows)
    ? source.workflows
    : fallback.workflows || [];

  const roles = Array.isArray(source.roles) ? source.roles : fallback.roles || [];
  const users = Array.isArray(source.users) ? source.users : fallback.users || [];
  const collections = Array.isArray(source.collections)
    ? source.collections
    : fallback.collections || [];

  return {
    ...fallback,
    ...source,
    pages,
    forms,
    workflows,
    roles,
    users,
    collections,
    activePageId: pages.some((page) => page.id === source.activePageId)
      ? source.activePageId
      : pages[0]?.id || "",
    activeFormId: forms.some((form) => form.id === source.activeFormId)
      ? source.activeFormId
      : forms[0]?.id || "",
    activeWorkflowId: workflows.some(
      (workflow) => workflow.id === source.activeWorkflowId
    )
      ? source.activeWorkflowId
      : workflows[0]?.id || "",
    activeRoleId: roles.some((role) => role.id === source.activeRoleId)
      ? source.activeRoleId
      : roles[0]?.id || "",
    siteChrome: {
      ...(fallback.siteChrome || defaultSiteChrome),
      ...(source.siteChrome || {}),
    },
    theme: {
      ...(fallback.theme || {}),
      ...(source.theme || {}),
    },
  };
};

const cleanBuilderProject = (project) => {
  const normalizedProject = normalizeBuilderProjectShape(project);

  if (!normalizedProject.pages.length) return normalizedProject;

  const formSectionsToKeep = normalizedProject.pages
    .slice(1)
    .flatMap((page) => page.sections || [])
    .filter((section) =>
      getSectionElements(section).some((element) => element.type === "formBlock")
    );

  const cleanedPages = normalizedProject.pages
    .filter(
      (page, index) =>
        index === 0 ||
        !internalPageNames.has(String(page.name || "").toLowerCase())
    )
    .map((page, index) => {
      const baseSections = (page.sections || []).filter(
        (section) => !isMetricsSection(section) && !isResponsesSection(section)
      );

      const sections =
        index === 0 && !hasFormSection({ ...page, sections: baseSections })
          ? [...baseSections, ...formSectionsToKeep]
          : baseSections;

      return {
        ...page,
        sections: sections.map(removeDuplicateFormHeadings),
        showInNavigation: index === 0 ? true : page.showInNavigation,
      };
    })
    .filter((page, index) => index === 0 || (page.sections || []).length > 0);

  const pages = cleanedPages.length ? cleanedPages : normalizedProject.pages;

  return {
    ...normalizedProject,
    activePageId: pages.some((page) => page.id === normalizedProject.activePageId)
      ? normalizedProject.activePageId
      : pages[0]?.id || "",
    siteChrome: {
      ...normalizedProject.siteChrome,
      footerShopLinks: String(normalizedProject.siteChrome?.footerShopLinks || "")
        .split("\n")
        .filter((item) => !["Responses", "Reports", "Orders"].includes(item.trim()))
        .join("\n"),
    },
    pages,
  };
};

const loadInitialProject = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return cleanBuilderProject(raw ? JSON.parse(raw) : createInitialProject());
  } catch {
    return cleanBuilderProject(createInitialProject());
  }
};

const normalizeProjectSlug = (value) => {
  const cleanValue = String(value || "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9-]/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-+|-+$/g, "");

  return cleanValue || `builder-project-${Date.now()}`;
};

const getBuilderProjectName = (project) =>
  String(project?.name || project?.siteChrome?.brandName || "Page Builder Project").trim() ||
  "Page Builder Project";

const getBuilderProjectSlug = (project, record) =>
  normalizeProjectSlug(record?.slug || project?.slug || project?.siteChrome?.subdomain || project?.siteChrome?.brandName || project?.name);

const getDraftProjectFromRecord = (record) => {
  if (!record?.draft_schema || typeof record.draft_schema !== "object" || Array.isArray(record.draft_schema)) {
    return null;
  }

  return cleanBuilderProject(record.draft_schema);
};

const getPreviewCanvasStyle = (viewport, isPreview) => {
  if (isPreview && viewport === "desktop") {
    return { width: "100%" };
  }

  const viewportWidth = viewports[viewport] || viewports.desktop;

  return {
    width: `${viewportWidth}px`,
    maxWidth: "100%",
  };
};

export default function PageBuilder({
  initialTab = "design",
  visibleTabIds = null,
  hideWorkspaceTabs = false,
  lang = "en",
  demoMode = false,
  templateLang = lang,
  appThemeMode = "light",
  onAppThemeModeChange,
  user = null,
} = {}) {
  const [project, setProject] = useState(() =>
    demoMode ? cleanBuilderProject(createInitialProject()) : loadInitialProject()
  );
  const [builderProjectRecord, setBuilderProjectRecord] = useState(null);
  const [builderProjectLoading, setBuilderProjectLoading] = useState(!demoMode);
  const [activeTab, setActiveTab] = useState(initialTab || "design");
  const [designPanel, setDesignPanel] = useState("Pages");
  const [viewport, setViewport] = useState("desktop");
  const [preview, setPreview] = useState(false);
  const [selected, setSelected] = useState({ type: "page", id: null });
  const [modal, setModal] = useState(() => (hideWorkspaceTabs ? null : "starter"));
  const [dragState, setDragState] = useState(null);
  const [insertTarget, setInsertTarget] = useState(null);
  const [runtimeAnswers, setRuntimeAnswers] = useState({});
  const [runtimeErrors, setRuntimeErrors] = useState({});
  const [quizSessions, setQuizSessions] = useState({});
  const [toast, setToast] = useState("");
  const [liveSitePath, setLiveSitePath] = useState("");
  const [activeTopbarAction, setActiveTopbarAction] = useState("");
  const [quizOptionsOpen, setQuizOptionsOpen] = useState(false);

  useEffect(() => {
    if (demoMode) return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(project));
  }, [demoMode, project]);

  useEffect(() => {
    if (demoMode) return;

    let cancelled = false;

    const loadBackendProject = async () => {
      setBuilderProjectLoading(true);

      try {
        const projects = await listBuilderProjects(user?.id);
        const selectedProject = projects[0] || null;

        if (!selectedProject) {
          if (!cancelled) {
            setBuilderProjectRecord(null);
          }
          return;
        }

        const fullRecord = await fetchBuilderProject(selectedProject.id, user?.id);
        const loadedProject = getDraftProjectFromRecord(fullRecord);

        if (!loadedProject) return;

        if (!cancelled) {
          setBuilderProjectRecord(fullRecord);
          setProject(loadedProject);
          setSelected({ type: "page", id: loadedProject.activePageId });
          localStorage.setItem(STORAGE_KEY, JSON.stringify(loadedProject));
        }
      } catch (error) {
        console.warn("Could not load builder project from backend:", error);
        if (!cancelled) {
          showToast("Using local draft cache. Save again when the backend is reachable.");
        }
      } finally {
        if (!cancelled) {
          setBuilderProjectLoading(false);
        }
      }
    };

    loadBackendProject();

    return () => {
      cancelled = true;
    };
  }, [demoMode]);

  const safeProjectPages = Array.isArray(project?.pages) ? project.pages : [];
  const safeProjectForms = Array.isArray(project?.forms) ? project.forms : [];
  const safeProjectWorkflows = Array.isArray(project?.workflows)
    ? project.workflows
    : [];
  const safeProjectRoles = Array.isArray(project?.roles) ? project.roles : [];

  const activePage = useMemo(
    () =>
      safeProjectPages.find((page) => page.id === project?.activePageId) ||
      safeProjectPages[0] ||
      null,
    [safeProjectPages, project?.activePageId]
  );

  const activeForm = useMemo(
    () =>
      safeProjectForms.find((form) => form.id === project?.activeFormId) ||
      safeProjectForms[0] ||
      null,
    [safeProjectForms, project?.activeFormId]
  );

  const activeWorkflow = useMemo(
    () =>
      safeProjectWorkflows.find(
        (workflow) => workflow.id === project?.activeWorkflowId
      ) ||
      safeProjectWorkflows[0] ||
      null,
    [safeProjectWorkflows, project?.activeWorkflowId]
  );

  const selectedSection = useMemo(() => {
    if (selected.type !== "section") return null;

    const sections = Array.isArray(activePage?.sections)
      ? activePage.sections
      : [];

    return sections.find((section) => section.id === selected.id) || null;
  }, [activePage, selected]);

  const selectedColumn = useMemo(() => {
    if (selected.type !== "column") return null;

    const sections = Array.isArray(activePage?.sections)
      ? activePage.sections
      : [];

    for (const section of sections) {
      const rows = Array.isArray(section?.rows) ? section.rows : [];

      for (const row of rows) {
        const columns = Array.isArray(row?.columns) ? row.columns : [];
        const column = columns.find((item) => item.id === selected.id);

        if (column) return column;
      }
    }

    return null;
  }, [activePage, selected]);

  const selectedElement = useMemo(() => {
    if (selected.type !== "element") return null;

    const sections = Array.isArray(activePage?.sections)
      ? activePage.sections
      : [];

    for (const section of sections) {
      if (section.mode === "free") {
        const freeElements = Array.isArray(section?.freeElements)
          ? section.freeElements
          : [];

        const found = freeElements.find((item) => item.id === selected.id);
        if (found) return found;
      }

      const rows = Array.isArray(section?.rows) ? section.rows : [];

      for (const row of rows) {
        const columns = Array.isArray(row?.columns) ? row.columns : [];

        for (const column of columns) {
          const elements = Array.isArray(column?.elements)
            ? column.elements
            : [];

          const found = elements.find((item) => item.id === selected.id);
          if (found) return found;
        }
      }
    }

    return null;
  }, [activePage, selected]);

  const selectedRole = useMemo(() => {
    if (selected.type !== "role") return null;
    return safeProjectRoles.find((role) => role.id === selected.id) || null;
  }, [safeProjectRoles, selected]);

  const showToast = (message) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 2200);
  };

  const updateProject = (updater) => {
    setProject((prev) => updater(prev));
  };

  const setThemeMode = (mode) => {
    updateProject((prev) => applyThemeModeToProject(prev, mode));

    if (typeof onAppThemeModeChange === "function") {
      onAppThemeModeChange(mode);
    }
  };

  useEffect(() => {
    if (!appThemeMode) return;
    if (project.theme?.mode === appThemeMode) return;

    setProject((prev) => applyThemeModeToProject(prev, appThemeMode));
  }, [appThemeMode, project.theme?.mode]);

  const updateActivePage = (updater) => {
    updateProject((prev) => ({
      ...prev,
      pages: prev.pages.map((page) =>
        page.id === prev.activePageId ? updater(page) : page
      ),
    }));
  };

  const updateSections = (updater) => {
    updateActivePage((page) => ({ ...page, sections: updater(page.sections) }));
  };

  const updateActiveForm = (updater) => {
    updateProject((prev) => ({
      ...prev,
      forms: prev.forms.map((form) =>
        form.id === prev.activeFormId ? updater(form) : form
      ),
    }));
  };

  const updateActiveWorkflow = (updater) => {
    updateProject((prev) => ({
      ...prev,
      workflows: prev.workflows.map((workflow) =>
        workflow.id === prev.activeWorkflowId ? updater(workflow) : workflow
      ),
    }));
  };

  const selectPage = (pageId) => {
    updateProject((prev) => ({ ...prev, activePageId: pageId }));
    setSelected({ type: "page", id: pageId });
  };

  const selectForm = (formId) => {
    updateProject((prev) => ({ ...prev, activeFormId: formId }));
    setSelected({ type: "form", id: formId });
  };

  const selectWorkflow = (workflowId) => {
    updateProject((prev) => ({ ...prev, activeWorkflowId: workflowId }));
    setSelected({ type: "workflow", id: workflowId });
  };

  const addPage = () => {
    const page = createPage(`Page ${project.pages.length + 1}`, [heroSection()]);
    updateProject((prev) => ({
      ...prev,
      pages: [...prev.pages, page],
      activePageId: page.id,
    }));
    setSelected({ type: "page", id: page.id });
  };

  const duplicatePage = () => {
    if (!activePage) return;
    const copy = cloneWithNewIds(activePage);
    copy.name = `${activePage.name} Copy`;
    copy.slug = `${activePage.slug === "/" ? "/home" : activePage.slug}-copy`;

    updateProject((prev) => ({
      ...prev,
      pages: [...prev.pages, copy],
      activePageId: copy.id,
    }));

    setSelected({ type: "page", id: copy.id });
  };

  const deleteActivePage = () => {
    if (!activePage || project.pages.length <= 1) {
      alert("You need at least one page.");
      return;
    }

    if (!window.confirm(`Delete page "${activePage.name}"?`)) return;

    const nextPage = project.pages.find((page) => page.id !== activePage.id);
    updateProject((prev) => ({
      ...prev,
      pages: prev.pages.filter((page) => page.id !== activePage.id),
      activePageId: nextPage.id,
    }));
    setSelected({ type: "page", id: nextPage.id });
  };

  const addSection = (factory) => {
    const section = factory(project.activeFormId);
    updateSections((sections) => [...sections, section]);
    setSelected({ type: "section", id: section.id });
    setModal(null);
  };

  const duplicateSelectedSection = () => {
    if (!selectedSection) return;
    const copy = cloneWithNewIds(selectedSection);
    copy.name = `${selectedSection.name} Copy`;

    updateSections((sections) => {
      const index = sections.findIndex((item) => item.id === selectedSection.id);
      const next = [...sections];
      next.splice(index + 1, 0, copy);
      return next;
    });

    setSelected({ type: "section", id: copy.id });
  };

  const updateSelectedSection = (updates) => {
    if (!selectedSection) return;

    updateSections((sections) =>
      sections.map((section) =>
        section.id === selectedSection.id
          ? {
              ...section,
              ...updates,
              layout: { ...section.layout, ...(updates.layout || {}) },
            }
          : section
      )
    );
  };

  const deleteSelectedSection = () => {
    if (!selectedSection) return;
    if (!window.confirm(`Delete section "${selectedSection.name}"?`)) return;

    updateSections((sections) => sections.filter((section) => section.id !== selectedSection.id));
    setSelected({ type: "page", id: activePage.id });
  };

  const addRowToSelectedSection = () => {
    if (!selectedSection || selectedSection.mode !== "auto") return;

    const row = createRow([createColumn()]);
    updateSections((sections) =>
      sections.map((section) =>
        section.id === selectedSection.id
          ? { ...section, rows: [...(section.rows || []), row] }
          : section
      )
    );
  };

  const updateSectionRow = (rowId, updates) => {
    if (!selectedSection) return;

    updateSections((sections) =>
      sections.map((section) =>
        section.id === selectedSection.id
          ? {
              ...section,
              rows: section.rows.map((row) =>
                row.id === rowId
                  ? { ...row, ...updates, layout: { ...row.layout, ...(updates.layout || {}) } }
                  : row
              ),
            }
          : section
      )
    );
  };

  const setRowColumnCount = (rowId, count) => {
    if (!selectedSection) return;

    updateSections((sections) =>
      sections.map((section) => {
        if (section.id !== selectedSection.id) return section;

        return {
          ...section,
          rows: section.rows.map((row) => {
            if (row.id !== rowId) return row;

            const nextColumns = [...row.columns];
            while (nextColumns.length < count) nextColumns.push(createColumn());
            const trimmedColumns = nextColumns.slice(0, count);
            const overflowColumns = nextColumns.slice(count);
            const overflowElements = overflowColumns.flatMap((column) => column.elements || []);

            if (overflowElements.length > 0 && trimmedColumns.length > 0) {
              trimmedColumns[trimmedColumns.length - 1] = {
                ...trimmedColumns[trimmedColumns.length - 1],
                elements: [
                  ...(trimmedColumns[trimmedColumns.length - 1].elements || []),
                  ...overflowElements,
                ],
              };
            }

            return {
              ...row,
              layout: { ...row.layout, columns: String(count) },
              columns: trimmedColumns,
            };
          }),
        };
      })
    );
  };

  const duplicateSectionRow = (rowId) => {
    if (!selectedSection) return;
    const sourceRow = selectedSection.rows.find((row) => row.id === rowId);
    if (!sourceRow) return;

    const copy = cloneWithNewIds(sourceRow);
    updateSections((sections) =>
      sections.map((section) => {
        if (section.id !== selectedSection.id) return section;
        const index = section.rows.findIndex((row) => row.id === rowId);
        const rows = [...section.rows];
        rows.splice(index + 1, 0, copy);
        return { ...section, rows };
      })
    );
  };

  const deleteSectionRow = (rowId) => {
    if (!selectedSection || selectedSection.rows.length <= 1) return;

    updateSections((sections) =>
      sections.map((section) =>
        section.id === selectedSection.id
          ? { ...section, rows: section.rows.filter((row) => row.id !== rowId) }
          : section
      )
    );
  };

  const updateSelectedColumn = (updates) => {
    if (!selectedColumn) return;

    updateSections((sections) =>
      sections.map((section) => ({
        ...section,
        rows: section.rows.map((row) => ({
          ...row,
          columns: row.columns.map((column) =>
            column.id === selectedColumn.id
              ? { ...column, ...updates, layout: { ...column.layout, ...(updates.layout || {}) } }
              : column
          ),
        })),
      }))
    );
  };

  const smartAddElement = (type) => {
    const element = createElement(type, type === "formBlock" || type === "responsesTable" ? { connectedFormId: project.activeFormId } : {});
    const selectedElementLocation = selectedElement ? findElementLocation(selectedElement.id) : null;

    if (selectedSection?.mode === "free") {
      const freeElement =
        insertTarget?.sectionId === selectedSection.id && insertTarget.mode === "free"
          ? {
              ...element,
              mode: "free",
              position: {
                ...element.position,
                [viewport]: {
                  ...element.position[viewport],
                  x: insertTarget.x,
                  y: insertTarget.y,
                },
              },
            }
          : { ...element, mode: "free" };

      updateSections((sections) =>
        sections.map((section) =>
          section.id === selectedSection.id
            ? { ...section, freeElements: [...section.freeElements, freeElement] }
            : section
        )
      );
      setSelected({ type: "element", id: element.id });
      return;
    }

    const insertTargetColumnExists = activePage.sections.some((section) =>
      (section.rows || []).some((row) =>
        (row.columns || []).some((column) => column.id === insertTarget?.columnId)
      )
    );

    let targetColumnId =
      selectedElementLocation?.isFree === false
        ? selectedElementLocation.columnId
        : selectedColumn?.id || (insertTargetColumnExists ? insertTarget.columnId : "");
    const afterElementId =
      selectedElementLocation?.isFree === false
        ? selectedElement.id
        : insertTarget?.columnId === targetColumnId
          ? insertTarget.afterElementId
          : "";

    if (!targetColumnId && selectedSection?.mode === "auto") {
      targetColumnId = selectedSection.rows?.[0]?.columns?.[0]?.id;
    }

    if (!targetColumnId) {
      const latestSection = activePage.sections[activePage.sections.length - 1];
      targetColumnId = latestSection?.rows?.[0]?.columns?.[0]?.id;
    }

    if (!targetColumnId) {
      const section = createSection({
        name: "Quick Section",
        rows: [createRow([createColumn([element])])],
      });
      updateSections((sections) => [...sections, section]);
      setSelected({ type: "element", id: element.id });
      return;
    }

    updateSections((sections) =>
      sections.map((section) => ({
        ...section,
        rows: section.rows.map((row) => ({
          ...row,
          columns: row.columns.map((column) => {
            if (column.id !== targetColumnId) return column;

            if (!afterElementId) {
              return { ...column, elements: [...column.elements, element] };
            }

            const insertIndex = column.elements.findIndex((item) => item.id === afterElementId);
            if (insertIndex < 0) {
              return { ...column, elements: [...column.elements, element] };
            }

            const elements = [...column.elements];
            elements.splice(insertIndex + 1, 0, element);
            return { ...column, elements };
          }),
        })),
      }))
    );

    setSelected({ type: "element", id: element.id });
  };

  const updateSelectedElement = (updates) => {
    if (!selectedElement) return;

    const merge = (element) => ({
      ...element,
      ...updates,
      styles: { ...element.styles, ...(updates.styles || {}) },
      action: { ...element.action, ...(updates.action || {}) },
    });

    updateSections((sections) =>
      sections.map((section) => {
        if (section.mode === "free") {
          return {
            ...section,
            freeElements: section.freeElements.map((element) =>
              element.id === selectedElement.id ? merge(element) : element
            ),
          };
        }

        return {
          ...section,
          rows: section.rows.map((row) => ({
            ...row,
            columns: row.columns.map((column) => ({
              ...column,
              elements: column.elements.map((element) =>
                element.id === selectedElement.id ? merge(element) : element
              ),
            })),
          })),
        };
      })
    );
  };

  const deleteSelectedElement = () => {
    if (!selectedElement) return;
    if (!window.confirm(`Delete "${selectedElement.name}"?`)) return;

    updateSections((sections) =>
      sections.map((section) => {
        if (section.mode === "free") {
          return {
            ...section,
            freeElements: section.freeElements.filter((element) => element.id !== selectedElement.id),
          };
        }

        return {
          ...section,
          rows: section.rows.map((row) => ({
            ...row,
            columns: row.columns.map((column) => ({
              ...column,
              elements: column.elements.filter((element) => element.id !== selectedElement.id),
            })),
          })),
        };
      })
    );

    setSelected({ type: "page", id: activePage.id });
  };

  const findElementLocation = (elementId) => {
    for (const section of activePage?.sections || []) {
      if (section.mode === "free") {
        const elementIndex = section.freeElements.findIndex((element) => element.id === elementId);
        if (elementIndex >= 0) return { sectionId: section.id, elementIndex, isFree: true };
      }

      for (const row of section.rows || []) {
        for (const column of row.columns || []) {
          const elementIndex = column.elements.findIndex((element) => element.id === elementId);
          if (elementIndex >= 0) {
            return { sectionId: section.id, rowId: row.id, columnId: column.id, elementIndex, isFree: false };
          }
        }
      }
    }

    return null;
  };

  const duplicateSelectedElement = () => {
    if (!selectedElement) return;
    const location = findElementLocation(selectedElement.id);
    const copy = cloneWithNewIds(selectedElement);
    copy.name = `${selectedElement.name} Copy`;

    updateSections((sections) =>
      sections.map((section) => {
        if (section.id !== location?.sectionId) return section;

        if (location.isFree) {
          const freeElements = [...section.freeElements];
          freeElements.splice(location.elementIndex + 1, 0, copy);
          return { ...section, freeElements };
        }

        return {
          ...section,
          rows: section.rows.map((row) => ({
            ...row,
            columns: row.columns.map((column) => {
              if (column.id !== location.columnId) return column;
              const elements = [...column.elements];
              elements.splice(location.elementIndex + 1, 0, copy);
              return { ...column, elements };
            }),
          })),
        };
      })
    );

    setSelected({ type: "element", id: copy.id });
  };

  const moveSelectedElement = (direction) => {
    if (!selectedElement) return;
    const location = findElementLocation(selectedElement.id);
    if (!location) return;

    if (location.isFree) {
      updateSections((sections) =>
        sections.map((section) => {
          if (section.id !== location.sectionId) return section;

          const freeElements = [...(section.freeElements || [])];
          const targetIndex = direction === "up" ? location.elementIndex - 1 : location.elementIndex + 1;
          if (targetIndex < 0 || targetIndex >= freeElements.length) return section;

          [freeElements[location.elementIndex], freeElements[targetIndex]] = [
            freeElements[targetIndex],
            freeElements[location.elementIndex],
          ];
          return { ...section, freeElements };
        })
      );
      return;
    }

    updateSections((sections) =>
      sections.map((section) => {
        if (section.id !== location.sectionId) return section;

        const slots = [];
        (section.rows || []).forEach((row, rowIndex) => {
          (row.columns || []).forEach((column, columnIndex) => {
            (column.elements || []).forEach((element, elementIndex) => {
              slots.push({ rowIndex, columnIndex, elementIndex, element });
            });
          });
        });

        const currentSlotIndex = slots.findIndex((slot) => slot.element.id === selectedElement.id);
        const targetSlotIndex = direction === "up" ? currentSlotIndex - 1 : currentSlotIndex + 1;
        if (currentSlotIndex < 0 || targetSlotIndex < 0 || targetSlotIndex >= slots.length) return section;

        const currentSlot = slots[currentSlotIndex];
        const targetSlot = slots[targetSlotIndex];

        return {
          ...section,
          rows: section.rows.map((row, rowIndex) => ({
            ...row,
            columns: row.columns.map((column, columnIndex) => {
              const isCurrentColumn =
                rowIndex === currentSlot.rowIndex && columnIndex === currentSlot.columnIndex;
              const isTargetColumn =
                rowIndex === targetSlot.rowIndex && columnIndex === targetSlot.columnIndex;

              if (!isCurrentColumn && !isTargetColumn) return column;

              const elements = [...column.elements];

              if (isCurrentColumn && isTargetColumn) {
                [elements[currentSlot.elementIndex], elements[targetSlot.elementIndex]] = [
                  elements[targetSlot.elementIndex],
                  elements[currentSlot.elementIndex],
                ];
                return { ...column, elements };
              }

              if (isCurrentColumn) {
                elements[currentSlot.elementIndex] = targetSlot.element;
                return { ...column, elements };
              }

              elements[targetSlot.elementIndex] = currentSlot.element;
              return { ...column, elements };
            }),
          })),
        };
      })
    );
  };

  const moveSelectedElementToColumn = (columnId) => {
    if (!selectedElement) return;
    const location = findElementLocation(selectedElement.id);
    if (!location || location.isFree || location.columnId === columnId) return;

    updateSections((sections) =>
      sections.map((section) => ({
        ...section,
        rows: section.rows.map((row) => ({
          ...row,
          columns: row.columns.map((column) => {
            if (column.id === location.columnId) {
              return {
                ...column,
                elements: column.elements.filter((element) => element.id !== selectedElement.id),
              };
            }

            if (column.id === columnId) {
              return { ...column, elements: [...column.elements, selectedElement] };
            }

            return column;
          }),
        })),
      }))
    );
  };

  const getFriendlySectionName = (section) => {
    const name = section?.name || "Page area";
    const normalized = name.toLowerCase();

    if (normalized.includes("hero")) return "Top area";
    if (normalized.includes("metric")) return "Stats area";
    if (normalized.includes("form")) return "Form area";
    if (normalized.includes("response")) return "Responses area";
    if (normalized.includes("login")) return "Login area";
    if (normalized.includes("reservation")) return "Booking area";
    if (normalized.includes("footer")) return "Footer area";
    if (normalized.includes("header")) return "Header area";

    return name;
  };

  const getFriendlyPlacementName = (section, row, rowIndex, columnIndex) => {
    const sectionName = getFriendlySectionName(section);
    const rows = section.rows || [];
    const columnCount = row.columns?.length || Number(row.layout?.columns) || 1;

    if (columnCount <= 1) {
      return rows.length > 1 ? `${sectionName} - row ${rowIndex + 1}` : sectionName;
    }

    if ((section.name || "").toLowerCase().includes("metric")) {
      return `Stat area ${columnIndex + 1}`;
    }

    if ((section.name || "").toLowerCase().includes("hero") && columnCount === 2) {
      return columnIndex === 0 ? "Intro content area" : "Supporting content area";
    }

    const placementNames = {
      2: ["Main content area", "Side content area"],
      3: ["Left content area", "Center content area", "Right content area"],
      4: ["Area 1", "Area 2", "Area 3", "Area 4"],
    };
    const placement = placementNames[columnCount]?.[columnIndex] || `Area ${columnIndex + 1}`;
    return rows.length > 1 ? `${sectionName} - row ${rowIndex + 1}, ${placement}` : `${sectionName} - ${placement}`;
  };

  const getColumnOptionLabel = (section, row, rowIndex, columnIndex) => {
    return getFriendlyPlacementName(section, row, rowIndex, columnIndex);
  };

  const getSectionLayerElements = (section) => {
    if (section.mode === "free") return section.freeElements || [];

    return (section.rows || []).flatMap((row) =>
      (row.columns || []).flatMap((column) => column.elements || [])
    );
  };

  const getElementLayerBaseLabel = (element, fallbackIndex = 0) => {
    const firstLine = splitLines(element.content)[0];

    if (element.type === "metric") return firstLine || "Metric";
    if (element.type === "heading") return "Headline";
    if (element.type === "text") return "Description";
    if (element.type === "button") return firstLine || "Button";
    if (element.type === "card") return firstLine || "Info card";
    if (element.type === "formBlock") {
      const form = project.forms.find((item) => item.id === element.connectedFormId);
      return form?.title || "Form";
    }
    if (element.type === "responsesTable") {
      const form = project.forms.find((item) => item.id === element.connectedFormId);
      return form ? `${form.title} responses` : "Responses";
    }

    return element.name || `Component ${fallbackIndex + 1}`;
  };

  const getElementLayerLabel = (element, elementIndex, elements) => {
    const baseLabel = getElementLayerBaseLabel(element, elementIndex);
    const duplicateIndex =
      elements
        .slice(0, elementIndex + 1)
        .filter((item, index) => getElementLayerBaseLabel(item, index) === baseLabel).length;
    const duplicateCount = elements.filter((item, index) => getElementLayerBaseLabel(item, index) === baseLabel).length;

    return duplicateCount > 1 ? `${baseLabel} ${duplicateIndex}` : baseLabel;
  };

  const getFreePositionBasis = (key) => {
    if (key === "x" || key === "width") return viewports[viewport] || viewports.desktop;

    const location = selectedElement ? findElementLocation(selectedElement.id) : null;
    const section = activePage?.sections.find((item) => item.id === location?.sectionId);
    return section?.layout?.minHeight || 560;
  };

  const getElementPositionPercent = (key) => {
    if (!selectedElement) return 0;

    const current = selectedElement.position?.[viewport] || createPosition()[viewport];
    const value = Number(current[key] || 0);
    const basis = getFreePositionBasis(key);
    return Math.round((value / basis) * 100);
  };

  const updateElementPositionPercent = (key, value) => {
    if (!selectedElement) return;

    const percent = value === "" ? "" : Number(value);
    const basis = getFreePositionBasis(key);
    const nextValue = percent === "" ? "" : Math.round((basis * percent) / 100);
    updateElementPosition(key, nextValue);
  };

  const updateElementPosition = (key, value) => {
    if (!selectedElement) return;

    const current = selectedElement.position?.[viewport] || createPosition()[viewport];
    const nextValue = value === "" ? "" : Number(value);

    updateSelectedElement({
      position: {
        ...selectedElement.position,
        [viewport]: {
          ...current,
          [key]: nextValue,
        },
      },
    });
  };

  const updateSelectedElementPlacement = (alignSelf) => {
    if (!selectedElement) return;

    const currentWidth = selectedElement.styles.width || "";
    const shouldMakeMovable =
      isDirectionalElementPlacement(alignSelf) &&
      (!currentWidth || currentWidth === "auto" || currentWidth === "100%");

    const nextElement = {
      ...selectedElement,
      styles: {
        ...selectedElement.styles,
        alignSelf,
        ...(shouldMakeMovable ? { width: "70%" } : {}),
      },
    };

    if (carouselElementTypes.has(selectedElement.type)) {
      updateSelectedElement({ styles: nextElement.styles });
      return;
    }

    const location = findElementLocation(selectedElement.id);
    const targetColumnIndexByPlacement = (columns) => {
      const placement = normalizeElementAlignSelf(alignSelf);
      if (placement === "flex-start") return 0;
      if (placement === "flex-end") return columns.length - 1;
      if (placement === "center") return Math.floor((columns.length - 1) / 2);
      return -1;
    };

    if (!location || location.isFree) {
      updateSelectedElement({ styles: nextElement.styles });
      return;
    }

    updateSections((sections) =>
      sections.map((section) => {
        if (section.id !== location.sectionId) return section;

        return {
          ...section,
          rows: section.rows.map((row) => {
            if (row.id !== location.rowId) return row;

            const targetColumnIndex = targetColumnIndexByPlacement(row.columns || []);
            const targetColumn = targetColumnIndex >= 0 ? row.columns[targetColumnIndex] : null;

            return {
              ...row,
              columns: row.columns.map((column) => {
                if (!targetColumn || column.id === location.columnId) {
                  return {
                    ...column,
                    elements: column.elements.map((element) =>
                      element.id === selectedElement.id ? nextElement : element
                    ),
                  };
                }

                if (column.id !== targetColumn.id) return column;

                const sourceColumn = row.columns.find((item) => item.id === location.columnId);
                const sourceIndex = sourceColumn?.elements.findIndex((item) => item.id === selectedElement.id) ?? -1;
                const insertIndex = Math.min(
                  Math.max(sourceIndex, 0),
                  column.elements.length
                );
                const elements = [...column.elements];
                elements.splice(insertIndex, 0, nextElement);

                return { ...column, elements };
              }).map((column) =>
                targetColumn && column.id === location.columnId && column.id !== targetColumn.id
                  ? {
                      ...column,
                      elements: column.elements.filter((element) => element.id !== selectedElement.id),
                    }
                  : column
              ),
            };
          }),
        };
      })
    );
  };

  const showAssetUploadUnavailable = () => {
    showToast(assetUploadUnavailableMessage);
  };

  const updateActiveFormQuiz = (updates) => {
    updateActiveForm((form) => ({
      ...form,
      quiz: {
        ...getQuizSettings(form),
        ...updates,
      },
    }));
  };

  const addForm = () => {
    const form = createForm(`Form ${project.forms.length + 1}`, [createField("Question 1", "shortText")]);
    updateProject((prev) => ({
      ...prev,
      forms: [...prev.forms, form],
      activeFormId: form.id,
      workflows: [...prev.workflows, createWorkflow(`After ${form.title} is submitted`, form.id)],
    }));
    setSelected({ type: "form", id: form.id });
  };

  const addFormSection = () => {
    const section = {
      id: createId("formSection"),
      title: `Section ${getFormSections(activeForm).length + 1}`,
      description: "",
      collapsed: false,
      fields: [],
    };

    updateActiveForm((form) => ({
      ...form,
      sections: [...getFormSections(form), section],
    }));
  };

  const addFieldToForm = (type = "shortText", sectionId = null) => {
    if (!activeForm) return;
    const meta = getFieldType(type);
    const field = createField(meta.label, type, {
      options: ["dropdown", "radio", "checkboxes", "status"].includes(type)
        ? ["Option 1", "Option 2"]
        : [],
    });
    const targetSectionId = sectionId || getFormSections(activeForm)[0]?.id;

    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).map((section) =>
        section.id === targetSectionId
          ? { ...section, fields: [...(section.fields || []), field] }
          : section
      ),
    }));

    setSelected({ type: "field", id: field.id });
  };

  const updateFormField = (fieldId, updates) => {
    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).map((section) => ({
        ...section,
        fields: (section.fields || []).map((field) =>
          field.id === fieldId
            ? (() => {
                const nextType = updates.type || field.type;
                const isChoice = ["dropdown", "radio", "checkboxes", "status"].includes(nextType);
                const nextOptions = updates.options || field.options || [];
                const typeChanged = updates.type && updates.type !== field.type;

                return {
                  ...field,
                  ...updates,
                  options: isChoice ? (nextOptions.length ? nextOptions : ["Option 1", "Option 2"]) : [],
                  ...(typeChanged
                    ? { quizCorrectAnswer: nextType === "checkboxes" ? [] : "" }
                    : {}),
                };
              })()
            : field
        ),
      })),
    }));
  };

  const updateFormSection = (sectionId, updates) => {
    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).map((section) =>
        section.id === sectionId ? { ...section, ...updates } : section
      ),
    }));
  };

  const renderQuizAnswerKeyEditor = (field) => {
    if (!correctableQuizTypes.has(field.type)) {
      return (
        <div className="quiz-answer-key is-muted">
          <strong>Correct answer</strong>
          <p>This field type is not automatically graded.</p>
        </div>
      );
    }

    if (field.type === "checkboxes") {
      const selectedAnswers = Array.isArray(field.quizCorrectAnswer) ? field.quizCorrectAnswer : [];

      return (
        <div className="quiz-answer-key">
          <strong>Correct answers</strong>
          <div className="quiz-answer-options">
            {getFieldOptions(field).map((option) => (
              <label className="checkbox-control" key={option}>
                <input
                  type="checkbox"
                  checked={selectedAnswers.includes(option)}
                  onChange={(event) => {
                    const nextAnswers = event.target.checked
                      ? [...selectedAnswers, option]
                      : selectedAnswers.filter((answer) => answer !== option);
                    updateFormField(field.id, { quizCorrectAnswer: nextAnswers });
                  }}
                />
                {option}
              </label>
            ))}
          </div>
        </div>
      );
    }

    if (singleAnswerQuizTypes.has(field.type)) {
      const options =
        field.type === "yesNo"
          ? ["Yes", "No"]
          : field.type === "linearScale"
            ? scaleRange(field)
            : field.type === "rating"
              ? Array.from({ length: Math.max(2, Math.min(10, Number(field.maxRating || 5))) }, (_, index) => String(index + 1))
              : getFieldOptions(field);

      return (
        <div className="quiz-answer-key">
          <label>
            Correct answer
            <select
              value={field.quizCorrectAnswer || ""}
              onChange={(event) => updateFormField(field.id, { quizCorrectAnswer: event.target.value })}
            >
              <option value="">Select the correct answer</option>
              {options.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </label>
        </div>
      );
    }

    return (
      <div className="quiz-answer-key">
        <label>
          Accepted answers
          <textarea
            value={Array.isArray(field.quizCorrectAnswer) ? field.quizCorrectAnswer.join("\n") : field.quizCorrectAnswer || ""}
            placeholder="One accepted answer per line"
            onChange={(event) => updateFormField(field.id, { quizCorrectAnswer: splitLines(event.target.value) })}
          />
        </label>
      </div>
    );
  };

  const duplicateFormField = (fieldId) => {
    if (!activeForm) return;
    let nextFieldId = "";

    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).map((section) => {
        const fieldIndex = (section.fields || []).findIndex((field) => field.id === fieldId);
        if (fieldIndex < 0) return section;

        const copy = cloneWithNewIds(section.fields[fieldIndex]);
        copy.label = `${section.fields[fieldIndex].label} Copy`;
        nextFieldId = copy.id;
        const fields = [...section.fields];
        fields.splice(fieldIndex + 1, 0, copy);
        return { ...section, fields };
      }),
    }));

    if (nextFieldId) setSelected({ type: "field", id: nextFieldId });
  };

  const moveFormField = (fieldId, direction) => {
    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).map((section) => {
        const fieldIndex = (section.fields || []).findIndex((field) => field.id === fieldId);
        if (fieldIndex < 0) return section;

        const targetIndex = direction === "up" ? fieldIndex - 1 : fieldIndex + 1;
        if (targetIndex < 0 || targetIndex >= section.fields.length) return section;

        const fields = [...section.fields];
        [fields[fieldIndex], fields[targetIndex]] = [fields[targetIndex], fields[fieldIndex]];
        return { ...section, fields };
      }),
    }));
  };

  const deleteFormSection = (sectionId) => {
    if (!activeForm || getFormSections(activeForm).length <= 1) return;

    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).filter((section) => section.id !== sectionId),
    }));
  };

  const deleteFormField = (fieldId) => {
    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).map((section) => ({
        ...section,
        fields: (section.fields || []).filter((field) => field.id !== fieldId),
      })),
    }));
    setSelected({ type: "form", id: activeForm?.id });
  };

  const startQuizSession = (form) => {
    const fields = getFormFields(form);
    if (fields.length === 0) return;

    const settings = getQuizSettings(form);
    const firstLimit = Number(fields[0]?.quizTimeLimitSec || settings.questionTimeLimitSec || 0);

    setQuizSessions((prev) => ({
      ...prev,
      [form.id]: {
        active: true,
        currentIndex: 0,
        totalRemaining: Number(settings.totalTimeLimitSec || 0),
        questionRemaining: firstLimit,
      },
    }));

    if (settings.lockScreen && document.documentElement.requestFullscreen) {
      document.documentElement.requestFullscreen().catch(() => undefined);
    }
  };

  const resetQuizSession = (formId) => {
    setQuizSessions((prev) => {
      const next = { ...prev };
      delete next[formId];
      return next;
    });
  };

  const moveQuizQuestion = (form, direction) => {
    const fields = getFormFields(form);
    const settings = getQuizSettings(form);

    setQuizSessions((prev) => {
      const current = prev[form.id];
      if (!current) return prev;

      const nextIndex =
        direction === "next"
          ? Math.min(fields.length - 1, current.currentIndex + 1)
          : Math.max(0, current.currentIndex - 1);
      const nextLimit = Number(fields[nextIndex]?.quizTimeLimitSec || settings.questionTimeLimitSec || 0);

      return {
        ...prev,
        [form.id]: {
          ...current,
          currentIndex: nextIndex,
          questionRemaining: nextLimit,
        },
      };
    });
  };

  const addWorkflow = () => {
    const workflow = createWorkflow(`Workflow ${project.workflows.length + 1}`, project.activeFormId);
    updateProject((prev) => ({
      ...prev,
      workflows: [...prev.workflows, workflow],
      activeWorkflowId: workflow.id,
    }));
    setSelected({ type: "workflow", id: workflow.id });
  };

  const addWorkflowStep = () => {
    const step = {
      id: createId("workflowStep"),
      type: "showMessage",
      label: "New step",
      details: "Describe what this step should do later.",
    };

    updateActiveWorkflow((workflow) => ({
      ...workflow,
      steps: [...workflow.steps, step],
    }));
  };

  const updateWorkflowStep = (stepId, updates) => {
    updateActiveWorkflow((workflow) => ({
      ...workflow,
      steps: workflow.steps.map((step) =>
        step.id === stepId ? { ...step, ...updates } : step
      ),
    }));
  };

  const deleteWorkflowStep = (stepId) => {
    updateActiveWorkflow((workflow) => ({
      ...workflow,
      steps: workflow.steps.filter((step) => step.id !== stepId),
    }));
  };

  const addRole = () => {
    const role = createRole(`Role ${project.roles.length + 1}`);
    updateProject((prev) => ({
      ...prev,
      roles: [...prev.roles, role],
      activeRoleId: role.id,
    }));
    setSelected({ type: "role", id: role.id });
  };

  const updateRole = (roleId, updates) => {
    updateProject((prev) => ({
      ...prev,
      roles: prev.roles.map((role) =>
        role.id === roleId
          ? {
              ...role,
              ...updates,
              permissions: { ...role.permissions, ...(updates.permissions || {}) },
            }
          : role
      ),
    }));
  };

  const addUser = () => {
    const user = createUser(
      `User ${project.users.length + 1}`,
      `user${project.users.length + 1}@madar.local`,
      project.roles[0]?.id || ""
    );

    updateProject((prev) => ({
      ...prev,
      users: [...prev.users, user],
    }));
  };

  const updateUser = (userId, updates) => {
  updateProject((prev) => ({
    ...prev,
    users: prev.users.map((user) => (user.id === userId ? { ...user, ...updates } : user)),
  }));
};

  const deleteUser = (userId) => {
  const user = project.users.find((item) => item.id === userId);

  if (!user) return;

  const isMainAdmin = user.email === "admin@madar.local";

  if (isMainAdmin) {
    alert("You cannot delete the main admin user.");
    return;
  }

  if (!window.confirm(`Delete user "${user.name}"?`)) return;

  updateProject((prev) => ({
    ...prev,
    users: prev.users.filter((item) => item.id !== userId),
  }));

  showToast("User deleted.");
};

  const getResponseCount = () =>
    project.forms.reduce((total, form) => total + (form.responses?.length || 0), 0);

  const getSavedRecordCount = () =>
    project.collections.reduce((total, collection) => total + (collection.records?.length || 0), 0);

  const setAnswer = (formId, fieldId, value) => {
    setRuntimeAnswers((prev) => ({
      ...prev,
      [formId]: {
        ...(prev[formId] || {}),
        [fieldId]: value,
      },
    }));

    setRuntimeErrors((prev) => {
      const next = { ...prev };
      delete next[fieldId];
      return next;
    });
  };

  const submitRuntimeForm = (form, { skipValidation = false } = {}) => {
    const enteredAnswers = runtimeAnswers[form.id] || {};
    const answers = getFormFields(form).reduce((acc, field) => {
      if (enteredAnswers[field.id] !== undefined) {
        acc[field.id] = enteredAnswers[field.id];
      } else if (field.defaultValue) {
        acc[field.id] = field.defaultValue;
      }
      return acc;
    }, {});
    const nextErrors = {};

    if (!skipValidation) {
      getFormFields(form).forEach((field) => {
        if (!field.required) return;
        const value = answers[field.id];

        if (
          value === undefined ||
          value === null ||
          value === "" ||
          (Array.isArray(value) && value.length === 0)
        ) {
          nextErrors[field.id] = "This field is required.";
        }
      });
    }

    setRuntimeErrors(nextErrors);

    if (Object.keys(nextErrors).length > 0) return;

    const quizResult = form.mode === "quiz" ? gradeQuizResponse(form, answers) : null;
    const responseStatus =
      quizResult?.passed === true
        ? "Passed"
        : quizResult?.passed === false
          ? "Failed"
          : form.mode === "quiz"
            ? "Submitted"
            : "New";

    const response = {
      id: createId("response"),
      createdAt: new Date().toISOString(),
      status: responseStatus,
      answers,
      ...(quizResult ? { quiz: quizResult } : {}),
    };

    updateProject((prev) => ({
      ...prev,
      forms: prev.forms.map((item) =>
        item.id === form.id ? { ...item, responses: [response, ...item.responses] } : item
      ),
      collections: prev.collections.map((collection) =>
        collection.id === form.connectedCollectionId
          ? { ...collection, records: [response, ...(collection.records || [])] }
          : collection
      ),
    }));

    setRuntimeAnswers((prev) => ({ ...prev, [form.id]: {} }));
    resetQuizSession(form.id);
    if (form.mode === "quiz" && document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => undefined);
    }
    if (form.mode === "quiz" && quizResult && getQuizSettings(form).showResults) {
      if (quizResult.score === null) {
        showToast("Quiz submitted. This quiz needs manual review.");
      } else {
        showToast(`Quiz submitted. Score: ${quizResult.score}% (${quizResult.correct}/${quizResult.total}).`);
      }
    } else {
      showToast(form.successMessage);
    }
  };

  const runElementAction = (element) => {
    const action = element.action || {};

    if (action.type === "goToPage" && action.pageId) {
      selectPage(action.pageId);
      return;
    }

    if (action.type === "openUrl" && action.url) {
      const urlError = getStoredUrlError(action.url, {
        fieldName: "Button action URL",
        allowRelative: true,
      });

      if (urlError) {
        showToast(urlError);
        return;
      }

      window.open(action.url, "_blank", "noopener,noreferrer");
      return;
    }

    if (action.type === "showMessage" && action.message) {
      showToast(action.message);
    }
  };

  const persistProject = (nextProject, message) => {
    if (!demoMode) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(nextProject));
    }
    setProject(nextProject);
    showToast(message);
    return nextProject;
  };

  const saveProject = async () => {
    setActiveTopbarAction("save");

    const nextProject = {
      ...project,
      publish: {
        ...project.publish,
        lastSavedAt: new Date().toISOString(),
      },
    };
    const urlErrors = collectBuilderUrlErrors(nextProject);

    if (urlErrors.length > 0) {
      showToast(urlErrors[0]);
      return;
    }

    if (demoMode) {
      persistProject(nextProject, "Demo changes stay until refresh.");
      return;
    }

    if (builderProjectLoading) {
      showToast("Builder project is still loading. Try saving again in a moment.");
      return;
    }

    persistProject(nextProject, "Saving to backend...");

    try {
      const payload = {
        name: getBuilderProjectName(nextProject),
        slug: getBuilderProjectSlug(nextProject, builderProjectRecord),
        draft_schema: nextProject,
      };

      const savedRecord = builderProjectRecord?.id
        ? await updateBuilderProject(builderProjectRecord.id, payload, user?.id)
        : await createBuilderProject(payload, user?.id);

      setBuilderProjectRecord(savedRecord);
      showToast("Saved to backend.");
    } catch (error) {
      console.error("Could not save builder project:", error);
      showToast("Saved local draft cache. Backend save failed.");
    }
  };

  const loadProject = async () => {
    if (demoMode) {
      const freshProject = cleanBuilderProject(createInitialProject());
      setProject(freshProject);
      setSelected({ type: "page", id: freshProject.activePageId });
      showToast("Default demo template loaded.");
      return;
    }

    try {
      const projects = await listBuilderProjects(user?.id);
      const selectedProject = projects[0] || null;

      if (selectedProject) {
        const fullRecord = await fetchBuilderProject(selectedProject.id, user?.id);
        const loadedProject = getDraftProjectFromRecord(fullRecord);

        if (loadedProject) {
          setBuilderProjectRecord(fullRecord);
          setProject(loadedProject);
          setSelected({ type: "page", id: loadedProject.activePageId });
          localStorage.setItem(STORAGE_KEY, JSON.stringify(loadedProject));
          showToast("Loaded backend project.");
          return;
        }
      }
    } catch (error) {
      console.warn("Could not load backend builder project:", error);
    }

    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      alert("No backend project or local draft cache found.");
      return;
    }

    try {
      const loaded = cleanBuilderProject(JSON.parse(raw));
      setProject(loaded);
      setSelected({ type: "page", id: loaded.activePageId });
      showToast("Loaded local draft cache.");
    } catch {
      alert("Saved project is not valid JSON.");
    }
  };

  const publishProject = async () => {
    setActiveTopbarAction("publish");
    const publishedProject = {
      ...project,
      status: "published",
      publish: {
        ...project.publish,
        lastSavedAt: new Date().toISOString(),
        lastPublishedAt: new Date().toISOString(),
      },
    };
    const urlErrors = collectBuilderUrlErrors(publishedProject);

    if (urlErrors.length > 0) {
      showToast(urlErrors[0]);
      return;
    }

    if (demoMode) {
      persistProject(publishedProject, "Demo publish status updated until refresh.");
      return;
    }

    if (builderProjectLoading) {
      showToast("Builder project is still loading. Try publishing again in a moment.");
      return;
    }

    persistProject(publishedProject, "Publishing to backend...");
    setLiveSitePath("");
    const liveWindow = window.open("about:blank", "_blank");

    try {
      const websiteSettings = await fetchWebsiteSettings(user?.id);
      const publicSubdomain = sanitizeSubdomain(websiteSettings?.subdomain || "");

      if (!publicSubdomain) {
        if (liveWindow && !liveWindow.closed) {
          liveWindow.close();
        }
        throw new Error("Configure a website subdomain before going live.");
      }

      const liveSitePath = `/site/${publicSubdomain}/`;
      const payload = {
        name: getBuilderProjectName(publishedProject),
        slug: getBuilderProjectSlug(publishedProject, builderProjectRecord),
        draft_schema: publishedProject,
      };

      const savedRecord = builderProjectRecord?.id
        ? await updateBuilderProject(builderProjectRecord.id, payload, user?.id)
        : await createBuilderProject(payload, user?.id);

      const publishedRecord = await publishBuilderProject(savedRecord.id, user?.id);

      setBuilderProjectRecord(publishedRecord);
      showToast("Site published to backend.");

      if (liveWindow && !liveWindow.closed) {
        liveWindow.location.href = liveSitePath;
      } else {
        const openedWindow = window.open(liveSitePath, "_blank", "noopener,noreferrer");
        if (!openedWindow) {
          setLiveSitePath(liveSitePath);
          showToast("Site published. Use the open live site link.");
        }
      }
    } catch (error) {
      if (liveWindow && !liveWindow.closed) {
        liveWindow.close();
      }
      console.error("Could not publish builder project:", error);
      showToast(error?.message || "Publish failed. Local draft cache was updated.");
    }
  };

  const exportProject = () => {
    const payload = JSON.stringify(project, null, 2);
    console.log(payload);

    try {
      navigator.clipboard.writeText(payload);
      showToast("Exported JSON copied to clipboard.");
    } catch {
      showToast("Exported JSON printed to console.");
    }
  };

  const applyStarter = (starterId) => {
    const starter = buildStarterProject(starterId);
    setProject(starter);
    setSelected({ type: "page", id: starter.activePageId });
    setActiveTab("design");
    setModal(null);
  };

  const getFormPlacements = (formId) =>
    project.pages.flatMap((page) =>
      page.sections.flatMap((section) => {
        const autoElements = (section.rows || []).flatMap((row) =>
          (row.columns || []).flatMap((column) => column.elements || [])
        );
        const freeElements = section.freeElements || [];
        const connected = [...autoElements, ...freeElements].some(
          (element) =>
            ["formBlock", "responsesTable"].includes(element.type) &&
            element.connectedFormId === formId
        );

        return connected ? [{ pageId: page.id, pageName: page.name, sectionName: section.name }] : [];
      })
    );

  const addConnectedFormSectionToPage = (formId, pageId = project.activePageId) => {
    if (!formId || !pageId) return;

    const section = formSection(formId);

    updateProject((prev) => ({
      ...prev,
      activePageId: pageId,
      activeFormId: formId,
      pages: prev.pages.map((page) =>
        page.id === pageId ? { ...page, sections: [...page.sections, section] } : page
      ),
    }));

    setSelected({ type: "section", id: section.id });
    setActiveTab("design");
    setDesignPanel("Layers");
    showToast("Form added to the selected page.");
  };

  const addConnectedResponsesSectionToPage = (formId, pageId = project.activePageId) => {
    if (!formId || !pageId) return;

    const section = responsesSection(formId);

    updateProject((prev) => ({
      ...prev,
      activePageId: pageId,
      activeFormId: formId,
      pages: prev.pages.map((page) =>
        page.id === pageId ? { ...page, sections: [...page.sections, section] } : page
      ),
    }));

    setSelected({ type: "section", id: section.id });
    setActiveTab("design");
    setDesignPanel("Layers");
    showToast("Responses table added to the selected page.");
  };

  const getElementStyle = (element) => {
    const isSelected = selected.type === "element" && selected.id === element.id;
    const placementMargins = getElementPlacementMargins(element.styles.alignSelf);
    const layoutWidth =
      getElementLayoutWidth(element.styles.width, element.styles.alignSelf) ||
      (carouselElementTypes.has(element.type) ? "100%" : undefined);

    return {
      ...element.styles,
      "--builder-element-width": layoutWidth || "auto",
      "--builder-element-align": normalizeElementAlignSelf(element.styles.alignSelf) || "auto",
      "--builder-element-color": element.styles.color || "inherit",
      "--builder-element-bg": element.styles.backgroundColor || "transparent",
      "--builder-element-radius": element.styles.borderRadius || "0",
      "--builder-element-font-size": element.styles.fontSize || "inherit",
      "--builder-element-text-align": element.styles.textAlign || "inherit",
      position: "relative",
      transform: undefined,
      width: layoutWidth,
      minHeight: element.styles.minHeight || undefined,
      maxWidth: "100%",
      alignSelf: normalizeElementAlignSelf(element.styles.alignSelf),
      ...placementMargins,
      zIndex: isSelected ? 5 : 1,
    };
  };

  const getFreeElementStyle = (element) => {
    const pos = element.position?.[viewport] || createPosition()[viewport];
    const location = findElementLocation(element.id);
    const section = activePage?.sections.find((item) => item.id === location?.sectionId);
    const viewportWidth = viewports[viewport] || viewports.desktop;
    const sectionHeight = Number(section?.layout?.minHeight) || 560;
    const left = `${((Number(pos.x) || 0) / viewportWidth) * 100}%`;
    const top = `${((Number(pos.y) || 0) / sectionHeight) * 100}%`;
    const width = `${((Number(pos.width) || 240) / viewportWidth) * 100}%`;
    const minHeight = `${((Number(pos.height) || 80) / sectionHeight) * 100}%`;

    return {
      ...element.styles,
      "--builder-element-color": element.styles.color || "inherit",
      "--builder-element-bg": element.styles.backgroundColor || "transparent",
      "--builder-element-radius": element.styles.borderRadius || "0",
      "--builder-element-font-size": element.styles.fontSize || "inherit",
      "--builder-element-text-align": element.styles.textAlign || "inherit",
      position: "absolute",
      left,
      top,
      width,
      minHeight,
      maxWidth: `calc(100% - ${left})`,
    };
  };

  const startDrag = (event, element) => {
    if (preview || element.mode !== "free") return;

    const tagName = event.target?.tagName?.toLowerCase();
    if (["input", "textarea", "select", "option", "button"].includes(tagName)) return;

    event.stopPropagation();
    event.preventDefault();

    const current = element.position?.[viewport] || createPosition()[viewport];

    setSelected({ type: "element", id: element.id });
    setDragState({
      elementId: element.id,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: current.x || 0,
      startY: current.y || 0,
    });
  };

  const handleMouseMove = (event) => {
    if (!dragState || !selectedElement || selectedElement.id !== dragState.elementId) return;

    const current = selectedElement.position?.[viewport] || createPosition()[viewport];
    const deltaX = event.clientX - dragState.startClientX;
    const deltaY = event.clientY - dragState.startClientY;

    updateSelectedElement({
      position: {
        ...selectedElement.position,
        [viewport]: {
          ...current,
          x: Math.max(-600, dragState.startX + deltaX),
          y: Math.max(-600, dragState.startY + deltaY),
        },
      },
    });
  };

  const renderFieldInput = (form, field, disabled = false) => {
    const value = runtimeAnswers[form.id]?.[field.id] || field.defaultValue || "";
    const error = runtimeErrors[field.id];
    const meta = getFieldType(field.type);
    const placeholder = getModernFieldPlaceholder(field);

    const common = {
      disabled,
      value,
      onChange: (event) => setAnswer(form.id, field.id, event.target.value),
    };

    let inputNode = null;

    if (["text", "email", "tel", "number", "date", "time", "url"].includes(meta.input)) {
      inputNode = <input type={meta.input} placeholder={placeholder} {...common} />;
    } else if (meta.input === "textarea") {
      inputNode = <textarea placeholder={placeholder} {...common} />;
    } else if (meta.input === "select") {
      inputNode = (
        <select {...common}>
          <option value="">{placeholder}</option>
          {getFieldOptions(field).map((option) => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
      );
    } else if (meta.input === "radio") {
      inputNode = (
        <div className="choice-list">
          {getFieldOptions(field).map((option) => (
            <label key={option}>
              <input
                type="radio"
                name={field.id}
                checked={value === option}
                disabled={disabled}
                onChange={() => setAnswer(form.id, field.id, option)}
              />
              <span>{option}</span>
            </label>
          ))}
        </div>
      );
    } else if (meta.input === "checkboxes") {
      const values = Array.isArray(runtimeAnswers[form.id]?.[field.id])
        ? runtimeAnswers[form.id][field.id]
        : [];

      inputNode = (
        <div className="choice-list">
          {getFieldOptions(field).map((option) => (
            <label key={option}>
              <input
                type="checkbox"
                checked={values.includes(option)}
                disabled={disabled}
                onChange={(event) => {
                  const next = event.target.checked
                    ? [...values, option]
                    : values.filter((item) => item !== option);
                  setAnswer(form.id, field.id, next);
                }}
              />
              <span>{option}</span>
            </label>
          ))}
        </div>
      );
    } else if (meta.input === "linearScale") {
      inputNode = (
        <div className="scale-choice">
          <span>{field.scaleMinLabel || field.scaleMin || 1}</span>
          {scaleRange(field).map((option) => (
            <button
              type="button"
              key={option}
              disabled={disabled}
              className={value === option ? "active" : ""}
              onClick={() => setAnswer(form.id, field.id, option)}
            >
              {option}
            </button>
          ))}
          <span>{field.scaleMaxLabel || field.scaleMax || 5}</span>
        </div>
      );
    } else if (meta.input === "rating") {
      const maxRating = Math.max(2, Math.min(10, Number(field.maxRating || 5)));
      inputNode = (
        <div className="rating-choice">
          {Array.from({ length: maxRating }, (_, index) => String(index + 1)).map((option) => (
            <button
              type="button"
              key={option}
              disabled={disabled}
              className={Number(value) >= Number(option) ? "active" : ""}
              onClick={() => setAnswer(form.id, field.id, option)}
            >
              {option}
            </button>
          ))}
        </div>
      );
    } else if (meta.input === "yesNo") {
      inputNode = (
        <div className="choice-pills">
          {["Yes", "No"].map((option) => (
            <button
              type="button"
              key={option}
              disabled={disabled}
              className={value === option ? "active" : ""}
              onClick={() => setAnswer(form.id, field.id, option)}
            >
              {option}
            </button>
          ))}
        </div>
      );
    } else if (meta.input === "file") {
      inputNode = (
        <input
          type="file"
          disabled={disabled}
          onChange={(event) => {
            const file = event.target.files?.[0];
            setAnswer(form.id, field.id, file ? { name: file.name, size: file.size, type: file.type } : "");
          }}
        />
      );
    }

    return (
      <div className={`runtime-question ${error ? "has-error" : ""}`} key={field.id}>
        <label>
          <span>
            {field.label}
            {field.required ? " *" : ""}
          </span>
          {field.helpText && <small>{field.helpText}</small>}
          {inputNode}
          {error && <strong>{error}</strong>}
        </label>
      </div>
    );
  };

  useEffect(() => {
    const timer = window.setInterval(() => {
      setQuizSessions((prev) => {
        let changed = false;
        const next = { ...prev };

        Object.entries(prev).forEach(([formId, session]) => {
          if (!session?.active) return;

          const nextSession = { ...session };
          if (nextSession.totalRemaining > 0) {
            nextSession.totalRemaining -= 1;
            changed = true;
          }

          if (nextSession.questionRemaining > 0) {
            nextSession.questionRemaining -= 1;
            changed = true;
          }

          next[formId] = nextSession;
        });

        return changed ? next : prev;
      });
    }, 1000);

    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    Object.entries(quizSessions).forEach(([formId, session]) => {
      if (!session?.active) return;
      const form = project.forms.find((item) => item.id === formId);
      if (!form) return;
      const fields = getFormFields(form);

      if (session.totalRemaining === 0 && getQuizSettings(form).totalTimeLimitSec > 0) {
        submitRuntimeForm(form, { skipValidation: true });
        return;
      }

      if (session.questionRemaining === 0) {
        const questionLimit = Number(fields[session.currentIndex]?.quizTimeLimitSec || getQuizSettings(form).questionTimeLimitSec || 0);
        if (questionLimit <= 0) return;

        if (session.currentIndex >= fields.length - 1) {
          submitRuntimeForm(form, { skipValidation: true });
        } else {
          moveQuizQuestion(form, "next");
        }
      }
    });
  }, [quizSessions, project.forms]);

  const renderConnectedForm = (formId, { allowInteraction = preview } = {}) => {
    const form = project.forms.find((item) => item.id === formId) || project.forms[0];
    if (!form) return <div className="empty-connected">No form selected.</div>;
    const isQuiz = form.mode === "quiz";
    const quizSettings = getQuizSettings(form);
    const quizFields = getFormFields(form);
    const quizSession = quizSessions[form.id];
    const quizStarted = !isQuiz || quizSession?.active;
    const currentQuestionIndex = Math.min(quizSession?.currentIndex || 0, Math.max(quizFields.length - 1, 0));
    const currentField = quizFields[currentQuestionIndex];

    return (
      <div className={`runtime-form ${isQuiz ? "runtime-quiz-form" : ""} ${quizSettings.lockScreen ? "runtime-quiz-lockable" : ""}`}>
        <div className="runtime-form-header">
          <h3>{form.title}</h3>
          <p>{form.description}</p>
          {isQuiz && (
            <div className="quiz-runtime-meta">
              <span>{quizFields.length} questions</span>
              {quizSettings.totalTimeLimitSec > 0 && (
                <span>Total: {formatQuizTime(quizStarted ? quizSession?.totalRemaining : quizSettings.totalTimeLimitSec)}</span>
              )}
              {quizSettings.questionTimeLimitSec > 0 && (
                <span>Per question: {formatQuizTime(quizSettings.questionTimeLimitSec)}</span>
              )}
              {quizSettings.lockScreen && <span>Focus mode</span>}
            </div>
          )}
        </div>

        {isQuiz && !quizStarted ? (
          <div className="quiz-start-panel">
            <strong>Ready to start?</strong>
            <p>
              {quizSettings.lockScreen
                ? "This quiz opens in focus mode. Timers begin when you start."
                : "Timers begin when you start the quiz."}
            </p>
            <button
              type="button"
              className="runtime-submit"
              disabled={!allowInteraction || quizFields.length === 0}
              onClick={() => startQuizSession(form)}
            >
              Start quiz
            </button>
          </div>
        ) : isQuiz ? (
          <div className="runtime-form-section quiz-question-stage">
            <div className="runtime-form-section-header">
              <h4>Question {currentQuestionIndex + 1} of {quizFields.length}</h4>
              {quizSession?.questionRemaining > 0 && (
                <p>Question time: {formatQuizTime(quizSession.questionRemaining)}</p>
              )}
            </div>

            {currentField && renderFieldInput(form, currentField, !allowInteraction)}

            <div className="quiz-navigation">
              <button
                type="button"
                disabled={!allowInteraction || currentQuestionIndex === 0}
                onClick={() => moveQuizQuestion(form, "previous")}
              >
                Previous
              </button>
              {currentQuestionIndex < quizFields.length - 1 ? (
                <button
                  type="button"
                  disabled={!allowInteraction}
                  onClick={() => moveQuizQuestion(form, "next")}
                >
                  Next
                </button>
              ) : (
                <button
                  type="button"
                  className="runtime-submit"
                  disabled={!allowInteraction}
                  onClick={() => submitRuntimeForm(form)}
                >
                  Submit quiz
                </button>
              )}
            </div>
          </div>
        ) : (
          <>
            {getFormSections(form).map((section) => (
              <div className="runtime-form-section" key={section.id}>
                <div className="runtime-form-section-header">
                  <h4>{section.title}</h4>
                  {section.description && <p>{section.description}</p>}
                </div>

                {(section.fields || []).map((field) => renderFieldInput(form, field, !allowInteraction))}
              </div>
            ))}

            <button
              type="button"
              className="runtime-submit"
              disabled={!allowInteraction}
              onClick={() => submitRuntimeForm(form)}
            >
              Submit
            </button>
          </>
        )}

        {!allowInteraction && <p className="builder-note">Enable Preview to test this form.</p>}
      </div>
    );
  };

  const renderResponsesTable = (formId) => {
    const form = project.forms.find((item) => item.id === formId) || project.forms[0];
    if (!form) return <div className="empty-connected">No form selected.</div>;

    const fields = getFormFields(form).slice(0, 4);
    const responses = form.responses;
    const isQuiz = form.mode === "quiz";

    return (
      <div className="responses-preview">
        <div className="responses-preview-header">
          <strong>{form.title}</strong>
          <span>{responses.length} responses</span>
        </div>

        <div className="mock-table">
          <div className="mock-table-row mock-table-head">
            <span>Status</span>
            {isQuiz && <span>Score</span>}
            {fields.map((field) => (
              <span key={field.id}>{field.label}</span>
            ))}
          </div>

          {(responses.length ? responses : [{ id: "sample", status: "Sample", answers: {} }]).map((response) => (
            <div className="mock-table-row" key={response.id}>
              <span>{response.status || "New"}</span>
              {isQuiz && <span>{response.quiz?.score === null || response.quiz?.score === undefined ? "-" : `${response.quiz.score}%`}</span>}
              {fields.map((field) => (
                <span key={field.id}>{formatSavedValue(response.answers?.[field.id])}</span>
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderElement = (element, isFree = false) => {
    const isSelected = selected.type === "element" && selected.id === element.id;

    const commonProps = {
      className: `builder-element builder-element-${element.type} ${isSelected ? "is-selected" : ""}`,
      style: isFree ? getFreeElementStyle(element) : getElementStyle(element),
      onMouseDown: (event) => startDrag(event, element),
      onClick: (event) => {
        event.stopPropagation();
        if (!preview) {
          const location = findElementLocation(element.id);
          if (location?.isFree === false) {
            setInsertTarget({
              sectionId: location.sectionId,
              mode: "auto",
              columnId: location.columnId,
              afterElementId: element.id,
            });
          } else if (location?.isFree) {
            setInsertTarget({
              sectionId: location.sectionId,
              mode: "free",
              afterElementId: element.id,
            });
          }
          setSelected({ type: "element", id: element.id });
        }
      },
    };

    if (element.type === "heading") {
      return <h1 key={element.id} {...commonProps}>{element.content}</h1>;
    }

    if (element.type === "text") {
      return <p key={element.id} {...commonProps}>{element.content}</p>;
    }

    if (element.type === "button") {
      return (
        <button
          key={element.id}
          type="button"
          {...commonProps}
          onClick={(event) => {
            commonProps.onClick(event);
            if (preview) runElementAction(element);
          }}
        >
          {element.content}
        </button>
      );
    }

    if (element.type === "image") {
      return <img key={element.id} {...commonProps} src={element.content} alt={element.name} />;
    }

    if (element.type === "card") {
      return (
        <div key={element.id} {...commonProps}>
          {String(element.content || "").split("\n").map((line, index) => (
            <span key={`${element.id}_${index}`}>{line}</span>
          ))}
        </div>
      );
    }

    if (carouselElementTypes.has(element.type)) {
      const carouselWidth = getCarouselWidthValue(element);
      const carouselFrameStyle = {
        ...commonProps.style,
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
          {...commonProps}
          className={`${commonProps.className} carousel-position-frame ${getComponentPositionClass(element.styles.alignSelf)}`}
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
        <ul key={element.id} {...commonProps}>
          {splitLines(element.content).map((item) => <li key={item}>{item}</li>)}
        </ul>
      );
    }

    if (element.type === "divider") {
      return <hr key={element.id} {...commonProps} />;
    }

    if (element.type === "embed") {
      return (
        <div key={element.id} {...commonProps}>
          <strong>Embed</strong>
          <a href={element.content} target="_blank" rel="noreferrer">{element.content}</a>
        </div>
      );
    }

    if (element.type === "metric") {
      const [label, value] = String(element.content || "").split("\n");
      return (
        <div key={element.id} {...commonProps}>
          <span className="metric-label">{label}</span>
          <strong className="metric-value">{value}</strong>
        </div>
      );
    }

    if (element.type === "formBlock") {
      return <div key={element.id} {...commonProps}>{renderConnectedForm(element.connectedFormId)}</div>;
    }

    if (element.type === "responsesTable") {
      return <div key={element.id} {...commonProps}>{renderResponsesTable(element.connectedFormId)}</div>;
    }

    return <div key={element.id} {...commonProps}>{element.content}</div>;
  };

  const renderSiteHeader = () => {
    const site = project.siteChrome || defaultSiteChrome;
    if (!site.showHeader) return null;

    const logoSrc = site.logoUrl;

    return (
      <header
        className={`built-site-header header-align-${site.headerAlign || "center"} ${selected.type === "siteHeader" ? "is-selected" : ""}`}
        onClick={(event) => {
          event.stopPropagation();
          if (!preview) setSelected({ type: "siteHeader", id: "site-header" });
        }}
      >
        <div className="built-site-header-inner">
          <button
            type="button"
            className="built-site-brand"
            onClick={(event) => {
              event.stopPropagation();
              const homePage = project.pages.find((page) => page.slug === "/") || project.pages[0];
              if (homePage) selectPage(homePage.id);
            }}
          >
            {logoSrc ? <img src={logoSrc} alt={`${site.brand || "Website"} logo`} /> : <span className="logo-fallback">M</span>}
            <span>{site.brand || "Website"}</span>
          </button>

          <nav className="built-site-nav">
            {project.pages.map((page) => (
              <button
                type="button"
                key={page.id}
                className={activePage?.id === page.id ? "active" : ""}
                onClick={(event) => {
                  event.stopPropagation();
                  selectPage(page.id);
                }}
              >
                {page.name}
              </button>
            ))}
          </nav>

          <button type="button" className="built-site-cta">
            {site.headerButtonLabel || "Contact"}
          </button>
        </div>
      </header>
    );
  };

  const renderSiteFooter = () => {
    const site = project.siteChrome || defaultSiteChrome;
    if (!site.showFooter) return null;

    const pageLinks = splitLines(site.footerShopLinks || "");
    const helpLinks = splitLines(site.footerHelpLinks || "About Us\nPolicies\nContact");
    const socialLinks = splitLines(site.footerSocialLinks || "Facebook\nLinkedIn\nX\nInstagram");
    const footerLinks = [...pageLinks, ...helpLinks];
    const footerBrand = site.footerStoreName || site.brand || "Your Brand";
    const footerInitial = footerBrand.trim().slice(0, 1).toUpperCase() || "B";
    const navigateFooterLink = (label) => {
      const normalizedLabel = label.toLowerCase().trim();
      const target = project.pages.find((page) => {
        const normalizedName = page.name.toLowerCase().trim();
        const normalizedSlug = page.slug.toLowerCase().replace(/^\//, "");
        return normalizedName === normalizedLabel || normalizedSlug === normalizedLabel.replace(/\s+/g, "-");
      });

      if (target) selectPage(target.id);
    };

    return (
      <footer
        className={`built-site-footer ecommerce-style-footer ${selected.type === "siteFooter" ? "is-selected" : ""}`}
        onClick={(event) => {
          event.stopPropagation();
          if (!preview) setSelected({ type: "siteFooter", id: "site-footer" });
          if (event.target.closest(".powered-by-madar")) {
            window.location.href = site.madarLink || "/";
          }
        }}
      >
        <div className="ecommerce-footer-grid">
          <div className="ecommerce-footer-brand">
            <div className="ecommerce-footer-logo-row">
              {site.logoUrl ? (
                <img className="ecommerce-footer-logo" src={site.logoUrl} alt={`${footerBrand} logo`} />
              ) : (
                <div className="ecommerce-footer-logo footer-logo-fallback">{footerInitial}</div>
              )}
              <h3>{footerBrand}</h3>
            </div>

            <p>{site.description}</p>

            <div className="ecommerce-social-row">
              {socialLinks.map((item) => (
                <button type="button" key={item} aria-label={item}>
                  {item.slice(0, 2).toUpperCase()}
                </button>
              ))}
            </div>

          </div>

          <div className="ecommerce-footer-column ecommerce-footer-links-column">
            <h4>Links</h4>
            <div className="ecommerce-footer-links-grid">
              {footerLinks.map((item) => <button type="button" key={item} onClick={() => navigateFooterLink(item)}>{item}</button>)}
            </div>
          </div>

          <div className="ecommerce-footer-contact">
            <h4>Contact</h4>
            <div className="footer-language-pill">
              <span>|</span>
              <strong>{site.footerLanguageLabel || "AR"}</strong>
            </div>
            <p>{site.contactEmail || "info@madar.com"}</p>
            <p dir="ltr">{site.phone || "+972599203857"}</p>
          </div>
        </div>

        <div className="ecommerce-footer-bottom">
          <p>(c) 2026 {site.footerStoreName || site.brand || "Your Website"}. {site.rights || "All rights reserved."}</p>
          <button type="button" className="powered-by-madar">Powered by Madar</button>
        </div>
      </footer>
    );
  };

  const renderDesignTab = () => (
    <div className="builder-layout">
      {!preview && (
        <aside className="builder-sidebar">
          <div className="builder-side-panel">
            <div className="panel-mode-select">
              <label>
                Editing panel
                <select value={designPanel} onChange={(event) => setDesignPanel(event.target.value)}>
                  {designPanels.map((panel) => <option key={panel} value={panel}>{panel}</option>)}
                </select>
              </label>
            </div>

            {designPanel === "Pages" && (
              <section className="builder-panel">
                <h2>Pages</h2>
                <p className="panel-help">Create public pages, dashboards, forms, and review screens.</p>

                <select value={activePage?.id || ""} onChange={(event) => selectPage(event.target.value)}>
                  {project.pages.map((page) => <option key={page.id} value={page.id}>{page.name}</option>)}
                </select>

                <div className="compact-actions">
                  <button type="button" onClick={addPage}>+ Page</button>
                  <button type="button" onClick={duplicatePage}>Duplicate</button>
                  <button type="button" onClick={() => setModal("starter")}>Starter</button>
                  <button type="button" className="danger-lite" onClick={deleteActivePage}>Delete</button>
                </div>
              </section>
            )}

          {designPanel === "Sections" && (
            <section className="builder-panel">
              <h2>Sections</h2>
              <p className="panel-help">Add page blocks. Auto layout is recommended.</p>
              <button type="button" className="full-width-action" onClick={() => setModal("section")}>+ Add Section</button>
              {selectedSection && (
                <div className="compact-actions">
                  <button type="button" onClick={duplicateSelectedSection}>Duplicate</button>
                  <button type="button" className="danger-lite" onClick={deleteSelectedSection}>Delete</button>
                </div>
              )}
            </section>
          )}

          {designPanel === "Layers" && (
            <section className="builder-panel">
              <h2>Layers</h2>
              <p className="panel-help">Page outline. Select a section or component to edit it.</p>
              <div className="layer-add-actions">
                <button type="button" onClick={() => setModal("section")}>
                  Add page area
                </button>
                {[
                  ["heading", "Headline"],
                  ["text", "Description"],
                  ["button", "Button"],
                  ["image", "Image"],
                  ["formBlock", "Form"],
                ].map(([type, label]) => (
                  <button type="button" key={type} onClick={() => smartAddElement(type)}>
                    Add {label}
                  </button>
                ))}
              </div>
              <div className="layer-tree">
                {activePage?.sections.map((section, sectionIndex) => {
                  const elements = getSectionLayerElements(section);

                  return (
                    <div key={section.id} className="layer-item">
                      <button
                        type="button"
                        className={`layer-section-button ${selected.id === section.id ? "active" : ""}`}
                        onClick={() => setSelected({ type: "section", id: section.id })}
                      >
                        {section.name || `Section ${sectionIndex + 1}`}
                      </button>

                      <div className="layer-children">
                        {elements.length > 0 ? (
                          elements.map((element, elementIndex) => (
                            <button
                              type="button"
                              key={element.id}
                              className={`layer-element-button ${selected.id === element.id ? "active" : ""}`}
                              onClick={() => setSelected({ type: "element", id: element.id })}
                            >
                              {getElementLayerLabel(element, elementIndex, elements)}
                            </button>
                          ))
                        ) : (
                          <span className="layer-empty">No components yet</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {designPanel === "Elements" && (
            <section className="builder-panel">
              <h2>Add Elements</h2>
              <p className="panel-help">Select a section or column, then add an element.</p>

                {["Content", "Collection", "Dashboard", "Connected"].map((group) => (
                <div key={group} className="add-group">
                  <span>{group}</span>
                  {elementTypes
                    .filter((item) => item.group === group)
                    .map((item) => (
                      <button type="button" key={item.id} onClick={() => smartAddElement(item.id)}>
                        + {item.label}
                      </button>
                    ))}
                </div>
              ))}
            </section>
          )}
          </div>
        </aside>
      )}

      <main
        className="builder-canvas-shell"
        onClick={() => {
          if (!preview) setSelected({ type: "page", id: activePage?.id });
        }}
      >
        <div
          className={`builder-canvas viewport-${viewport}`}
          style={getPreviewCanvasStyle(viewport, preview)}
        >
          {renderSiteHeader()}

          {activePage?.sections.map((section) => {
            const isSelected = selected.type === "section" && selected.id === section.id;

            if (section.mode === "free") {
              return (
                <section
                  key={section.id}
                  className={`site-section free-canvas-section width-${section.layout.width} ${isSelected ? "is-selected" : ""}`}
                  style={{ backgroundColor: section.layout.background, minHeight: section.layout.minHeight }}
                  onClick={(event) => {
                    event.stopPropagation();
                    if (!preview) {
                      const frame = event.currentTarget.querySelector(".free-canvas-frame");
                      const rect = frame?.getBoundingClientRect();
                      setInsertTarget({
                        sectionId: section.id,
                        mode: "free",
                        x: rect ? Math.max(0, Math.round(event.clientX - rect.left)) : 40,
                        y: rect ? Math.max(0, Math.round(event.clientY - rect.top)) : 40,
                      });
                      setSelected({ type: "section", id: section.id });
                    }
                  }}
                >
                  {!preview && (
                    <div className="free-canvas-toolbar">
                      <strong>Free Canvas</strong>
                      <button type="button" onClick={() => setSelected({ type: "page", id: activePage.id })}>Exit</button>
                    </div>
                  )}

                  <div
                    className="free-canvas-frame"
                    style={{ width: `min(100%, ${viewports[viewport]}px)`, minHeight: `${section.layout.minHeight}px` }}
                  >
                    {section.freeElements.map((element) => renderElement(element, true))}
                  </div>
                </section>
              );
            }

            return (
              <section
                key={section.id}
                className={`site-section width-${section.layout.width} padding-${section.layout.paddingY} ${isSelected ? "is-selected" : ""}`}
                style={{ backgroundColor: section.layout.background }}
                onClick={(event) => {
                  event.stopPropagation();
                  if (!preview) {
                    const columnId = getClosestColumnIdFromEvent(event);
                      setInsertTarget({
                        sectionId: section.id,
                        mode: "auto",
                        columnId,
                        afterElementId: "",
                      });
                    setSelected({ type: "section", id: section.id });
                  }
                }}
              >
                {section.rows.map((row) => (
                  <div
                    key={row.id}
                    className={`site-row columns-${row.layout.columns} align-${row.layout.align} gap-${row.layout.gap}`}
                  >
                    {row.columns.map((column) => {
                      const columnSelected = selected.type === "column" && selected.id === column.id;

                      return (
                        <div
                          key={column.id}
                          data-column-id={column.id}
                          className={`site-column column-align-${column.layout.align} ${columnSelected ? "is-selected" : ""}`}
                          onClick={(event) => {
                            event.stopPropagation();
                            if (!preview) {
                              setInsertTarget({
                                sectionId: section.id,
                                mode: "auto",
                                columnId: column.id,
                                afterElementId: "",
                              });
                              setSelected({ type: "column", id: column.id });
                            }
                          }}
                        >
                          {column.elements
                            .filter((element) => !carouselElementTypes.has(element.type))
                            .map((element) => renderElement(element, false))}
                          {!preview && column.elements.length === 0 && (
                            <div className="empty-column">Select this column, then add an element.</div>
                          )}
                        </div>
                      );
                    })}
                    {getRowCarouselElements(row).map((element) => renderElement(element, false))}
                  </div>
                ))}
              </section>
            );
          })}

          {renderSiteFooter()}
        </div>
      </main>

      {!preview && renderInspector()}
    </div>
  );

  const renderInspector = () => (
    <aside className="builder-inspector">
      <div className="builder-side-panel">
        <div className="inspector-title">
          <h2>Inspector</h2>
          <span>{selected.type}</span>
        </div>

      {selected.type === "page" && activePage && (
        <div className="inspector-group">
          <h3>Page Settings</h3>
          <label>Page name<input value={activePage.name} onChange={(event) => updateActivePage((page) => ({ ...page, name: event.target.value }))} /></label>
          <label>Page link<input value={activePage.slug} onChange={(event) => updateActivePage((page) => ({ ...page, slug: event.target.value }))} /></label>
          <label>Page background<input type="color" value={activePage.backgroundColor || "#ffffff"} onChange={(event) => updateActivePage((page) => ({ ...page, backgroundColor: event.target.value }))} /></label>

          <details>
            <summary>Website Header & Footer</summary>
            <label>Brand name<input value={project.siteChrome?.brand || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), brand: event.target.value } }))} /></label>
            <label>Contact email<input value={project.siteChrome?.contactEmail || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), contactEmail: event.target.value } }))} /></label>
            <label>Phone<input value={project.siteChrome?.phone || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), phone: event.target.value } }))} /></label>
            <label>Logo URL<input value={project.siteChrome?.logoUrl || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), logoUrl: event.target.value } }))} /></label>
            <button type="button" className="upload-image-button" onClick={showAssetUploadUnavailable}>Upload logo</button>
            <label>Footer brand name<input value={project.siteChrome?.footerStoreName || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), footerStoreName: event.target.value } }))} /></label>
            <label>Footer description<textarea value={project.siteChrome?.description || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), description: event.target.value } }))} /></label>
            <label>Footer rights<input value={project.siteChrome?.rights || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), rights: event.target.value } }))} /></label>
            <label>Footer pages<textarea value={project.siteChrome?.footerShopLinks || ""} placeholder="One link per line" onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), footerShopLinks: event.target.value } }))} /></label>
            <label>Footer help links<textarea value={project.siteChrome?.footerHelpLinks || ""} placeholder="One link per line" onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), footerHelpLinks: event.target.value } }))} /></label>
            <label>Social links<textarea value={project.siteChrome?.footerSocialLinks || ""} placeholder="One item per line" onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), footerSocialLinks: event.target.value } }))} /></label>
          </details>
        </div>
      )}

      {selected.type === "siteHeader" && (
        <div className="inspector-group">
          <h3>Header</h3>
          <label>Brand name<input value={project.siteChrome?.brand || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), brand: event.target.value } }))} /></label>
          <label>Logo URL<input value={project.siteChrome?.logoUrl || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), logoUrl: event.target.value } }))} /></label>
          <button type="button" className="upload-image-button" onClick={showAssetUploadUnavailable}>Upload logo</button>
          <label>Header button<input value={project.siteChrome?.headerButtonLabel || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), headerButtonLabel: event.target.value } }))} /></label>
          <label>Header alignment<select value={project.siteChrome?.headerAlign || "center"} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), headerAlign: event.target.value } }))}>
            <option value="left">Left</option>
            <option value="center">Center</option>
            <option value="right">Right</option>
          </select></label>
        </div>
      )}

      {selected.type === "siteFooter" && (
        <div className="inspector-group">
          <h3>Footer</h3>
          <label>Footer brand name<input value={project.siteChrome?.footerStoreName || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), footerStoreName: event.target.value } }))} /></label>
          <label>Footer description<textarea value={project.siteChrome?.description || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), description: event.target.value } }))} /></label>
          <label>Contact email<input value={project.siteChrome?.contactEmail || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), contactEmail: event.target.value } }))} /></label>
          <label>Phone<input value={project.siteChrome?.phone || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), phone: event.target.value } }))} /></label>
          <label>Footer pages<textarea value={project.siteChrome?.footerShopLinks || ""} placeholder="One link per line" onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), footerShopLinks: event.target.value } }))} /></label>
          <label>Footer help links<textarea value={project.siteChrome?.footerHelpLinks || ""} placeholder="One link per line" onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), footerHelpLinks: event.target.value } }))} /></label>
          <label>Social links<textarea value={project.siteChrome?.footerSocialLinks || ""} placeholder="One item per line" onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), footerSocialLinks: event.target.value } }))} /></label>
          <label>Footer rights<input value={project.siteChrome?.rights || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), rights: event.target.value } }))} /></label>
        </div>
      )}

      {selected.type === "section" && selectedSection && (
        <div className="inspector-group">
          <h3>Section</h3>
          <label>Name<input value={selectedSection.name} onChange={(event) => updateSelectedSection({ name: event.target.value })} /></label>
          <label>Background<input type="color" value={selectedSection.layout.background === "transparent" ? "#ffffff" : selectedSection.layout.background} onChange={(event) => updateSelectedSection({ layout: { background: event.target.value } })} /></label>
          <label>Width<select value={selectedSection.layout.width} onChange={(event) => updateSelectedSection({ layout: { width: event.target.value } })}>{sectionWidths.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          <label>Padding<select value={selectedSection.layout.paddingY} onChange={(event) => updateSelectedSection({ layout: { paddingY: event.target.value } })}>{spacingOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          {selectedSection.mode === "free" && <label>Minimum height<input type="number" value={selectedSection.layout.minHeight} onChange={(event) => updateSelectedSection({ layout: { minHeight: Number(event.target.value) } })} /></label>}
          {selectedSection.mode === "auto" && (
            <details open>
              <summary>Rows and columns</summary>
              <button type="button" className="full-width-action" onClick={addRowToSelectedSection}>+ Add Row</button>
              <div className="row-editor-list">
                {(selectedSection.rows || []).map((row, index) => (
                  <div className="row-editor-card" key={row.id}>
                    <div className="row-editor-header">
                      <strong>Row {index + 1}</strong>
                      <div>
                        <button type="button" onClick={() => duplicateSectionRow(row.id)}>Duplicate</button>
                        <button type="button" className="danger-lite" onClick={() => deleteSectionRow(row.id)}>Delete</button>
                      </div>
                    </div>
                    <label>Columns<select value={row.layout.columns} onChange={(event) => setRowColumnCount(row.id, Number(event.target.value))}>{columnOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
                    <label>Alignment<select value={row.layout.align} onChange={(event) => updateSectionRow(row.id, { layout: { align: event.target.value } })}>{["start", "center", "stretch"].map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
                    <label>Gap<select value={row.layout.gap} onChange={(event) => updateSectionRow(row.id, { layout: { gap: event.target.value } })}>{spacingOptions.filter((item) => item.value !== "none").map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}

      {selected.type === "column" && selectedColumn && (
        <div className="inspector-group">
          <h3>Column</h3>
          <label>Alignment<select value={selectedColumn.layout.align} onChange={(event) => updateSelectedColumn({ layout: { align: event.target.value } })}>{alignmentOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        </div>
      )}

      {selected.type === "element" && selectedElement && (
        <div className="inspector-group">
          <h3>Element</h3>
          <label>Name<input value={selectedElement.name} onChange={(event) => updateSelectedElement({ name: event.target.value })} /></label>
          {carouselElementTypes.has(selectedElement.type) && (
            <p className="builder-note">
              Use one slide per block: title, description, image URL. Separate slides with a blank line.
            </p>
          )}
          <label>Content<textarea value={selectedElement.content} onChange={(event) => updateSelectedElement({ content: event.target.value })} /></label>
          <label>Text color<input type="color" value={selectedElement.styles.color || "#1a2744"} onChange={(event) => updateSelectedElement({ styles: { color: event.target.value } })} /></label>
          <label>Background<input type="color" value={selectedElement.styles.backgroundColor || "#ffffff"} onChange={(event) => updateSelectedElement({ styles: { backgroundColor: event.target.value } })} /></label>
          <label>Font size<input value={selectedElement.styles.fontSize || ""} placeholder="Example: 18px" onChange={(event) => updateSelectedElement({ styles: { fontSize: event.target.value } })} /></label>
          <label>Border radius<input value={selectedElement.styles.borderRadius || ""} placeholder="Example: 16px" onChange={(event) => updateSelectedElement({ styles: { borderRadius: event.target.value } })} /></label>
          <label>Text alignment<select value={selectedElement.styles.textAlign || "left"} onChange={(event) => updateSelectedElement({ styles: { textAlign: event.target.value } })}>{alignmentOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          {selectedElement.mode !== "free" && (
            <>
              <label>
                Component width
                <select
                  value={
                    selectedElement.styles.width ||
                    (carouselElementTypes.has(selectedElement.type) ? "100%" : "auto")
                  }
                  onChange={(event) => {
                    const width = event.target.value === "auto" ? "" : event.target.value;
                    updateSelectedElement({
                      styles: {
                        width,
                        ...(width === "100%" ? { alignSelf: "stretch" } : {}),
                      },
                    });
                  }}
                >
                  {!carouselElementTypes.has(selectedElement.type) && (
                    <option value="auto">Auto - content width</option>
                  )}
                  <option value="100%">Full - 100%</option>
                  <option value="70%">Comfort - 70%</option>
                  <option value="75%">Wide - 75%</option>
                  <option value="50%">Half - 50%</option>
                  <option value="33.333%">Third - 33%</option>
                  <option value="25%">Quarter - 25%</option>
                </select>
              </label>
              <label>
                Minimum height
                <input
                  value={selectedElement.styles.minHeight || ""}
                  placeholder="Example: 320px"
                  onChange={(event) => updateSelectedElement({ styles: { minHeight: event.target.value } })}
                />
              </label>
              <label>
                Component position
                <select
                  value={getElementAlignControlValue(selectedElement.styles.alignSelf)}
                  onChange={(event) => updateSelectedElementPlacement(event.target.value)}
                >
                  <option value="auto">Default</option>
                  <option value="flex-start">Left</option>
                  <option value="center">Center</option>
                  <option value="flex-end">Right</option>
                  <option value="stretch">Stretch full width</option>
                </select>
              </label>
              {carouselElementTypes.has(selectedElement.type) && (
                <>
                  <label>
                    Carousel height
                    <select
                      value={selectedElement.styles["--carousel-height"] || ""}
                      onChange={(event) =>
                        updateSelectedElement({
                          styles: { "--carousel-height": event.target.value },
                        })
                      }
                    >
                      <option value="">Default</option>
                      <option value="260px">Small - 260px</option>
                      <option value="340px">Medium - 340px</option>
                      <option value="420px">Large - 420px</option>
                      <option value="520px">Tall - 520px</option>
                    </select>
                  </label>
                  <label>
                    Auto scroll
                    <select
                      value={selectedElement.autoScroll ? "on" : "off"}
                      onChange={(event) =>
                        updateSelectedElement({ autoScroll: event.target.value === "on" })
                      }
                    >
                      <option value="on">On</option>
                      <option value="off">Off</option>
                    </select>
                  </label>
                  <label>
                    Auto scroll timing
                    <input
                      type="number"
                      min="1"
                      step="0.5"
                      value={(Number(selectedElement.autoScrollMs) || 4000) / 1000}
                      onChange={(event) =>
                        updateSelectedElement({
                          autoScrollMs: Math.max(1000, Number(event.target.value || 4) * 1000),
                        })
                      }
                    />
                  </label>
                  {selectedElement.type === "circularGallery" && (
                    <label>
                      Gallery depth
                      <select
                        value={selectedElement.styles["--gallery-depth"] || ""}
                        onChange={(event) =>
                          updateSelectedElement({
                            styles: { "--gallery-depth": event.target.value },
                          })
                        }
                      >
                        <option value="">Default</option>
                        <option value="220px">Tight</option>
                        <option value="300px">Medium</option>
                        <option value="360px">Deep</option>
                        <option value="440px">Wide ring</option>
                      </select>
                    </label>
                  )}
                </>
              )}
            </>
          )}

          {(selectedElement.type === "formBlock" || selectedElement.type === "responsesTable") && (
            <label>Connected form<select value={selectedElement.connectedFormId || ""} onChange={(event) => updateSelectedElement({ connectedFormId: event.target.value })}>{project.forms.map((form) => <option key={form.id} value={form.id}>{form.title}</option>)}</select></label>
          )}

          {selectedElement.type === "image" && (
            <button type="button" className="upload-image-button" onClick={showAssetUploadUnavailable}>Upload image</button>
          )}

          {selectedElement.mode === "free" && (
            <details open>
              <summary>Size and position: {viewport}</summary>
              {[
                ["x", "Left"],
                ["y", "Top"],
                ["width", "Width"],
                ["height", "Height"],
              ].map(([key, label]) => (
                <label key={key}>
                  {label} (% of full canvas)
                  <input
                    type="number"
                    min="-100"
                    max="200"
                    value={getElementPositionPercent(key)}
                    onChange={(event) => updateElementPositionPercent(key, event.target.value)}
                  />
                </label>
              ))}
            </details>
          )}

          {selectedElement.type === "button" && (
            <details>
              <summary>Interaction</summary>
              <label>Action<select value={selectedElement.action?.type || "none"} onChange={(event) => updateSelectedElement({ action: { type: event.target.value } })}>
                <option value="none">None</option>
                <option value="goToPage">Go to page</option>
                <option value="openUrl">Open URL</option>
                <option value="showMessage">Show message</option>
              </select></label>
              {selectedElement.action?.type === "goToPage" && (
                <label>Target page<select value={selectedElement.action?.pageId || ""} onChange={(event) => updateSelectedElement({ action: { pageId: event.target.value } })}>{project.pages.map((page) => <option key={page.id} value={page.id}>{page.name}</option>)}</select></label>
              )}
              {selectedElement.action?.type === "openUrl" && (
                <label>URL<input value={selectedElement.action?.url || ""} onChange={(event) => updateSelectedElement({ action: { url: event.target.value } })} /></label>
              )}
              {selectedElement.action?.type === "showMessage" && (
                <label>Message<input value={selectedElement.action?.message || ""} onChange={(event) => updateSelectedElement({ action: { message: event.target.value } })} /></label>
              )}
            </details>
          )}

          <details open>
            <summary>Element actions</summary>
            <div className="element-action-grid">
              <button type="button" onClick={duplicateSelectedElement}>Duplicate</button>
              <button type="button" onClick={() => moveSelectedElement("up")}>Move up</button>
              <button type="button" onClick={() => moveSelectedElement("down")}>Move down</button>
            </div>
            {findElementLocation(selectedElement.id)?.isFree === false && (
              <label>Move this element to<select value={findElementLocation(selectedElement.id)?.columnId || ""} onChange={(event) => moveSelectedElementToColumn(event.target.value)}>
                {activePage?.sections.flatMap((section) =>
                  (section.rows || []).flatMap((row, rowIndex) =>
                    row.columns.map((column, columnIndex) => (
                      <option key={column.id} value={column.id}>
                        {getColumnOptionLabel(section, row, rowIndex, columnIndex)}
                      </option>
                    ))
                  )
                )}
              </select></label>
            )}
          </details>

          <button type="button" className="danger-button" onClick={deleteSelectedElement}>Delete Element</button>
        </div>
      )}
      </div>
    </aside>
  );

  const formatSavedValue = (value) => {
    if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
    if (value === true) return "Yes";
    if (value === false) return "No";
    if (value === null || value === undefined || value === "") return "—";
    if (typeof value === "object" && value.name) return value.name;
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  };
  const renderDataTab = () => (
  <DataAnalysisWorkspace
    project={project}
    lang={lang}
    user={user}
    selectForm={selectForm}
    setActiveTab={setActiveTab}
    getFormFields={getFormFields}
  />
);

  const renderFormsTab = () => {
    const commonFieldTypes = [
      "shortText",
      "paragraph",
      "email",
      "phone",
      "url",
      "number",
      "date",
      "time",
      "dropdown",
      "radio",
      "checkboxes",
      "yesNo",
      "linearScale",
      "rating",
      "file",
    ];
    const placements = activeForm ? getFormPlacements(activeForm.id) : [];

    return (
    <div className="workspace-page forms-google-workspace">
      <div className="workspace-header">
        <div>
          <h2>Forms</h2>
          <p>Build forms like a document, preview them live, and place them on any page.</p>
        </div>
        <button type="button" onClick={addForm}>+ Form</button>
      </div>

      <div className="forms-top-stack">
        <section className="object-list google-form-list forms-form-strip" aria-label="Forms">
          {project.forms.map((form) => (
            <button key={form.id} type="button" className={activeForm?.id === form.id ? "active" : ""} onClick={() => selectForm(form.id)}>
              <strong>{form.title}</strong>
              <span>{getFormFields(form).length} fields / {form.responses.length} responses</span>
            </button>
          ))}
        </section>

        <section className="forms-settings-top google-form-actions">
          <section className="quiz-settings-panel quiz-settings-summary">
            <div className="quiz-settings-header">
              <div>
                <h3>Quiz Settings</h3>
                <p>{activeForm?.mode === "quiz" ? "Quiz mode is enabled for this form." : "Keep this as a form or turn it into a timed quiz."}</p>
              </div>
              <label className="checkbox-control">
                <input
                  type="checkbox"
                  checked={activeForm?.mode === "quiz"}
                  onChange={(event) =>
                    updateActiveForm((form) => ({
                      ...form,
                      mode: event.target.checked ? "quiz" : "form",
                      quiz: getQuizSettings(form),
                    }))
                  }
                />
                Quiz
              </label>
            </div>
            <button type="button" className="quiz-options-trigger" onClick={() => setQuizOptionsOpen(true)}>
              Quiz options
            </button>
          </section>

          <section className="form-placement-panel">
            <h3>Place Form</h3>
            <label>
              Page
              <select value={project.activePageId || ""} onChange={(event) => selectPage(event.target.value)}>
                {project.pages.map((page) => <option key={page.id} value={page.id}>{page.name}</option>)}
              </select>
            </label>
            <div className="form-panel-actions">
              <button type="button" className="primary-action" onClick={() => addConnectedFormSectionToPage(activeForm?.id)}>
                Add to page
              </button>
              <button type="button" onClick={() => addConnectedResponsesSectionToPage(activeForm?.id)}>
                Add responses
              </button>
            </div>
            {placements.length > 0 && (
              <div className="connected-placement-list">
                <span>Placed on:</span>
                {placements.map((placement) => (
                  <button
                    type="button"
                    key={`${placement.pageId}_${placement.sectionName}`}
                    onClick={() => {
                      selectPage(placement.pageId);
                      setActiveTab("design");
                      setDesignPanel("Layers");
                    }}
                  >
                    {placement.pageName}
                  </button>
                ))}
              </div>
            )}
          </section>

          <section className="form-save-panel">
            <h3>Save Data</h3>
            <label>
              Save submissions to
              <select value={activeForm?.connectedCollectionId || ""} onChange={(event) => updateActiveForm((form) => ({ ...form, connectedCollectionId: event.target.value }))}>
                <option value="">Form submissions only</option>
                {project.collections.map((collection) => <option key={collection.id} value={collection.id}>{collection.name}</option>)}
              </select>
            </label>
            <label>
              Success message
              <textarea value={activeForm?.successMessage || ""} onChange={(event) => updateActiveForm((form) => ({ ...form, successMessage: event.target.value }))} />
            </label>
          </section>

          <details className="form-preview-panel">
            <summary>Preview</summary>
            {activeForm && renderConnectedForm(activeForm.id, { allowInteraction: true })}
          </details>
        </section>
      </div>

      <div className="google-form-layout">
        <main className="google-form-document">
          {activeForm && (
            <>
              <div className="google-form-title-card">
                <input className="google-form-title-input" value={activeForm.title} onChange={(event) => updateActiveForm((form) => ({ ...form, title: event.target.value }))} />
                <textarea className="google-form-description-input" value={activeForm.description} placeholder="Form description" onChange={(event) => updateActiveForm((form) => ({ ...form, description: event.target.value }))} />
              </div>

              <div className="google-add-strip">
                {commonFieldTypes.map((typeId) => {
                  const type = getFieldType(typeId);
                  return (
                    <button key={type.id} type="button" onClick={() => addFieldToForm(type.id)}>
                      + {type.label}
                    </button>
                  );
                })}
                <button type="button" className="add-section-control" onClick={addFormSection}>+ Section</button>
              </div>

              <div className="form-sections-stack">
                {getFormSections(activeForm).map((section, sectionIndex) => (
                  <section className="form-section-card google-section-card" key={section.id}>
                    <div className="google-section-header">
                      <input className="section-title-input" value={section.title} onChange={(event) => updateFormSection(section.id, { title: event.target.value })} />
                      <button type="button" className="danger-lite" disabled={getFormSections(activeForm).length <= 1} onClick={() => deleteFormSection(section.id)}>Delete section</button>
                    </div>
                    <textarea className="section-description-input" value={section.description || ""} placeholder="Section description" onChange={(event) => updateFormSection(section.id, { description: event.target.value })} />
                    {(section.fields || []).map((field) => (
                      <article className={`question-card google-question-card ${selected.id === field.id ? "active" : ""}`} key={field.id} onClick={() => setSelected({ type: "field", id: field.id })}>
                        <div className="question-main">
                          <div className="google-question-topline">
                            <input className="question-title-input" value={field.label} placeholder="Question" onChange={(event) => updateFormField(field.id, { label: event.target.value })} />
                            <select value={field.type} onChange={(event) => updateFormField(field.id, { type: event.target.value })}>
                              {fieldTypes.map((type) => <option key={type.id} value={type.id}>{type.label}</option>)}
                            </select>
                          </div>
                          <div className="question-secondary-grid">
                            <input value={field.helpText || ""} placeholder="Help text shown under the question" onChange={(event) => updateFormField(field.id, { helpText: event.target.value })} />
                            <input value={field.placeholder || ""} placeholder="Placeholder text" onChange={(event) => updateFormField(field.id, { placeholder: event.target.value })} />
                            <input value={field.defaultValue || ""} placeholder="Default answer" onChange={(event) => updateFormField(field.id, { defaultValue: event.target.value })} />
                          </div>
                          {["dropdown", "radio", "checkboxes", "status"].includes(field.type) && (
                            <textarea className="options-editor" value={(field.options || []).join("\n")} placeholder="One option per line" onChange={(event) => updateFormField(field.id, { options: splitLines(event.target.value) })} />
                          )}
                          {field.type === "linearScale" && (
                            <div className="scale-editor">
                              <label>From<input type="number" min="0" max="10" value={field.scaleMin || 1} onChange={(event) => updateFormField(field.id, { scaleMin: Number(event.target.value) })} /></label>
                              <label>To<input type="number" min="2" max="10" value={field.scaleMax || 5} onChange={(event) => updateFormField(field.id, { scaleMax: Number(event.target.value) })} /></label>
                              <label>Low label<input value={field.scaleMinLabel || ""} onChange={(event) => updateFormField(field.id, { scaleMinLabel: event.target.value })} /></label>
                              <label>High label<input value={field.scaleMaxLabel || ""} onChange={(event) => updateFormField(field.id, { scaleMaxLabel: event.target.value })} /></label>
                            </div>
                          )}
                          {field.type === "rating" && (
                            <label className="inline-setting">Max rating<input type="number" min="2" max="10" value={field.maxRating || 5} onChange={(event) => updateFormField(field.id, { maxRating: Number(event.target.value) })} /></label>
                          )}
                          {activeForm.mode === "quiz" && (
                            <div className="quiz-question-settings">
                              {renderQuizAnswerKeyEditor(field)}
                              <label>
                                Question time override (seconds)
                                <input
                                  type="number"
                                  min="0"
                                  value={Number(field.quizTimeLimitSec || 0)}
                                  placeholder="Use default"
                                  onChange={(event) => updateFormField(field.id, { quizTimeLimitSec: Math.max(0, Number(event.target.value || 0)) })}
                                />
                              </label>
                            </div>
                          )}
                        </div>
                        <div className="question-footer-actions">
                          <span>Question {sectionIndex + 1}.{(section.fields || []).findIndex((item) => item.id === field.id) + 1}</span>
                          <button type="button" onClick={(event) => { event.stopPropagation(); moveFormField(field.id, "up"); }}>Up</button>
                          <button type="button" onClick={(event) => { event.stopPropagation(); moveFormField(field.id, "down"); }}>Down</button>
                          <button type="button" onClick={(event) => { event.stopPropagation(); duplicateFormField(field.id); }}>Duplicate</button>
                          <label className="checkbox-control"><input type="checkbox" checked={field.required} onChange={(event) => updateFormField(field.id, { required: event.target.checked })} /> Required</label>
                          <button type="button" className="danger-lite" onClick={(event) => { event.stopPropagation(); deleteFormField(field.id); }}>Delete</button>
                        </div>
                      </article>
                    ))}
                    <button type="button" className="add-question-wide" onClick={() => addFieldToForm("shortText", section.id)}>+ Add question</button>
                  </section>
                ))}
              </div>
            </>
          )}
        </main>

      </div>
      {quizOptionsOpen && (
        <div className="quiz-drawer-backdrop" onClick={() => setQuizOptionsOpen(false)}>
          <aside className="quiz-options-drawer" aria-label="Quiz options" onClick={(event) => event.stopPropagation()}>
            <div className="quiz-drawer-header">
              <div>
                <span>Quiz features</span>
                <h3>Quiz Options</h3>
                <p>Control timing, focus mode, scoring, results, and retakes for this form.</p>
              </div>
              <button type="button" onClick={() => setQuizOptionsOpen(false)}>Close</button>
            </div>

            <div className="quiz-settings-grid quiz-drawer-grid">
              <label className="checkbox-control">
                <input
                  type="checkbox"
                  checked={activeForm?.mode === "quiz"}
                  onChange={(event) =>
                    updateActiveForm((form) => ({
                      ...form,
                      mode: event.target.checked ? "quiz" : "form",
                      quiz: getQuizSettings(form),
                    }))
                  }
                />
                Enable quiz mode
              </label>
              <label className="checkbox-control">
                <input
                  type="checkbox"
                  checked={Boolean(getQuizSettings(activeForm).lockScreen)}
                  onChange={(event) => updateActiveFormQuiz({ lockScreen: event.target.checked })}
                />
                Lock screen in focus mode
              </label>
              <label>
                Total time limit (minutes)
                <input
                  type="number"
                  min="0"
                  value={Math.round(Number(getQuizSettings(activeForm).totalTimeLimitSec || 0) / 60)}
                  onChange={(event) => updateActiveFormQuiz({ totalTimeLimitSec: Math.max(0, Number(event.target.value || 0) * 60) })}
                />
              </label>
              <label>
                Default time per question (seconds)
                <input
                  type="number"
                  min="0"
                  value={Number(getQuizSettings(activeForm).questionTimeLimitSec || 0)}
                  onChange={(event) => updateActiveFormQuiz({ questionTimeLimitSec: Math.max(0, Number(event.target.value || 0)) })}
                />
              </label>
              <label>
                Scoring
                <select
                  value={getQuizSettings(activeForm).scoring}
                  onChange={(event) => updateActiveFormQuiz({ scoring: event.target.value })}
                >
                  <option value="automatic">Automatic</option>
                  <option value="manual">Manual review</option>
                  <option value="completion">Completion only</option>
                </select>
              </label>
              <label>
                Required passing score (%)
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={Number(getQuizSettings(activeForm).passingScore || 0)}
                  onChange={(event) => updateActiveFormQuiz({ passingScore: Math.min(100, Math.max(0, Number(event.target.value || 0))) })}
                />
              </label>
              <label className="checkbox-control">
                <input
                  type="checkbox"
                  checked={Boolean(getQuizSettings(activeForm).showResults)}
                  onChange={(event) => updateActiveFormQuiz({ showResults: event.target.checked })}
                />
                Show results after submit
              </label>
              <label className="checkbox-control">
                <input
                  type="checkbox"
                  checked={Boolean(getQuizSettings(activeForm).allowRetakes)}
                  onChange={(event) => updateActiveFormQuiz({ allowRetakes: event.target.checked })}
                />
                Allow retakes
              </label>
              <label>
                Max retakes
                <input
                  type="number"
                  min="0"
                  value={Number(getQuizSettings(activeForm).maxRetakes || 0)}
                  onChange={(event) => updateActiveFormQuiz({ maxRetakes: Math.max(0, Number(event.target.value || 0)) })}
                />
              </label>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
  };

  const renderWorkflowsTab = () => (
    <PageBuilderWorkflowsTab
      project={project}
      activeWorkflow={activeWorkflow}
      workflowStepTypes={workflowStepTypes}
      selectWorkflow={selectWorkflow}
      addWorkflow={addWorkflow}
      addWorkflowStep={addWorkflowStep}
      updateActiveWorkflow={updateActiveWorkflow}
      updateWorkflowStep={updateWorkflowStep}
      deleteWorkflowStep={deleteWorkflowStep}
    />
  );

  const renderUsersTab = () => (
    <PageBuilderUsersTab
      project={project}
      selectedRole={selectedRole}
      permissionGroups={permissionGroups}
      addUser={addUser}
      addRole={addRole}
      updateUser={updateUser}
      updateRole={updateRole}
      deleteUser={deleteUser}
      setSelected={setSelected}
    />
  );

  const renderThemeTab = () => (
    <PageBuilderThemeTab
      project={project}
      updateProject={updateProject}
      setThemeMode={setThemeMode}
    />
  );

  const renderResponsesTab = () => (
    <BuilderResponsesPage
      project={project}
      builderProjectId={builderProjectRecord?.id || ""}
      lang={lang}
      user={user}
      activeForm={activeForm}
      selectForm={selectForm}
      setActiveTab={setActiveTab}
      getFormFields={getFormFields}
      formatSavedValue={formatSavedValue}
      showToast={showToast}
    />
  );

  const renderPublishTab = () => (
    <PageBuilderPublishTab
      project={project}
      saveProject={saveProject}
      loadProject={loadProject}
      exportProject={exportProject}
      publishProject={publishProject}
    />
  );

  const renderActiveTab = () => {
    if (activeTab === "design") return renderDesignTab();
    if (activeTab === "data") return renderDataTab();
    if (activeTab === "forms") return renderFormsTab();
    if (activeTab === "responses") return renderResponsesTab();
    if (activeTab === "workflows") return renderWorkflowsTab();
    if (activeTab === "users") return renderUsersTab();
    if (activeTab === "theme") return renderThemeTab();
    if (activeTab === "publish") return renderPublishTab();
    return renderDesignTab();
  };

  const builderCopy = builderWorkspaceCopy[lang] || builderWorkspaceCopy.en;

  const renderWorkspaceNavigator = () => (
    <nav className="workspace-tabs" aria-label={lang === "ar" ? "مساحات عمل المنشئ" : "Builder workspaces"}>
      {builderTabs
        .filter((tab) =>
          visibleTabIds
            ? visibleTabIds.includes(tab.id)
            : !mainBuilderHiddenTabs.includes(tab.id)
        )
        .map((tab) => (
        <button
          type="button"
          key={tab.id}
          className={activeTab === tab.id ? "active" : ""}
          onClick={() => setActiveTab(tab.id)}
        >
          {builderCopy.tabs[tab.id]?.label || tab.label}
        </button>
      ))}
    </nav>
  );

  const activeHelper =
    builderCopy.tabs[activeTab]?.helper ||
    builderTabs.find((tab) => tab.id === activeTab)?.helper ||
    "";
  const templateCopy = templateModalText[templateLang] || templateModalText.en;
  const projectDisplayName =
    builderCopy.projectNames[project.name] ||
    project.name;
  const mobileCopy =
    (mobileBlockerCopy[lang] || mobileBlockerCopy.en)[activeTab] ||
    (mobileBlockerCopy[lang] || mobileBlockerCopy.en).default;
  const getStarterDisplay = (starter) => {
    if (templateLang !== "ar") return starter;
    const translated = starterArabicText[starter.id] || {};
    return {
      ...starter,
      ...translated,
      tags: translated.tags || starter.tags,
    };
  };

  return (
    <div
      className={getPageBuilderThemeClassName({
        mode: project.theme?.mode || "light",
        preview,
      })}
      style={getPageBuilderThemeVars(project.theme)}
      onMouseMove={handleMouseMove}
      onMouseUp={() => setDragState(null)}
      onMouseLeave={() => setDragState(null)}
    >
      <div className="builder-desktop-shell">
        <PageBuilderTopbar
          project={project}
          displayName={projectDisplayName}
          activeHelper={activeHelper}
          hideWorkspaceTabs={hideWorkspaceTabs}
          preview={preview}
          demoMode={demoMode}
          copy={builderCopy.topbar}
          activeTopbarAction={activeTopbarAction}
          setActiveTopbarAction={setActiveTopbarAction}
          setModal={setModal}
          setPreview={setPreview}
          saveProject={saveProject}
          publishProject={publishProject}
        />

        <PageBuilderSubbar
          preview={preview}
          hideWorkspaceTabs={hideWorkspaceTabs}
          viewports={viewports}
          viewport={viewport}
          setViewport={setViewport}
          renderWorkspaceNavigator={renderWorkspaceNavigator}
        />

        {renderActiveTab()}
      </div>

      <div className="builder-mobile-blocker">
        <div>
          <h2>{mobileCopy.title}</h2>
          <p>{mobileCopy.message}</p>
        </div>
      </div>

      {modal === "section" && (
        <div className="builder-modal-backdrop" onClick={() => setModal(null)}>
          <div className="builder-modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h2>Add Section</h2>
              <button type="button" onClick={() => setModal(null)}>Close</button>
            </div>
            <div className="section-library-grid">
              {sectionLibrary.map((section) => (
                <button type="button" className="section-card" key={section.id} onClick={() => addSection(section.create)}>
                  <span>{section.category}</span>
                  <strong>{section.title}</strong>
                  <p>{section.description}</p>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {modal === "starter" && (
        <div className="builder-modal-backdrop" onClick={() => setModal(null)}>
          <div
            className="builder-modal wide template-picker-modal"
            dir={templateLang === "ar" ? "rtl" : "ltr"}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <span className="modal-eyebrow">{templateCopy.eyebrow}</span>
                <h2>{templateCopy.title}</h2>
                <p>{templateCopy.description}</p>
              </div>
              <button type="button" onClick={() => setModal(null)}>{templateCopy.close}</button>
            </div>
            <div className="starter-grid">
              {starterSystems.map((starter) => {
                const displayStarter = getStarterDisplay(starter);

                return (
                <button type="button" className="starter-card" key={starter.id} onClick={() => applyStarter(starter.id)}>
                  {displayStarter.category && <span>{displayStarter.category}</span>}
                  <strong>{displayStarter.title}</strong>
                  <p>{displayStarter.subtitle}</p>
                  {Array.isArray(displayStarter.tags) && displayStarter.tags.length > 0 && (
                    <em>
                      {displayStarter.tags.map((tag) => (
                        <i key={tag}>{tag}</i>
                      ))}
                    </em>
                  )}
                </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {toast && <div className="builder-toast">{toast}</div>}
      {liveSitePath && (
        <a
          className="builder-live-site-link"
          href={liveSitePath}
          target="_blank"
          rel="noreferrer"
        >
          Open live site
        </a>
      )}
    </div>
  );
}





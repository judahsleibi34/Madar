import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, ArrowLeft, ArrowRight, Check, ChevronDown, Download, Eye, Trash2, X } from "lucide-react";

import { uiText } from "../constants/uiText";
import { analysisGroups } from "../constants/analysisConfig";
import { API_URL, getFriendlyExternalError, readApiResponse } from "../utils/api";
import { cleanObject, escapeCsvValue } from "../utils/formatters";
import { getMissingRequiredParams } from "../utils/validation";
import { apiFetch } from "../../../../utils/apiClient";

import Stepper from "./Stepper";
import DataSourceStep from "./DataSourceStep";
import DatasetReviewStep from "./DatasetReviewStep";
import PrepareDataStep from "./PrepareDataStep";
import ReportBuilderStep from "./ReportBuilderStep";
import AssistantPanel from "./AssistantPanel";
import ReportCanvas from "./ReportCanvas";
import PageVerticalSlider from "./PageVerticalSlider";
import Field from "./Field";

const chartTypes = [
  { id: "bar", label: "Bar" },
  { id: "line", label: "Line" },
  { id: "scatter", label: "Scatter" },
  { id: "histogram", label: "Histogram" },
  { id: "box", label: "Box" },
  { id: "violin", label: "Violin" },
  { id: "count", label: "Frequency" },
  { id: "pie", label: "Pie" },
  { id: "heatmap", label: "Heatmap" },
];

const paletteOptions = [
  "viridis",
  "magma",
  "plasma",
  "crest",
  "rocket",
  "deep",
  "muted",
  "pastel",
];

const palettePreviewColors = {
  viridis: ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"],
  magma: ["#000004", "#57106e", "#bc3754", "#f98e09", "#fcfdbf"],
  plasma: ["#0d0887", "#7e03a8", "#cc4778", "#f89540", "#f0f921"],
  crest: ["#2c115f", "#1f6f8b", "#3aa77f", "#9bd36a", "#f2f0a1"],
  rocket: ["#03051a", "#711f57", "#cb1b4f", "#f26b43", "#f6b48f"],
  deep: ["#4c72b0", "#dd8452", "#55a868", "#c44e52", "#8172b3"],
  muted: ["#4878d0", "#ee854a", "#6acc64", "#d65f5f", "#956cb4"],
  pastel: ["#a1c9f4", "#ffb482", "#8de5a1", "#ff9f9b", "#d0bbff"],
};

const fontFamilyOptions = [
  "DejaVu Sans",
  "Arial",
  "Verdana",
  "Tahoma",
  "Times New Roman",
];

const getVisualizationPlots = (visualizationResult) => {
  if (!visualizationResult) return [];
  if (Array.isArray(visualizationResult.plots)) return visualizationResult.plots;
  return [visualizationResult];
};

const getVisualizationUrl = (plotResult, key) => {
  const url = plotResult?.[key] || "";
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return url;
  return `${API_URL}${url}`;
};

const userSafeErrorMessage = (
  message,
  fallback = "Something went wrong. Please try again."
) => {
  const text = String(message || "").trim();
  if (!text) return fallback;

  const looksLikeImplementationError =
    /\b(set[A-Z]\w*|get[A-Z]\w*|use[A-Z]\w*|[A-Za-z_$][\w$]*\(\))\b/.test(text) ||
    /\b(is not defined|undefined is not|Cannot read properties|TypeError|ReferenceError|Traceback|HTTPException)\b/i.test(text) ||
    /frontend[\\/]|backend[\\/]|\.jsx?:\d+|\.py:\d+/.test(text);

  return looksLikeImplementationError ? fallback : text;
};

const needsXColumn = (chartType) => !["heatmap"].includes(chartType);
const needsYColumn = (chartType) =>
  ["bar", "line", "scatter", "box", "violin", "pie"].includes(chartType);
const axisLabelsDisabled = (chartType) => ["pie", "heatmap"].includes(chartType);
const toArray = (value) => (Array.isArray(value) ? value : value ? [value] : []);
const hasColumnValue = (value) => toArray(value).filter(Boolean).length > 0;
const arabicDigitMap = {
  "٠": "0",
  "١": "1",
  "٢": "2",
  "٣": "3",
  "٤": "4",
  "٥": "5",
  "٦": "6",
  "٧": "7",
  "٨": "8",
  "٩": "9",
  "۰": "0",
  "۱": "1",
  "۲": "2",
  "۳": "3",
  "۴": "4",
  "۵": "5",
  "۶": "6",
  "۷": "7",
  "۸": "8",
  "۹": "9",
};
const normalizeNumericText = (value) =>
  String(value ?? "")
    .trim()
    .replace(/[٠-٩۰-۹]/g, (digit) => arabicDigitMap[digit] || digit)
    .replace(/[%$€£₪،,\s]/g, "");
const isNumericLikeValue = (value) => {
  if (value === null || value === undefined || value === "") return false;
  if (typeof value === "number") return Number.isFinite(value);

  const normalized = normalizeNumericText(value);
  if (!normalized) return false;

  return Number.isFinite(Number(normalized));
};
const singleVariableCharts = ["histogram", "count"];
const singlePairCharts = ["pie", "violin"];
const multiSeriesCharts = ["bar", "line", "scatter", "box"];
const categoryColorCharts = ["bar", "box", "violin", "count", "pie"];
const chartRelationshipOptions = {
  bar: [
    {
      value: "1:1",
      label: "One category + one value",
      hint: "Use one group column and one value column, like Region and Sales.",
    },
    {
      value: "1:M",
      label: "One category + many values",
      hint: "Use one group column with several value columns, like Month with Sales, Cost, and Profit.",
    },
    {
      value: "M:M",
      label: "Matched category/value pairs",
      hint: "Choose pairs in the same order, like Month A with Sales A, then Month B with Sales B.",
    },
  ],
  line: [
    {
      value: "1:1",
      label: "One timeline + one value",
      hint: "Use one time or order column and one numeric value column.",
    },
    {
      value: "1:M",
      label: "One timeline + many values",
      hint: "Use one shared time or order column with several numeric value columns.",
    },
  ],
  scatter: [
    {
      value: "1:1",
      label: "One X + one Y",
      hint: "Use one column for horizontal position and one column for vertical position.",
    },
    {
      value: "1:M",
      label: "One X + many Y values",
      hint: "Use one shared X column with several Y columns.",
    },
    {
      value: "M:M",
      label: "Matched X/Y pairs",
      hint: "Choose X and Y columns in pairs, in the same order.",
    },
  ],
  histogram: [
    {
      value: "1:1",
      label: "One column",
      hint: "Pick one column to show how its values are distributed.",
    },
  ],
  box: [
    {
      value: "1:1",
      label: "One group + one value",
      hint: "Use one group column and one numeric value column.",
    },
    {
      value: "1:M",
      label: "One group + many values",
      hint: "Use one group column with several numeric value columns.",
    },
  ],
  violin: [
    {
      value: "1:1",
      label: "One group + one value",
      hint: "Use one group column and one numeric value column.",
    },
  ],
  count: [
    {
      value: "1:1",
      label: "One column",
      hint: "Pick one column to count how often each answer appears.",
    },
  ],
  pie: [
    {
      value: "1:1",
      label: "One label + one value",
      hint: "Use one label column and one numeric value column.",
    },
  ],
  heatmap: [
    {
      value: "M:M",
      label: "Many numeric columns",
      hint: "Pick two or more numeric columns to compare how they move together.",
    },
  ],
};
const getRelationshipOptions = (chartType) =>
  chartRelationshipOptions[chartType] || chartRelationshipOptions.bar;
const getDefaultComparisonMode = (chartType) =>
  getRelationshipOptions(chartType)[0]?.value || "1:1";
const normalizeComparisonMode = (chartType, comparisonMode) => {
  const options = getRelationshipOptions(chartType);
  return options.some((option) => option.value === comparisonMode)
    ? comparisonMode
    : getDefaultComparisonMode(chartType);
};
const getRelationshipOption = (chartType, comparisonMode) => {
  const options = getRelationshipOptions(chartType);
  const normalizedMode = normalizeComparisonMode(chartType, comparisonMode);
  return options.find((option) => option.value === normalizedMode) || options[0];
};
const supportsUngroupedCategoryColors = (chartType) =>
  ["bar", "box", "violin", "count", "pie"].includes(chartType);
const supportsHueGrouping = (chartType) =>
  ["bar", "line", "scatter", "histogram", "box", "violin", "count"].includes(
    chartType
  );
const getSeriesCount = (plot) => {
  if (!plot || !multiSeriesCharts.includes(plot.chartType)) return 1;
  const activeComparisonMode = normalizeComparisonMode(
    plot.chartType,
    plot.comparisonMode
  );
  if (activeComparisonMode === "1:M") {
    return Math.max(1, toArray(plot.yColumns).filter(Boolean).length);
  }
  if (activeComparisonMode === "M:M") {
    return Math.max(1, toArray(plot.yColumns).filter(Boolean).length);
  }
  return 1;
};

const getPalettePreview = (palette, count) => {
  const baseColors = palettePreviewColors[palette] || palettePreviewColors.viridis;
  const safeCount = Math.max(1, Number(count) || 1);

  const hexToRgb = (hex) => {
    const value = String(hex || "").replace("#", "");
    const normalized =
      value.length === 3
        ? value
            .split("")
            .map((char) => `${char}${char}`)
            .join("")
        : value.padEnd(6, "0").slice(0, 6);
    return [
      parseInt(normalized.slice(0, 2), 16),
      parseInt(normalized.slice(2, 4), 16),
      parseInt(normalized.slice(4, 6), 16),
    ];
  };

  const rgbToHex = ([red, green, blue]) =>
    `#${[red, green, blue]
      .map((channel) =>
        Math.round(Math.max(0, Math.min(255, channel)))
          .toString(16)
          .padStart(2, "0")
      )
      .join("")}`;

  const mixColors = (start, end, amount) => {
    const startRgb = hexToRgb(start);
    const endRgb = hexToRgb(end);
    return rgbToHex(
      startRgb.map((channel, index) => channel + (endRgb[index] - channel) * amount)
    );
  };

  return Array.from({ length: safeCount }, (_, index) => {
    if (safeCount === 1) return baseColors[0];
    const position = (index / (safeCount - 1)) * (baseColors.length - 1);
    const leftIndex = Math.floor(position);
    const rightIndex = Math.min(baseColors.length - 1, leftIndex + 1);
    return mixColors(baseColors[leftIndex], baseColors[rightIndex], position - leftIndex);
  });
};

const isTrendColumn = (column) =>
  /(date|time|timestamp|year|month|quarter|week|day|period)/i.test(
    String(column || "")
  );

const shouldUseTrendGradient = (plot, xValue) => {
  if (!plot) return false;
  if (["heatmap", "box", "violin", "pie", "count", "histogram"].includes(plot.chartType)) {
    return true;
  }
  if (plot.chartType === "line") return true;
  if (!["bar", "scatter"].includes(plot.chartType)) return false;
  return toArray(xValue || plot.xColumns || plot.xColumn).some(isTrendColumn);
};

const getComparisonHint = (plot) => {
  return getRelationshipOption(plot.chartType, plot.comparisonMode)?.hint || "";
};

const validateVisualizationPlot = (plot, numericColumns = []) => {
  const chartType = plot?.chartType;
  const xColumns = toArray(plot?.xColumns).filter(Boolean);
  const xCount = xColumns.length;
  const yColumns = toArray(plot?.yColumns).filter(Boolean);
  const yCount = yColumns.length;
  const plotName = plot?.name || "this plot";
  const numericColumnSet = new Set(numericColumns);

  if (!plot) return "Choose a plot before generating.";
  const activeComparisonMode = normalizeComparisonMode(chartType, plot.comparisonMode);

  if (chartType === "heatmap") {
    const heatmapColumns = toArray(plot?.heatmapColumns).filter(Boolean);
    const nonNumericHeatmapColumns = heatmapColumns.filter(
      (column) => !numericColumnSet.has(column)
    );

    if (nonNumericHeatmapColumns.length) {
      return `${plotName} heatmap can only use numeric columns. Remove: ${nonNumericHeatmapColumns.join(", ")}.`;
    }

    return heatmapColumns.length >= 2
      ? ""
      : `${plotName} heatmap needs at least two numeric columns.`;
  }

  if (activeComparisonMode !== "M:M" && xCount > 1) {
    return `${plotName} has ${xCount} X columns selected. This relationship uses one X column.`;
  }

  if (singleVariableCharts.includes(chartType)) {
    return xCount >= 1 ? "" : `Choose one column for ${plotName}.`;
  }

  if (singlePairCharts.includes(chartType)) {
    return xCount === 1 && yCount === 1
      ? ""
      : `${plotName} needs one label/group column and one value column.`;
  }

  if (!multiSeriesCharts.includes(chartType)) {
    return "";
  }

  if (["line", "box"].includes(chartType)) {
    const nonNumericYColumns = yColumns.filter(
      (column) => !numericColumnSet.has(column)
    );

    if (nonNumericYColumns.length) {
      return `${plotName} needs numeric value columns. Remove: ${nonNumericYColumns.join(", ")}.`;
    }
  }

  if (chartType === "box" && xColumns.some((column) => yColumns.includes(column))) {
    return `${plotName} uses the same column for group and value. Choose a different value column, or clear the group column to show one distribution.`;
  }

  if (activeComparisonMode === "1:M") {
    return xCount === 1 && yCount >= 1
      ? ""
      : `${plotName} needs one X/group column and one or more value columns.`;
  }

  if (activeComparisonMode === "M:M") {
    if (xCount < 1 || yCount < 1) {
      return `${plotName} needs at least one X column and one Y column.`;
    }

    return xCount === yCount
      ? ""
      : `${plotName} needs the same number of X and Y columns. You selected ${xCount} X and ${yCount} Y.`;
  }

  return xCount === 1 && yCount === 1
    ? ""
    : `${plotName} needs one X column and one Y column.`;
};

const getFriendlyVisualizationError = (message) => {
  const text = String(message || "").trim();

  if (!text) return "Could not create the visualization. Please check the selected fields and chart type.";

  const lowerText = text.toLowerCase();
  const backendErrorPatterns = [
    "id_vars",
    "traceback",
    "keyerror",
    "valueerror",
    "indexerror",
    "cannot contain duplicate columns",
    "pandas",
    "seaborn",
  ];

  if (backendErrorPatterns.some((pattern) => lowerText.includes(pattern))) {
    return "Could not create the visualization. Check that the group/X column is not also selected as a value column, and that the selected value columns are numeric.";
  }

  return text;
};

const createVisualizationPlot = (index, columns = [], numericColumns = []) => ({
  id: `plot-${index}`,
  name: `Plot ${index}`,
  comparisonMode: "1:1",
  chartType: "bar",
  barOrientation: "vertical",
  xColumn: columns[0] || "",
  yColumn: numericColumns[0] || columns[1] || "",
  xColumns: columns[0] ? [columns[0]] : [],
  yColumns: numericColumns[0] ? [numericColumns[0]] : columns[1] ? [columns[1]] : [],
  heatmapColumns: numericColumns.slice(0, 6),
  seriesColors: {},
  categoryColors: {},
  categoryColorColumn: "",
  categoryColorValues: [],
  hueColumn: "",
  header: `Plot ${index}`,
  title: "",
  xLabel: "",
  yLabel: "",
  palette: "viridis",
  useSingleColor: false,
  useGradient: "auto",
  color: "#8f2a1f",
  fontFamily: "DejaVu Sans",
  titleFontSize: 18,
  labelFontSize: 12,
  tickFontSize: 10,
  legendFontSize: 10,
  width: 10,
  height: 6,
});

const DATA_WORKSPACE_CACHE_VERSION = 1;
const DATA_WORKSPACE_CACHE_TTL_MS = 24 * 60 * 60 * 1000;

const getDataWorkspaceCacheKey = (user, project) => {
  const userId = user?.id || user?.email || "anonymous";
  const projectId = project?.id || project?.slug || project?.name || "default";
  return `madar:data-workspace:${userId}:${projectId}:v${DATA_WORKSPACE_CACHE_VERSION}`;
};

const safeReadDataWorkspaceCache = (storageKey) => {
  if (typeof window === "undefined") return null;

  try {
    const rawValue = window.localStorage.getItem(storageKey);
    if (!rawValue) return null;

    const cachedValue = JSON.parse(rawValue);
    const savedAt = Number(cachedValue?.savedAt || 0);
    const isExpired = Date.now() - savedAt > DATA_WORKSPACE_CACHE_TTL_MS;

    if (isExpired || !cachedValue?.dataset?.file_path) {
      window.localStorage.removeItem(storageKey);
      return null;
    }

    return cachedValue;
  } catch {
    window.localStorage.removeItem(storageKey);
    return null;
  }
};

const safeWriteDataWorkspaceCache = (storageKey, payload) => {
  if (typeof window === "undefined") return;

  try {
    window.localStorage.setItem(
      storageKey,
      JSON.stringify({
        ...payload,
        savedAt: Date.now(),
        version: DATA_WORKSPACE_CACHE_VERSION,
      })
    );
  } catch {
    // localStorage can be full or blocked; the app should keep working without cache.
  }
};

const safeRemoveDataWorkspaceCache = (storageKey) => {
  if (typeof window === "undefined") return;

  try {
    window.localStorage.removeItem(storageKey);
  } catch {
    // Ignore storage failures.
  }
};

const getCacheableDataset = (dataset) => {
  if (!dataset?.file_path) return null;

  return {
    file_path: dataset.file_path,
    original_filename: dataset.original_filename || dataset.file_path,
    rows: dataset.rows,
    columns: Array.isArray(dataset.columns) ? dataset.columns : [],
    preview: Array.isArray(dataset.preview) ? dataset.preview.slice(0, 100) : [],
  };
};

const getRestorableDataWorkspaceStep = (step) =>
  ["review", "prepare", "visualization"].includes(step) ? step : "review";

export default function DataAnalysisWorkspace({
  lang = "en",
  project,
  user = null,
  getFormFields = () => [],
  selectForm,
  setActiveTab,
}) {
  const activeLang = lang === "ar" ? "ar" : "en";
  const isArabic = activeLang === "ar";
  const t = uiText[activeLang];
  const dataWorkspaceCacheKey = getDataWorkspaceCacheKey(user, project);
  const cachedWorkspace = useMemo(
    () => safeReadDataWorkspaceCache(dataWorkspaceCacheKey),
    [dataWorkspaceCacheKey]
  );

  const userApiPath = (path) => {
    if (!user?.id) {
      throw new Error(t.sessionExpired || "Your session has expired.");
    }

    return `${API_URL}/users/${encodeURIComponent(user.id)}${path}`;
  };

  const availableForms = project?.forms || [];
  const firstFormWithResponses =
    availableForms.find((form) => form.responses?.length) || availableForms[0];

  const [currentStep, setCurrentStep] = useState(() =>
    cachedWorkspace?.dataset
      ? getRestorableDataWorkspaceStep(cachedWorkspace.currentStep)
      : "source"
  );
  const [sourceMode, setSourceMode] = useState(
    () => cachedWorkspace?.sourceMode || "forms"
  );
  const [selectedFormId, setSelectedFormId] = useState(
    () => cachedWorkspace?.selectedFormId || firstFormWithResponses?.id || ""
  );
  const [dataset, setDataset] = useState(() => cachedWorkspace?.dataset || null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [externalUrl, setExternalUrl] = useState(
    () => cachedWorkspace?.externalUrl || ""
  );
  const [inspection, setInspection] = useState(null);
  const [inspectionCache, setInspectionCache] = useState({});
  const [analysisResult, setAnalysisResult] = useState(null);
  const [assistQuestion, setAssistQuestion] = useState("");
  const [assistResult, setAssistResult] = useState(null);
  const [analysisError, setAnalysisError] = useState("");
  const [flowToast, setFlowToast] = useState("");
  const [visualizationError, setVisualizationError] = useState("");
  const [visualizationSuccess, setVisualizationSuccess] = useState("");
  const [visualizationNotice, setVisualizationNotice] = useState("");
  const [isVisualizationChecking, setIsVisualizationChecking] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const [reportOptions, setReportOptions] = useState(() => ({
    title: "",
    includeSummary: true,
    includeKpis: true,
    includeInsights: true,
    includeTables: true,
    includeCharts: true,
    includeWarnings: true,
    ...(cachedWorkspace?.reportOptions || {}),
  }));
  const [isVisualizationSettingsOpen, setIsVisualizationSettingsOpen] =
    useState(false);
  const [visualizationPlots, setVisualizationPlots] = useState(() =>
    Array.isArray(cachedWorkspace?.visualizationPlots) &&
    cachedWorkspace.visualizationPlots.length
      ? cachedWorkspace.visualizationPlots
      : [createVisualizationPlot(1)]
  );
  const [visualizationResultsByPlot, setVisualizationResultsByPlot] = useState({});
  const [visualizationPreview, setVisualizationPreview] = useState(null);
  const [activeVisualizationPlotId, setActiveVisualizationPlotId] = useState(
    () => cachedWorkspace?.activeVisualizationPlotId || "plot-1"
  );
  const [openAxisDropdown, setOpenAxisDropdown] = useState("");
  const activeColorInputRef = useRef(null);
  const visualizationNoticeRequestRef = useRef(0);
  const visualizationProfileCacheRef = useRef({});

  const [cleaning, setCleaning] = useState(() => ({
    trimText: true,
    lowercaseText: false,
    removeDuplicates: false,
    removeMissingRows: false,
    fillMissing: false,
    fillColumn: "",
    fillMethod: "mode",
    fillValue: "",
    dropColumns: [],
    dropColumnsConfirmed: false,
    encodeColumns: [],
    encodeMethod: "one_hot",
    keepEncodedOriginals: false,
    convertColumn: "",
    convertType: "numeric",
    renameColumn: "",
    renameTo: "",
    ...(cachedWorkspace?.cleaning || {}),
  }));

  const [analysisDomain, setAnalysisDomain] = useState(
    () => cachedWorkspace?.analysisDomain || "finance"
  );
  const [analysisMethod, setAnalysisMethod] = useState(() => {
    const cachedDomain = cachedWorkspace?.analysisDomain || "finance";
    const domainMethods =
      analysisGroups[cachedDomain]?.methods || analysisGroups.finance.methods;
    return cachedWorkspace?.analysisMethod || domainMethods[0].id;
  });
  const [params, setParams] = useState(() => {
    const cachedDomain = cachedWorkspace?.analysisDomain || "finance";
    const domainMethods =
      analysisGroups[cachedDomain]?.methods || analysisGroups.finance.methods;
    const cachedMethod =
      domainMethods.find((method) => method.id === cachedWorkspace?.analysisMethod) ||
      domainMethods[0];

    return {
      ...cachedMethod.template,
      ...(cachedWorkspace?.params || {}),
    };
  });

  const selectedForm =
    availableForms.find((form) => form.id === selectedFormId) ||
    firstFormWithResponses;

  const formFields = selectedForm ? getFormFields(selectedForm) : [];
  const methods =
    analysisGroups[analysisDomain]?.methods || analysisGroups.finance.methods;
  const activeMethod =
    methods.find((method) => method.id === analysisMethod) || methods[0];

  const columns = useMemo(() => dataset?.columns || [], [dataset]);

  const numericColumns = useMemo(() => {
    const preview = dataset?.preview || [];

    return columns.filter((column) =>
      preview.some((row) => isNumericLikeValue(row[column]))
    );
  }, [columns, dataset]);

  const textColumns = useMemo(
    () => columns.filter((column) => !numericColumns.includes(column)),
    [columns, numericColumns]
  );

  const activeVisualizationPlot = useMemo(
    () =>
      visualizationPlots.find((plot) => plot.id === activeVisualizationPlotId) ||
      visualizationPlots[0],
    [activeVisualizationPlotId, visualizationPlots]
  );

  useEffect(() => {
    if (!flowToast) return undefined;

    const timeoutId = window.setTimeout(() => {
      setFlowToast("");
    }, 7000);

    return () => window.clearTimeout(timeoutId);
  }, [flowToast]);

  useEffect(() => {
    const container = document.querySelector(".daw-page");
    if (container) {
      container.scrollTop = 0;
    }
  }, [currentStep]);

  useEffect(() => {
    if (dataset?.file_path || !cachedWorkspace?.dataset?.file_path) return;

    setDataset(cachedWorkspace.dataset);
    setCurrentStep(getRestorableDataWorkspaceStep(cachedWorkspace.currentStep));
    setSourceMode(cachedWorkspace.sourceMode || "forms");
    setSelectedFormId(cachedWorkspace.selectedFormId || firstFormWithResponses?.id || "");
    setExternalUrl(cachedWorkspace.externalUrl || "");
    setCleaning((current) => ({ ...current, ...(cachedWorkspace.cleaning || {}) }));
    setReportOptions((current) => ({
      ...current,
      ...(cachedWorkspace.reportOptions || {}),
    }));
    setAnalysisDomain(cachedWorkspace.analysisDomain || "finance");
    setAnalysisMethod((current) => cachedWorkspace.analysisMethod || current);
    setParams((current) => ({ ...current, ...(cachedWorkspace.params || {}) }));
    if (
      Array.isArray(cachedWorkspace.visualizationPlots) &&
      cachedWorkspace.visualizationPlots.length
    ) {
      setVisualizationPlots(cachedWorkspace.visualizationPlots);
    }
    setActiveVisualizationPlotId(
      cachedWorkspace.activeVisualizationPlotId || "plot-1"
    );
  }, [
    cachedWorkspace,
    dataset?.file_path,
    firstFormWithResponses?.id,
  ]);

  useEffect(() => {
    if (!dataset?.file_path) {
      if (!cachedWorkspace?.dataset?.file_path) {
        safeRemoveDataWorkspaceCache(dataWorkspaceCacheKey);
      }
      return;
    }

    safeWriteDataWorkspaceCache(dataWorkspaceCacheKey, {
      dataset: getCacheableDataset(dataset),
      currentStep: getRestorableDataWorkspaceStep(currentStep),
      sourceMode,
      selectedFormId,
      externalUrl,
      cleaning,
      reportOptions,
      analysisDomain,
      analysisMethod,
      params,
      visualizationPlots,
      activeVisualizationPlotId,
    });
  }, [
    activeVisualizationPlotId,
    analysisDomain,
    analysisMethod,
    cachedWorkspace,
    cleaning,
    currentStep,
    dataWorkspaceCacheKey,
    dataset,
    externalUrl,
    params,
    reportOptions,
    selectedFormId,
    sourceMode,
    visualizationPlots,
  ]);

  useEffect(() => {
    if (!columns.length) return;

    setVisualizationPlots((currentPlots) =>
      currentPlots.map((plot) => {
        const fallbackYColumns = numericColumns[0]
          ? [numericColumns[0]]
          : columns[1]
          ? [columns[1]]
          : [];
        const lineYColumns = toArray(plot.yColumns).filter((column) =>
          numericColumns.includes(column)
        );
        const heatmapColumns = toArray(plot.heatmapColumns).filter((column) =>
          numericColumns.includes(column)
        );

        return {
          ...plot,
          comparisonMode: normalizeComparisonMode(plot.chartType, plot.comparisonMode),
          xColumn: plot.xColumn || columns[0] || "",
          yColumn:
            plot.chartType === "line"
              ? (lineYColumns[0] || numericColumns[0] || "")
              : plot.yColumn || numericColumns[0] || columns[1] || "",
          xColumns: plot.xColumns?.length ? plot.xColumns : columns[0] ? [columns[0]] : [],
          yColumns:
            plot.chartType === "line"
              ? lineYColumns.length
                ? lineYColumns
                : numericColumns[0]
                ? [numericColumns[0]]
                : []
              : plot.yColumns?.length
              ? plot.yColumns
              : fallbackYColumns,
          heatmapColumns: heatmapColumns.length
            ? heatmapColumns
            : numericColumns.slice(0, 6),
        };
      })
    );
  }, [columns, numericColumns]);

  useEffect(() => {
    if (!isVisualizationSettingsOpen) return undefined;

    const blurActiveColorInput = (target) => {
      const activeColorInput =
        activeColorInputRef.current?.matches?.('input[type="color"]')
          ? activeColorInputRef.current
          : null;

      if (
        activeColorInput &&
        !target.closest(".daw-series-color-row") &&
        !target.closest(".daw-color-control")
      ) {
        activeColorInput.blur();
        activeColorInputRef.current = null;
      }
    };

    const handlePointerDown = (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      if (openAxisDropdown && !target.closest(".daw-multi-select")) {
        setOpenAxisDropdown("");
      }

      blurActiveColorInput(target);
    };

    const handleKeyDown = (event) => {
      if (event.key !== "Escape") return;

      setOpenAxisDropdown("");
      if (activeColorInputRef.current) {
        activeColorInputRef.current.blur();
        activeColorInputRef.current = null;
      }
    };

    document.addEventListener("pointerdown", handlePointerDown, true);
    document.addEventListener("keydown", handleKeyDown, true);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown, true);
      document.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [isVisualizationSettingsOpen, openAxisDropdown]);

  const showFlowError = (message) => {
    const safeMessage = userSafeErrorMessage(message);
    setAnalysisError(safeMessage);
    setFlowToast("");
    window.setTimeout(() => setFlowToast(safeMessage), 0);
  };

  const showVisualizationError = (message) => {
    const safeMessage = userSafeErrorMessage(
      message,
      "The visualization could not be created. Please check the plot settings and try again."
    );
    setAnalysisError(safeMessage);
    setVisualizationError(safeMessage);
    setVisualizationSuccess("");
    setVisualizationNotice("");
    setFlowToast("");
    setIsVisualizationSettingsOpen(true);
  };

  const renderVisualizationStatusMessage = () => {
    if (!visualizationError && !visualizationSuccess && !visualizationNotice) return null;

    const isSuccess = Boolean(visualizationSuccess);
    const isNotice = !isSuccess && !visualizationError;
    const message = visualizationSuccess || visualizationError || visualizationNotice;

    return (
      <div
        className={`daw-modal-alert ${
          isSuccess ? "daw-modal-alert-success" : ""
        } ${isNotice ? "daw-modal-alert-info" : ""
        }`}
        role={isSuccess || isNotice ? "status" : "alert"}
        aria-live={isSuccess || isNotice ? "polite" : "assertive"}
      >
        <span>
          {isSuccess ? <Check size={18} /> : <AlertTriangle size={18} />}
        </span>
        <div>
          <strong>{isSuccess ? "Success" : isNotice ? "Color note" : t.flowIssueTitle}</strong>
          <p>{message}</p>
        </div>
        <button
          type="button"
          aria-label="Dismiss message"
          onClick={() => {
            setVisualizationError("");
            setVisualizationSuccess("");
            setVisualizationNotice("");
          }}
        >
          <X size={16} />
        </button>
      </div>
    );
  };

  const renderVisualizationPreviewModal = () => {
    if (!visualizationPreview) return null;

    return (
      <div className="daw-modal-backdrop" role="dialog" aria-modal="true">
        <section className="daw-modal daw-visualization-preview-modal">
          <div className="daw-modal-header">
            <div>
              <span className="daw-kicker">PREVIEW</span>
              <h3>{visualizationPreview.title || "Generated visualization"}</h3>
            </div>
            <button
              type="button"
              className="daw-icon-button"
              aria-label="Close preview"
              onClick={() => setVisualizationPreview(null)}
            >
              <X size={18} />
            </button>
          </div>

          <div className="daw-visualization-preview-stage">
            <img
              src={visualizationPreview.url}
              alt={visualizationPreview.title || "Generated visualization preview"}
            />
          </div>

          <div className="daw-modal-actions">
            <button
              type="button"
              className="daw-primary"
              onClick={() => setVisualizationPreview(null)}
            >
              Done
            </button>
          </div>
        </section>
      </div>
    );
  };

  const cleaningActions = useMemo(() => {
    const actions = [];

    if (cleaning.trimText && textColumns.length) {
      actions.push({
        type: "clean_text_columns",
        params: {
          columns: textColumns,
          lower: cleaning.lowercaseText,
          strip: true,
          collapse_spaces: true,
        },
      });
    }

    if (cleaning.removeDuplicates) {
      actions.push({ type: "drop_duplicates", params: {} });
    }

    if (cleaning.removeMissingRows) {
      actions.push({ type: "drop_missing_rows", params: { how: "any" } });
    }

    if (cleaning.fillMissing && cleaning.fillColumn) {
      const config = { method: cleaning.fillMethod };

      if (cleaning.fillMethod === "constant") {
        config.value = cleaning.fillValue;
      }

      actions.push({
        type: "fill_missing",
        params: { fill_map: { [cleaning.fillColumn]: config } },
      });
    }

    if (cleaning.encodeColumns?.length) {
      actions.push({
        type: "encode_columns",
        params: {
          columns: cleaning.encodeColumns,
          method: cleaning.encodeMethod,
          keep_original: cleaning.keepEncodedOriginals,
        },
      });
    }

    if (cleaning.dropColumns.length && cleaning.dropColumnsConfirmed) {
      actions.push({
        type: "drop_columns",
        params: { columns: cleaning.dropColumns },
      });
    }

    if (cleaning.convertColumn) {
      actions.push({
        type: "convert_column_types",
        params: {
          type_map: { [cleaning.convertColumn]: cleaning.convertType },
        },
      });
    }

    if (cleaning.renameColumn && cleaning.renameTo.trim()) {
      actions.push({
        type: "rename_column",
        params: {
          rename_map: { [cleaning.renameColumn]: cleaning.renameTo.trim() },
        },
      });
    }

    return actions;
  }, [cleaning, textColumns]);

  const updateCleaning = (key, value) => {
    setCleaning((current) => ({ ...current, [key]: value }));
  };

  const updateParams = (key, value) => {
    setParams((current) => ({ ...current, [key]: value }));
  };

  const updateReportOptions = (key, value) => {
    setReportOptions((current) => ({ ...current, [key]: value }));
  };

  const updateVisualizationPlot = (plotId, key, value) => {
    setVisualizationPlots((currentPlots) =>
      currentPlots.map((plot) =>
        plot.id === plotId ? { ...plot, [key]: value } : plot
      )
    );
  };

  const updateVisualizationPlotChartType = (plotId, chartType) => {
    setVisualizationPlots((currentPlots) =>
      currentPlots.map((plot) =>
        {
          if (plot.id !== plotId) return plot;

          if (chartType === "line") {
            const nextYColumns = toArray(plot.yColumns).filter((column) =>
              numericColumns.includes(column)
            );
            const fallbackYColumns = nextYColumns.length
              ? nextYColumns
              : numericColumns[0]
              ? [numericColumns[0]]
              : [];

            return {
              ...plot,
              chartType,
              comparisonMode: normalizeComparisonMode(chartType, plot.comparisonMode),
              yColumn: fallbackYColumns[0] || "",
              yColumns: fallbackYColumns,
            };
          }

          return {
            ...plot,
            chartType,
            comparisonMode: normalizeComparisonMode(chartType, plot.comparisonMode),
            xLabel: axisLabelsDisabled(chartType) ? "" : plot.xLabel,
            yLabel: axisLabelsDisabled(chartType) ? "" : plot.yLabel,
            heatmapColumns:
              chartType === "heatmap" && !toArray(plot.heatmapColumns).length
                ? numericColumns.slice(0, 6)
                : plot.heatmapColumns,
          };
        }
      )
    );
  };

  const updateVisualizationColumns = (plotId, key, values) => {
    const nextValues = values.filter(Boolean);
    const currentPlot =
      visualizationPlots.find((plot) => plot.id === plotId) ||
      activeVisualizationPlot;
    const normalizePlotColumns = (plot) => {
      if (!plot || plot.chartType !== "box") return plot;

      const xColumns = toArray(plot.xColumns).filter(Boolean);
      const yColumns = toArray(plot.yColumns).filter(Boolean);
      if (!xColumns.length || !yColumns.length) return plot;

      const xSet = new Set(xColumns);
      const ySet = new Set(yColumns);
      const hasOverlap = xColumns.some((column) => ySet.has(column));
      if (!hasOverlap) return plot;

      if (key === "xColumns") {
        const filteredYColumns = yColumns.filter((column) => !xSet.has(column));
        return {
          ...plot,
          yColumns: filteredYColumns,
          yColumn: filteredYColumns[0] || "",
        };
      }

      if (key === "yColumns") {
        const filteredXColumns = xColumns.filter((column) => !ySet.has(column));
        return {
          ...plot,
          xColumns: filteredXColumns,
          xColumn: filteredXColumns[0] || "",
        };
      }

      return plot;
    };
    const nextPlot = currentPlot
      ? normalizePlotColumns({
          ...currentPlot,
          [key]: nextValues,
          ...(key === "xColumns" ? { xColumn: nextValues[0] || "" } : {}),
          ...(key === "yColumns" ? { yColumn: nextValues[0] || "" } : {}),
        })
      : null;

    setVisualizationPlots((currentPlots) =>
      currentPlots.map((plot) =>
        plot.id === plotId ? normalizePlotColumns({
          ...plot,
          [key]: nextValues,
          ...(key === "xColumns" ? { xColumn: nextValues[0] || "" } : {}),
          ...(key === "yColumns" ? { yColumn: nextValues[0] || "" } : {}),
        }) : plot
      )
    );

    if (nextPlot) {
      refreshVisualizationSelectionNotice(nextPlot, key);
    }
  };

  const updateVisualizationSeriesColor = (plotId, seriesName, color) => {
    setVisualizationPlots((currentPlots) =>
      currentPlots.map((plot) =>
        plot.id === plotId
          ? {
              ...plot,
              seriesColors: {
                ...(plot.seriesColors || {}),
                [seriesName]: color,
              },
            }
          : plot
      )
    );
  };

  const updateVisualizationCategoryColor = (plotId, categoryName, color) => {
    setVisualizationPlots((currentPlots) =>
      currentPlots.map((plot) =>
        plot.id === plotId
          ? {
              ...plot,
              categoryColors: {
                ...(plot.categoryColors || {}),
                [categoryName]: color,
              },
            }
          : plot
      )
    );
  };

  const updateVisualizationPalette = (plotId, palette) => {
    setVisualizationPlots((currentPlots) =>
      currentPlots.map((plot) => {
        if (plot.id !== plotId) return plot;

        const categoryValues = Array.isArray(plot.categoryColorValues)
          ? plot.categoryColorValues
          : [];
        const categoryPalette = getPalettePreview(
          palette,
          Math.max(1, categoryValues.length)
        );
        const nextCategoryColors = Object.fromEntries(
          categoryValues.map((value, index) => [
            value,
            categoryPalette[index] || plot.color,
          ])
        );

        return {
          ...plot,
          palette,
          useSingleColor: false,
          seriesColors: {},
          categoryColors: nextCategoryColors,
        };
      })
    );
  };

  const renderColumnDropdown = ({
    id,
    options,
    selectedValues,
    multiple = false,
    placeholder = "Select column",
    colorMap = {},
    onChange,
  }) => {
    const selected = toArray(selectedValues).filter(Boolean);
    const menuOptions = [
      ...selected.filter((value) => !options.includes(value)),
      ...options,
    ];
    const isOpen = openAxisDropdown === id;
    const summary = selected.length
      ? multiple
        ? selected.length === 1
          ? selected[0]
          : `${selected.length} selected`
        : selected[0]
      : placeholder;

    const toggleValue = (value) => {
      if (!multiple) {
        onChange(selected.includes(value) ? [] : value ? [value] : []);
        setOpenAxisDropdown("");
        return;
      }

      onChange(
        selected.includes(value)
          ? selected.filter((item) => item !== value)
          : [...selected, value]
      );
    };

    return (
      <div className="daw-multi-select">
        <button
          type="button"
          className="daw-multi-select-trigger"
          aria-expanded={isOpen}
          onClick={() => setOpenAxisDropdown(isOpen ? "" : id)}
        >
          <span className={selected.length ? "" : "is-placeholder"}>
            {summary}
          </span>
          <ChevronDown size={16} />
        </button>

        {isOpen ? (
          <div className="daw-multi-select-menu" role="listbox">
            {menuOptions.map((option) => {
              const isSelected = selected.includes(option);
              const isStaleSelection = isSelected && !options.includes(option);
              const selectedColor = colorMap[option];

              return (
                <button
                  type="button"
                  key={option}
                  className={isSelected ? "selected" : ""}
                  style={
                    isSelected && selectedColor
                      ? { "--series-color": selectedColor }
                      : undefined
                  }
                  role="option"
                  aria-selected={isSelected}
                  title={
                    isStaleSelection
                      ? "Selected earlier. Click to remove it."
                      : option
                  }
                  onClick={() => toggleValue(option)}
                >
                  <span className="daw-multi-select-check">
                    {isSelected ? <Check size={13} /> : null}
                  </span>
                  <span>{option}</span>
                  {isStaleSelection ? <small>Remove</small> : null}
                </button>
              );
            })}
          </div>
        ) : null}
      </div>
    );
  };

  const buildSingleVisualizationConfig = (plot, overrides = {}) => {
    const {
      name,
      comparisonMode,
      chartType,
      barOrientation,
      xColumn,
      yColumn,
      hueColumn,
      header,
      title,
      xLabel,
      yLabel,
      palette,
      useSingleColor,
      useGradient,
      color,
      seriesColors,
      categoryColors,
      categoryColorValues,
      fontFamily,
      titleFontSize,
      labelFontSize,
      tickFontSize,
      legendFontSize,
      heatmapColumns,
      width,
      height,
    } = plot || {};
    const nextX = overrides.xColumn ?? xColumn;
    const nextY = overrides.yColumn ?? yColumn;
    const nextXLabel = Array.isArray(nextX) ? nextX.join(" / ") : nextX;
    const nextYLabel = Array.isArray(nextY) ? nextY.join(" / ") : nextY;
    const titleSuffix = overrides.titleSuffix ? ` ${overrides.titleSuffix}` : "";
    const activeComparisonMode = normalizeComparisonMode(chartType, comparisonMode);
    const seriesCount = Math.max(1, toArray(nextY).filter(Boolean).length);
    const seriesNames = toArray(nextY).filter(Boolean);
    const shouldUseSeriesPalette =
      multiSeriesCharts.includes(chartType) &&
      ["1:M", "M:M"].includes(activeComparisonMode);
    const histogramUsesGradient =
      chartType === "histogram" && !hueColumn && Boolean(useGradient);
    const shouldForceSingleColor =
      chartType === "histogram" && !hueColumn && !histogramUsesGradient;
    const shouldUseSingleColor =
      !shouldUseSeriesPalette && (Boolean(useSingleColor) || shouldForceSingleColor);
    const nextSeriesPalette = shouldUseSeriesPalette
      ? seriesNames.map(
          (seriesName, index) =>
            seriesColors?.[seriesName] ||
            getPalettePreview(palette, seriesCount)[index]
        )
      : [];
    const canUseCategoryPalette =
      !shouldUseSeriesPalette &&
      !shouldUseSingleColor &&
      Array.isArray(categoryColorValues) &&
      categoryColorCharts.includes(chartType) &&
      (Boolean(hueColumn) || supportsUngroupedCategoryColors(chartType));
    const categoryPalette =
      canUseCategoryPalette
        ? categoryColorValues
            .map((value) => categoryColors?.[value])
            .filter(Boolean)
        : [];

    const fallbackTitle =
      String(title || "").trim() ||
      reportOptions.title?.trim() ||
      (needsYColumn(chartType) && nextYLabel && nextXLabel
        ? activeLang === "ar"
          ? `${nextYLabel} حسب ${nextXLabel}`
          : `${nextYLabel} by ${nextXLabel}`
        : `${chartTypes.find((type) => type.id === chartType)?.label || "Chart"} visualization`);

    return cleanObject({
      chart_type: chartType,
      orientation: ["bar", "box", "violin"].includes(chartType)
        ? barOrientation || "vertical"
        : "",
      x: needsXColumn(chartType) ? nextX : "",
      y: needsYColumn(chartType) ? nextY : "",
      hue: supportsHueGrouping(chartType) ? hueColumn : "",
      features: chartType === "heatmap" ? toArray(heatmapColumns).filter(Boolean) : [],
      title: `${fallbackTitle}${titleSuffix}`,
      x_label: axisLabelsDisabled(chartType) ? "" : String(xLabel || "").trim(),
      y_label: axisLabelsDisabled(chartType) ? "" : String(yLabel || "").trim(),
      palette: shouldUseSeriesPalette
        ? nextSeriesPalette
        : shouldUseSingleColor
        ? ""
        : categoryPalette.length
        ? categoryPalette
        : palette,
      color: shouldUseSingleColor ? color : "",
      series_count: categoryPalette.length || seriesCount,
      language: activeLang,
      font_family: fontFamily,
      title_font_size: Number(titleFontSize) || 18,
      label_font_size: Number(labelFontSize) || 12,
      tick_font_size: Number(tickFontSize) || 10,
      legend_font_size: Number(legendFontSize) || 10,
      figsize: [Number(width) || 10, Number(height) || 6],
      gradient:
        typeof useGradient === "boolean"
          ? useGradient
          : shouldUseTrendGradient(plot, nextX),
      save_path: `${String(header || name || "madar-visualization")
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/(^-|-$)/g, "") || "madar-visualization"}-${Date.now()}.png`,
    });
  };

  const buildVisualizationConfigs = (plot = activeVisualizationPlot) => {
    if (!plot) return [];

    const chartType = plot.chartType;
    const activeComparisonMode = normalizeComparisonMode(chartType, plot.comparisonMode);

    if (!needsYColumn(chartType)) {
      return [
        buildSingleVisualizationConfig(plot, {
          xColumn: toArray(plot.xColumns)[0] || plot.xColumn,
        }),
      ];
    }

    if (activeComparisonMode === "1:M") {
      return [
        buildSingleVisualizationConfig(plot, {
          xColumn: toArray(plot.xColumns)[0] || plot.xColumn,
          yColumn: toArray(plot.yColumns),
        }),
      ];
    }

    if (activeComparisonMode === "M:M") {
      const xColumns = toArray(plot.xColumns);
      const yColumns = toArray(plot.yColumns);

      return [
        buildSingleVisualizationConfig(plot, {
          xColumn: xColumns,
          yColumn: yColumns,
        }),
      ];
    }

    return [
      buildSingleVisualizationConfig(plot, {
        xColumn: toArray(plot.xColumns)[0] || plot.xColumn,
        yColumn: toArray(plot.yColumns)[0] || plot.yColumn,
      }),
    ];
  };

  const getVisualizationProfileCacheKey = (plot) => {
    const columnsToProfile = [
      ...toArray(plot?.xColumns),
      ...toArray(plot?.yColumns),
      plot?.hueColumn,
    ]
      .filter(Boolean)
      .map(String)
      .sort();

    return JSON.stringify({
      inputPath: dataset?.file_path || "",
      cleaningActions,
      columns: Array.from(new Set(columnsToProfile)),
    });
  };

  const profileVisualizationColumns = async (plot) => {
    const columnsToProfile = [
      ...toArray(plot?.xColumns),
      ...toArray(plot?.yColumns),
      plot?.hueColumn,
    ].filter(Boolean);

    if (!columnsToProfile.length) return null;

    const cacheKey = getVisualizationProfileCacheKey(plot);

    if (visualizationProfileCacheRef.current[cacheKey]) {
      return visualizationProfileCacheRef.current[cacheKey];
    }

    const response = await apiFetch(userApiPath("/visualization/columns/profile"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input_path: dataset.file_path,
        cleaning_actions: cleaningActions,
        columns: Array.from(new Set(columnsToProfile)),
      }),
    });

    const data = await readApiResponse(response);

    if (!response.ok) {
      throw new Error(data.detail || "Could not inspect selected columns.");
    }

    visualizationProfileCacheRef.current[cacheKey] = data;
    return data;
  };

  const getVisualizationColorNotice = (plot, profileData, changedKey = "") => {
    const profiles = profileData?.profiles || {};
    const activeComparisonMode = normalizeComparisonMode(
      plot?.chartType,
      plot?.comparisonMode
    );
    const xColumn = toArray(plot?.xColumns).filter(Boolean)[0];
    const yColumn = toArray(plot?.yColumns).filter(Boolean)[0];
    const hueColumn = plot?.hueColumn;
    const xUniqueCount = Number(profiles[xColumn]?.unique_count || 0);
    const yUniqueCount = Number(profiles[yColumn]?.unique_count || 0);
    const hueUniqueCount = Number(profiles[hueColumn]?.unique_count || 0);
    const yIsNumeric = Boolean(profiles[yColumn]?.is_numeric);

    if (hueColumn && hueUniqueCount > 1 && supportsHueGrouping(plot?.chartType)) {
      return `${hueColumn} has ${hueUniqueCount} unique values, so colors represent those groups.`;
    }

    if (plot?.chartType === "histogram") {
      return plot?.useSingleColor
        ? "Histogram shows one distribution. Base color is on, so the bars use the selected color."
        : "Histogram shows one distribution. Choose a group column if you want separate colors.";
    }

    if (["line", "scatter"].includes(plot?.chartType) && !hueColumn) {
      return plot?.useSingleColor
        ? `${plot?.chartType === "line" ? "Line" : "Scatter"} chart uses the selected base color. Add a group column for separate colors.`
        : `${plot?.chartType === "line" ? "Line" : "Scatter"} chart uses the selected palette when grouped or when multiple series are selected.`;
    }

    if (plot?.chartType === "bar" && yColumn && !yIsNumeric && xUniqueCount > 1) {
      return `${xColumn} has ${xUniqueCount} values on the chart. ${yColumn} is categorical, so the chart counts records by ${xColumn} and colors by ${yColumn}.`;
    }

    if (activeComparisonMode !== "1:1" && toArray(plot?.yColumns).filter(Boolean).length > 1) {
      return "More than one value column is selected, so colors identify each series.";
    }

    if (!plot?.useSingleColor && xColumn && xUniqueCount > 1) {
      return `${xColumn} has ${xUniqueCount} unique values. With base color turned off, the palette can color categories separately.`;
    }

    if (plot?.useSingleColor && xColumn && xUniqueCount > 1) {
      if (changedKey === "yColumns" && yColumn && yUniqueCount > 1) {
        return `${yColumn} has ${yUniqueCount} unique values. Bar size shows the Y values; base color is on, so all ${xUniqueCount} X categories use the selected base color.`;
      }

      return `${xColumn} has ${xUniqueCount} unique values. Base color is on, so all categories use the selected base color.`;
    }

    if (changedKey === "yColumns" && yColumn && yUniqueCount > 1) {
      return `${yColumn} has ${yUniqueCount} unique values. The Y axis controls bar size; colors only multiply when grouping, multiple series, or palette category coloring is enabled.`;
    }

    return "";
  };

  const applyVisualizationCategoryColors = (plot, profileData) => {
    const profiles = profileData?.profiles || {};
    const xColumn = toArray(plot?.xColumns).filter(Boolean)[0] || "";
    const yColumn = toArray(plot?.yColumns).filter(Boolean)[0] || "";
    const yIsNumeric = Boolean(profiles[yColumn]?.is_numeric);
    const colorColumn = plot?.hueColumn
      ? plot.hueColumn
      : plot?.chartType === "bar" && yColumn && !yIsNumeric
      ? yColumn
      : supportsUngroupedCategoryColors(plot?.chartType)
      ? xColumn
      : "";
    const profile = profiles[colorColumn];
    const values = Array.isArray(profile?.sample_values)
      ? profile.sample_values.map((value) => String(value)).filter(Boolean)
      : [];

    if (!plot?.id || !colorColumn || values.length <= 1) {
      setVisualizationPlots((currentPlots) =>
        currentPlots.map((currentPlot) =>
          currentPlot.id === plot?.id
            ? {
                ...currentPlot,
                categoryColorColumn: "",
                categoryColorValues: [],
              }
            : currentPlot
        )
      );
      return;
    }

    const paletteColors = getPalettePreview(plot.palette, values.length);

    setVisualizationPlots((currentPlots) =>
      currentPlots.map((currentPlot) => {
        if (currentPlot.id !== plot.id) return currentPlot;

        const nextCategoryColors = { ...(currentPlot.categoryColors || {}) };
        values.forEach((value, index) => {
          if (!nextCategoryColors[value]) {
            nextCategoryColors[value] = paletteColors[index] || currentPlot.color;
          }
        });

        return {
          ...currentPlot,
          useSingleColor: false,
          categoryColorColumn: colorColumn,
          categoryColorValues: values,
          categoryColors: nextCategoryColors,
        };
      })
    );
  };

  async function refreshVisualizationSelectionNotice(plot, changedKey = "") {
    if (!dataset?.file_path || !plot) return;

    const requestId = visualizationNoticeRequestRef.current + 1;
    visualizationNoticeRequestRef.current = requestId;
    setVisualizationError("");
    setVisualizationSuccess("");
    setVisualizationNotice("Checking selected column values...");
    setIsVisualizationChecking(true);

    try {
      const profileData = await profileVisualizationColumns(plot);
      const profiles = profileData?.profiles || {};
      const firstYColumn = toArray(plot?.yColumns).filter(Boolean)[0];
      const firstXColumn = toArray(plot?.xColumns).filter(Boolean)[0];
      const colorColumn = plot?.hueColumn
        ? plot.hueColumn
        : plot?.chartType === "bar" &&
          firstYColumn &&
          !profiles[firstYColumn]?.is_numeric
        ? firstYColumn
        : supportsUngroupedCategoryColors(plot?.chartType)
        ? firstXColumn
        : "";
      const categoryValues = Array.isArray(profiles[colorColumn]?.sample_values)
        ? profiles[colorColumn].sample_values
        : [];
      const nextPlot =
        categoryValues.length > 1
          ? { ...plot, useSingleColor: false }
          : plot;
      const nextNotice = getVisualizationColorNotice(
        nextPlot,
        profileData,
        changedKey
      );
      if (visualizationNoticeRequestRef.current !== requestId) return;
      applyVisualizationCategoryColors(nextPlot, profileData);
      setVisualizationNotice(nextNotice);
      setIsVisualizationChecking(false);
    } catch (error) {
      if (visualizationNoticeRequestRef.current !== requestId) return;
      setVisualizationNotice("");
      setVisualizationError(
        userSafeErrorMessage(
          error.message,
          "Could not inspect the selected fields for color suggestions."
        )
      );
      setIsVisualizationChecking(false);
    }
  }

  const setDomain = (domain) => {
    const nextMethod = analysisGroups[domain].methods[0];

    setAnalysisDomain(domain);
    setAnalysisMethod(nextMethod.id);
    setParams({ ...nextMethod.template });
  };

  const setMethod = (methodId) => {
    const nextMethod =
      methods.find((method) => method.id === methodId) || methods[0];

    setAnalysisMethod(nextMethod.id);
    setParams({ ...nextMethod.template });
  };

  const setLoadedDataset = (data, sourceContext = {}) => {
    setDataset(data);
    if (sourceContext.sourceMode) {
      setSourceMode(sourceContext.sourceMode);
    }
    if (sourceContext.selectedFormId) {
      setSelectedFormId(sourceContext.selectedFormId);
    }
    if (sourceContext.externalUrl) {
      setExternalUrl(sourceContext.externalUrl);
    }
    setSelectedFile(null);
    setInspection(null);
    setInspectionCache({});
    setAnalysisResult(null);
    setVisualizationResultsByPlot({});
    setVisualizationPreview(null);
    setAssistResult(null);
    setCurrentStep("review");
  };

  const uploadFile = async (file, sourceContext = {}) => {
    if (!file) {
      showFlowError(t.chooseFileFirst);
      return;
    }

    const payload = new FormData();
    payload.append("file", file);

    setIsLoading(true);
    setAnalysisError("");

    try {
      const response = await apiFetch(userApiPath("/data/upload"), {
        method: "POST",
        credentials: "include",
        body: payload,
      });

      const data = await readApiResponse(response);

      if (!response.ok) {
        throw new Error(data.detail || "The data could not be loaded.");
      }

      setLoadedDataset(data, {
        sourceMode: sourceContext.sourceMode || "upload",
        selectedFormId: sourceContext.selectedFormId,
      });
    } catch (error) {
      showFlowError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const loadExternalSource = async () => {
    const inputPath = externalUrl.trim();

    if (!inputPath) {
      showFlowError(t.pasteLinkFirst);
      return;
    }

    setIsLoading(true);
    setAnalysisError("");

    try {
      const response = await apiFetch(userApiPath("/data/read"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_path: inputPath }),
      });

      const data = await readApiResponse(response);

      if (!response.ok) {
        throw new Error(getFriendlyExternalError(data.detail));
      }

      setLoadedDataset(
        {
          ...data,
          file_path: data.file_path || inputPath,
          original_filename: data.original_filename || inputPath,
        },
        {
          sourceMode: "external",
          externalUrl: inputPath,
        }
      );
    } catch (error) {
      showFlowError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const importFormResponses = async () => {
    if (!selectedForm) {
      showFlowError(t.createFormFirst);
      return;
    }

    if (!selectedForm.responses?.length) {
      showFlowError(t.emptyForm);
      return;
    }

    const headers = [
      "Submitted at",
      "Status",
      ...formFields.map((field) => field.label || field.title || field.id),
    ];

    const rows = selectedForm.responses.map((response) => [
      response.createdAt || "",
      response.status || "Submitted",
      ...formFields.map((field) => response.answers?.[field.id] ?? ""),
    ]);

    const csv = [headers, ...rows]
      .map((row) => row.map(escapeCsvValue).join(","))
      .join("\n");

    const file = new File(
      ["\uFEFF" + csv],
      `${selectedForm.title || "form-responses"}.csv`,
      { type: "text/csv;charset=utf-8" }
    );

    await uploadFile(file, {
      sourceMode: "forms",
      selectedFormId: selectedForm.id,
    });
  };

  const runInspection = async (type) => {
    if (!dataset?.file_path) {
      showFlowError(t.loadDataBeforeReview);
      return;
    }

    const cacheKey = `${dataset.file_path}:${type}`;

    if (inspectionCache[cacheKey]) {
      setInspection(inspectionCache[cacheKey]);
      setAnalysisError("");
      return;
    }

    const paths = {
      overview: "/cleaning/inspect",
      statistics: "/cleaning/statistics",
      missing: "/cleaning/missing-report",
      quality: "/cleaning/quality-report",
    };

    setIsLoading(true);
    setAnalysisError("");

    try {
      const response = await apiFetch(userApiPath(paths[type]), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_path: dataset.file_path }),
      });

      const data = await readApiResponse(response);

      if (!response.ok) {
        throw new Error(data.detail || "The review could not be completed.");
      }

      const nextInspection = { type, data };
      setInspection(nextInspection);
      setInspectionCache((current) => ({
        ...current,
        [cacheKey]: nextInspection,
      }));
    } catch (error) {
      showFlowError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const runAnalysis = async () => {
    if (!dataset?.file_path) {
      showFlowError(t.loadDataBeforeAnalysis);
      return;
    }

    const missingRequiredParams = getMissingRequiredParams(
      activeMethod.template,
      params,
      activeLang
    );

    if (missingRequiredParams.length) {
      showFlowError(t.missingRequiredFields(missingRequiredParams));
      setCurrentStep("report");
      return;
    }

    setIsLoading(true);
    setAnalysisError("");

    try {
      const response = await apiFetch(userApiPath("/analysis/run"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_path: dataset.file_path,
          cleaning_actions: cleaningActions,
          language: activeLang,
          symbols: {
            currency: activeLang === "ar" ? "د.إ" : "$",
            percent: activeLang === "ar" ? "٪" : "%",
            decimal_separator: activeLang === "ar" ? "," : ".",
            thousands_separator: activeLang === "ar" ? "." : ",",
          },
          analysis_requests: [
            {
              domain: analysisDomain,
              method: analysisMethod,
              key: activeMethod.label,
              params: cleanObject(params),
            },
          ],
        }),
      });

      const data = await readApiResponse(response);

      if (!response.ok) {
        throw new Error(data.detail || "The analysis could not be completed.");
      }

      setAnalysisResult(data);
      setCurrentStep("report");
    } catch (error) {
      showFlowError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const runVisualization = async (plot = activeVisualizationPlot) => {
    if (isVisualizationChecking) {
      return;
    }

    if (!dataset?.file_path) {
      showVisualizationError(t.loadDataBeforeAnalysis);
      return;
    }

    const validationMessage = validateVisualizationPlot(plot, numericColumns);
    if (validationMessage) {
      showVisualizationError(validationMessage);
      return;
    }

    const chartConfigs = buildVisualizationConfigs(plot);
    const chartType = plot?.chartType;

    if (!chartConfigs.length) {
      showVisualizationError(
        `Choose comparison variables for ${plot?.name || "this plot"} before generating.`
      );
      return;
    }

    if (needsXColumn(chartType) && chartConfigs.some((config) => !hasColumnValue(config.x))) {
      showVisualizationError(
        `Choose X axis variable(s) for ${plot?.name || "this plot"} before generating.`
      );
      return;
    }

    if (needsYColumn(chartType) && chartConfigs.some((config) => !hasColumnValue(config.y))) {
      showVisualizationError(
        `Choose Y axis variable(s) for ${plot?.name || "this plot"} before generating.`
      );
      return;
    }

    setIsLoading(true);
    setAnalysisError("");
    setVisualizationError("");
    setVisualizationSuccess("");
    setVisualizationNotice("");

    try {
      const profileData = await profileVisualizationColumns(plot);
      const colorNotice = getVisualizationColorNotice(plot, profileData);
      const results = [];

      for (const chartConfig of chartConfigs) {
        const response = await apiFetch(userApiPath("/visualization/create"), {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            input_path: dataset.file_path,
            cleaning_actions: cleaningActions,
            chart_config: chartConfig,
          }),
        });

        const data = await readApiResponse(response);

        if (!response.ok) {
          throw new Error(data.detail || "The visualization could not be created.");
        }

        results.push(data);
      }

      setVisualizationResultsByPlot((current) => {
        const existingPlots = getVisualizationPlots(current[plot.id]);
        const nextPlots = [...existingPlots, ...results];

        return {
          ...current,
          [plot.id]: nextPlots.length === 1 ? nextPlots[0] : { plots: nextPlots },
        };
      });
      setVisualizationError("");
      setVisualizationSuccess(
        results.length === 1
          ? "Visualization generated successfully."
          : `${results.length} visualizations generated successfully.`
      );
      setVisualizationNotice(colorNotice);
      setIsVisualizationSettingsOpen(false);
      setActiveVisualizationPlotId(plot.id);
      setCurrentStep("visualization");
    } catch (error) {
      showVisualizationError(getFriendlyVisualizationError(error.message));
    } finally {
      setIsLoading(false);
    }
  };

  const deleteVisualizationOutput = (plotId, outputIndex) => {
    setVisualizationResultsByPlot((current) => {
      const existingPlots = getVisualizationPlots(current[plotId]);
      const nextPlots = existingPlots.filter((_, index) => index !== outputIndex);

      if (!nextPlots.length) {
        const remainingPlots = { ...current };
        delete remainingPlots[plotId];
        return remainingPlots;
      }

      return {
        ...current,
        [plotId]: nextPlots.length === 1 ? nextPlots[0] : { plots: nextPlots },
      };
    });
  };

  const runAssistedQuestion = async () => {
    const question = assistQuestion.trim();

    if (!dataset?.file_path) {
      showFlowError(t.loadDataBeforeAnalysis);
      return;
    }

    if (!question) {
      showFlowError(t.writeQuestionFirst);
      return;
    }

    setIsLoading(true);
    setAnalysisError("");

    try {
      const response = await apiFetch(userApiPath("/analysis/assist"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_path: dataset.file_path,
          cleaning_actions: cleaningActions,
          question,
          language: activeLang,
          symbols: {
            currency: activeLang === "ar" ? "د.إ" : "$",
            percent: activeLang === "ar" ? "٪" : "%",
            decimal_separator: activeLang === "ar" ? "," : ".",
            thousands_separator: activeLang === "ar" ? "." : ",",
          },
        }),
      });

      const data = await readApiResponse(response);

      if (!response.ok) {
        throw new Error(
          data.detail || "The assisted analysis could not be completed."
        );
      }

      setAssistResult(data.result || data);
      setAssistQuestion("");
    } catch (error) {
      showFlowError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const analysisPayload = useMemo(() => {
    if (!analysisResult?.results) return analysisResult;

    return (
      analysisResult.results[activeMethod.label] ||
      Object.values(analysisResult.results)[0] ||
      analysisResult.results
    );
  }, [analysisResult, activeMethod.label]);

  const goToPreviousStep = () => {
    const order = ["source", "review", "prepare", "visualization", "report"];
    const currentIndex = order.indexOf(currentStep);
    setCurrentStep(order[Math.max(0, currentIndex - 1)]);
  };

  const goToNextStep = () => {
    const order = ["source", "review", "prepare", "visualization", "report"];
    const currentIndex = order.indexOf(currentStep);
    setCurrentStep(order[Math.min(order.length - 1, currentIndex + 1)]);
  };

  const renderVisualizationSettingsModal = () => {
    if (!isVisualizationSettingsOpen) return null;

    return (
      <div className="daw-modal-backdrop" role="presentation">
        <section
          className="daw-modal daw-visualization-settings-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="daw-visualization-settings-title"
        >
          <div className="daw-modal-header">
            <div>
              <span className="daw-kicker">CHART SETTINGS</span>
              <h3 id="daw-visualization-settings-title">
                Configure plots
              </h3>
              <p>
                Edit each plot separately: type, variables, headers, titles,
                colors, and fonts.
              </p>
            </div>
            <button
              type="button"
              className="daw-icon-button"
              aria-label="Close chart settings"
              onClick={() => setIsVisualizationSettingsOpen(false)}
            >
              <X size={18} />
            </button>
          </div>

          <div className="daw-plot-editor-list">
            {visualizationPlots.map((plot, index) => {
              const chartType = plot.chartType;
              const relationshipOptions = getRelationshipOptions(chartType);
              const activeComparisonMode = normalizeComparisonMode(
                chartType,
                plot.comparisonMode
              );
              const activeRelationship = getRelationshipOption(
                chartType,
                activeComparisonMode
              );
              const seriesCount = getSeriesCount(plot);
              const usesSeriesPalette =
                multiSeriesCharts.includes(chartType) &&
                ["1:M", "M:M"].includes(activeComparisonMode);
              const selectedChartLabel =
                chartTypes.find((type) => type.id === chartType)?.label ||
                "Chart";

              return (
                <article
                  key={plot.id}
                  className={`daw-plot-editor-card ${
                    activeVisualizationPlotId === plot.id ? "active" : ""
                  }`}
                >
                  <div className="daw-plot-editor-card-header">
                    <div>
                      <span>Plot {index + 1}</span>
                      <h4>{plot.header || plot.name}</h4>
                    </div>
                  </div>

                  <div className="daw-modal-grid">
                    <Field label="Plot name">
                      <input
                        value={plot.name}
                        onChange={(event) =>
                          updateVisualizationPlot(plot.id, "name", event.target.value)
                        }
                      />
                    </Field>

                    <Field label="Relationship">
                      <select
                        value={activeComparisonMode}
                        disabled={relationshipOptions.length <= 1}
                        onChange={(event) =>
                          updateVisualizationPlot(
                            plot.id,
                            "comparisonMode",
                            event.target.value
                          )
                        }
                      >
                        {relationshipOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </Field>

                    <div className="daw-comparison-hint">
                      <span>{activeRelationship?.label}</span>
                      <p>{getComparisonHint({ ...plot, comparisonMode: activeComparisonMode })}</p>
                    </div>

                    <Field label="Plot type">
                      <select
                        value={chartType}
                        onChange={(event) =>
                          updateVisualizationPlotChartType(
                            plot.id,
                            event.target.value
                          )
                        }
                      >
                        {chartTypes.map((type) => (
                          <option key={type.id} value={type.id}>
                            {type.label}
                          </option>
                        ))}
                      </select>
                    </Field>

                    {["bar", "box", "violin"].includes(chartType) ? (
                      <Field label="Chart direction">
                        <select
                          value={plot.barOrientation || "vertical"}
                          onChange={(event) =>
                            updateVisualizationPlot(
                              plot.id,
                              "barOrientation",
                              event.target.value
                            )
                          }
                        >
                          <option value="vertical">Vertical</option>
                          <option value="horizontal">Horizontal</option>
                        </select>
                      </Field>
                    ) : null}

                    <Field label="Header">
                      <input
                        value={plot.header}
                        placeholder={`Plot ${index + 1}`}
                        onChange={(event) =>
                          updateVisualizationPlot(
                            plot.id,
                            "header",
                            event.target.value
                          )
                        }
                      />
                    </Field>

                    {supportsHueGrouping(chartType) ? (
                      <Field label="Group color by">
                        <select
                          value={plot.hueColumn}
                          onChange={(event) => {
                            const nextPlot = {
                              ...plot,
                              hueColumn: event.target.value,
                            };
                            updateVisualizationPlot(
                              plot.id,
                              "hueColumn",
                              event.target.value
                            );
                            refreshVisualizationSelectionNotice(nextPlot, "hueColumn");
                          }}
                        >
                          <option value="">No grouping</option>
                          {columns.map((column) => (
                            <option key={column} value={column}>
                              {column}
                            </option>
                          ))}
                        </select>
                      </Field>
                    ) : null}

                    {chartType === "heatmap" ? (
                      <Field label="Numeric columns" wide>
                        {renderColumnDropdown({
                          id: `${plot.id}-heatmap-features`,
                          options: numericColumns,
                          selectedValues: toArray(plot.heatmapColumns),
                          multiple: true,
                          placeholder: "Select numeric columns",
                          onChange: (values) =>
                            updateVisualizationColumns(
                              plot.id,
                              "heatmapColumns",
                              values
                            ),
                        })}
                      </Field>
                    ) : null}

                    {needsXColumn(chartType) || needsYColumn(chartType) ? (
                      <div className="daw-axis-select-row">
                        {needsXColumn(chartType) ? (
                          <Field
                            label={
                              activeComparisonMode === "M:M" &&
                              multiSeriesCharts.includes(chartType)
                                ? "X columns"
                                : chartType === "pie"
                                ? "Label column"
                                : ["box", "violin"].includes(chartType)
                                ? "Group column"
                                : "X axis"
                            }
                          >
                            {(() => {
                              const multiple =
                                activeComparisonMode === "M:M" &&
                                multiSeriesCharts.includes(chartType);
                              const selectedValues = toArray(plot.xColumns);

                              return renderColumnDropdown({
                                id: `${plot.id}-x`,
                                options:
                                  chartType === "box"
                                    ? columns.filter(
                                        (column) => !toArray(plot.yColumns).includes(column)
                                      )
                                    : columns,
                                selectedValues,
                                multiple,
                                placeholder: multiple
                                  ? "Select X columns"
                                  : "Select X axis",
                                onChange: (values) =>
                                  updateVisualizationColumns(
                                    plot.id,
                                    "xColumns",
                                    values
                                  ),
                              });
                            })()}
                          </Field>
                        ) : null}

                        {needsYColumn(chartType) ? (
                          <Field
                            label={
                              (activeComparisonMode === "1:M" ||
                                activeComparisonMode === "M:M") &&
                              multiSeriesCharts.includes(chartType)
                                ? chartType === "line"
                                  ? "Value columns"
                                  : "Value columns"
                                : chartType === "pie"
                                ? "Value column"
                                : ["box", "violin"].includes(chartType)
                                ? "Value column"
                                : "Y axis"
                            }
                          >
                            {(() => {
                              const yOptions =
                                ["line", "box"].includes(chartType) ? numericColumns : columns;
                              const availableYOptions =
                                chartType === "box"
                                  ? yOptions.filter(
                                      (column) => !toArray(plot.xColumns).includes(column)
                                    )
                                  : yOptions;
                              const multiple =
                                (activeComparisonMode === "1:M" ||
                                  activeComparisonMode === "M:M") &&
                                multiSeriesCharts.includes(chartType);
                              const selectedValues = toArray(plot.yColumns);
                              const selectedColors = getPalettePreview(
                                plot.palette,
                                selectedValues.length || 1
                              );
                              const colorMap = Object.fromEntries(
                                selectedValues.map((value, colorIndex) => [
                                  value,
                                  plot.seriesColors?.[value] || selectedColors[colorIndex],
                                ])
                              );

                              return renderColumnDropdown({
                                id: `${plot.id}-y`,
                                options: availableYOptions,
                                selectedValues,
                                multiple,
                                colorMap,
                                placeholder: multiple
                                  ? "Select value columns"
                                  : "Select Y axis",
                                onChange: (values) =>
                                  updateVisualizationColumns(
                                    plot.id,
                                    "yColumns",
                                    values
                                  ),
                              });
                            })()}
                          </Field>
                        ) : null}
                      </div>
                    ) : null}

                    <Field label="Chart title" wide>
                      <input
                        value={plot.title}
                        placeholder={`${selectedChartLabel} visualization`}
                        onChange={(event) =>
                          updateVisualizationPlot(plot.id, "title", event.target.value)
                        }
                      />
                    </Field>

                    <Field label="X label">
                      <input
                        value={axisLabelsDisabled(chartType) ? "" : plot.xLabel}
                        disabled={axisLabelsDisabled(chartType)}
                        onChange={(event) =>
                          updateVisualizationPlot(plot.id, "xLabel", event.target.value)
                        }
                      />
                    </Field>

                    <Field label="Y label">
                      <input
                        value={axisLabelsDisabled(chartType) ? "" : plot.yLabel}
                        disabled={axisLabelsDisabled(chartType)}
                        onChange={(event) =>
                          updateVisualizationPlot(plot.id, "yLabel", event.target.value)
                        }
                      />
                    </Field>

                    {axisLabelsDisabled(chartType) ? (
                      <p className="daw-field-note">
                        Axis labels are disabled for pie charts and heatmaps.
                      </p>
                    ) : null}

                    <Field label="Palette">
                      <select
                        value={plot.palette}
                        disabled={plot.useSingleColor && !usesSeriesPalette}
                        onChange={(event) =>
                          updateVisualizationPalette(plot.id, event.target.value)
                        }
                      >
                        {paletteOptions.map((palette) => (
                          <option key={palette} value={palette}>
                            {palette}
                          </option>
                        ))}
                      </select>
                    </Field>

                    <Field label="Gradient">
                      <label className="daw-color-mode-toggle daw-gradient-toggle">
                        <input
                          type="checkbox"
                          checked={
                            typeof plot.useGradient === "boolean"
                              ? plot.useGradient
                              : shouldUseTrendGradient(plot)
                          }
                          onChange={(event) =>
                            updateVisualizationPlot(
                              plot.id,
                              "useGradient",
                              event.target.checked
                            )
                          }
                        />
                        <span>Use gradient</span>
                      </label>
                      <small>
                        Uses the selected palette or category colors as a gradient for this plot.
                      </small>
                    </Field>

                    {usesSeriesPalette ? (
                      <Field label="Variable colors" wide>
                        <div className="daw-series-colors">
                          {toArray(plot.yColumns)
                            .filter(Boolean)
                            .map((seriesName, colorIndex) => {
                              const fallbackColor = getPalettePreview(
                                plot.palette,
                                seriesCount
                              )[colorIndex];
                              const selectedColor =
                                plot.seriesColors?.[seriesName] || fallbackColor;

                              return (
                                <label
                                  key={seriesName}
                                  className="daw-series-color-row"
                                  title={seriesName}
                                >
                                  <input
                                    type="color"
                                    value={selectedColor}
                                    onFocus={(event) => {
                                      activeColorInputRef.current = event.currentTarget;
                                      setOpenAxisDropdown("");
                                    }}
                                    onBlur={() => {
                                      activeColorInputRef.current = null;
                                    }}
                                    onChange={(event) =>
                                      updateVisualizationSeriesColor(
                                        plot.id,
                                        seriesName,
                                        event.target.value
                                      )
                                    }
                                  />
                                  <span>{seriesName}</span>
                                </label>
                              );
                            })}
                        </div>
                        <small>
                          {seriesCount} variable{seriesCount === 1 ? "" : "s"} selected.
                          Click a color to edit it.
                        </small>
                      </Field>
                    ) : (
                      <Field label="Single color">
                        <div className="daw-color-control">
                          <label className="daw-color-mode-toggle">
                            <input
                              type="checkbox"
                              checked={
                                plot.useSingleColor ||
                                (chartType === "histogram" &&
                                  !plot.hueColumn &&
                                  !plot.useGradient)
                              }
                              onChange={(event) => {
                                const nextPlot = {
                                  ...plot,
                                  useSingleColor: event.target.checked,
                                };
                                setVisualizationPlots((currentPlots) =>
                                  currentPlots.map((currentPlot) =>
                                    currentPlot.id === plot.id
                                      ? nextPlot
                                      : currentPlot
                                  )
                                );
                                refreshVisualizationSelectionNotice(
                                  nextPlot,
                                  "useSingleColor"
                                );
                              }}
                            />
                            <span>Use base color</span>
                          </label>
                          <input
                            type="color"
                            value={plot.color}
                            onFocus={(event) => {
                              activeColorInputRef.current = event.currentTarget;
                              setOpenAxisDropdown("");
                              if (!plot.useSingleColor) {
                                setVisualizationPlots((currentPlots) =>
                                  currentPlots.map((currentPlot) =>
                                    currentPlot.id === plot.id
                                      ? {
                                          ...currentPlot,
                                          useSingleColor: true,
                                        }
                                      : currentPlot
                                  )
                                );
                              }
                            }}
                            onBlur={() => {
                              activeColorInputRef.current = null;
                            }}
                            onChange={(event) => {
                              const nextColor = event.target.value;
                              setVisualizationPlots((currentPlots) =>
                                currentPlots.map((currentPlot) =>
                                  currentPlot.id === plot.id
                                    ? {
                                        ...currentPlot,
                                        color: nextColor,
                                        useSingleColor: true,
                                      }
                                    : currentPlot
                                )
                              );
                            }}
                          />
                        </div>
                        <small>
                          Turn off base color to let the selected palette use multiple colors.
                        </small>
                      </Field>
                    )}

                    {!usesSeriesPalette &&
                    categoryColorCharts.includes(chartType) &&
                    (Boolean(plot.hueColumn) ||
                      supportsUngroupedCategoryColors(chartType)) &&
                    Array.isArray(plot.categoryColorValues) &&
                    plot.categoryColorValues.length > 1 ? (
                      <Field label="Category colors" wide>
                        <div className="daw-series-colors">
                          {plot.categoryColorValues.map((categoryName, colorIndex) => {
                            const fallbackColor =
                              getPalettePreview(
                                plot.palette,
                                plot.categoryColorValues.length
                              )[colorIndex] || plot.color;
                            const selectedColor =
                              plot.categoryColors?.[categoryName] || fallbackColor;

                            return (
                              <label
                                key={categoryName}
                                className="daw-series-color-row"
                                title={categoryName}
                              >
                                <input
                                  type="color"
                                  value={selectedColor}
                                  onFocus={(event) => {
                                    activeColorInputRef.current = event.currentTarget;
                                    setOpenAxisDropdown("");
                                  }}
                                  onBlur={() => {
                                    activeColorInputRef.current = null;
                                  }}
                                  onChange={(event) => {
                                    updateVisualizationCategoryColor(
                                      plot.id,
                                      categoryName,
                                      event.target.value
                                    );
                                    if (plot.useSingleColor) {
                                      updateVisualizationPlot(
                                        plot.id,
                                        "useSingleColor",
                                        false
                                      );
                                    }
                                  }}
                                />
                                <span>{categoryName}</span>
                              </label>
                            );
                          })}
                        </div>
                        <small>
                          {plot.categoryColorValues.length} value
                          {plot.categoryColorValues.length === 1 ? "" : "s"} in{" "}
                          {plot.categoryColorColumn}. Edit each color to control the
                          category palette.
                        </small>
                      </Field>
                    ) : null}

                    <Field label="Font">
                      <select
                        value={plot.fontFamily}
                        onChange={(event) =>
                          updateVisualizationPlot(
                            plot.id,
                            "fontFamily",
                            event.target.value
                          )
                        }
                      >
                        {fontFamilyOptions.map((font) => (
                          <option key={font} value={font}>
                            {font}
                          </option>
                        ))}
                      </select>
                    </Field>

                    <Field label="Title size">
                      <input
                        type="number"
                        min="10"
                        max="42"
                        value={plot.titleFontSize}
                        onChange={(event) =>
                          updateVisualizationPlot(
                            plot.id,
                            "titleFontSize",
                            event.target.value
                          )
                        }
                      />
                    </Field>

                    <Field label="Label size">
                      <input
                        type="number"
                        min="8"
                        max="28"
                        value={plot.labelFontSize}
                        onChange={(event) =>
                          updateVisualizationPlot(
                            plot.id,
                            "labelFontSize",
                            event.target.value
                          )
                        }
                      />
                    </Field>

                    <Field label="Tick size">
                      <input
                        type="number"
                        min="8"
                        max="24"
                        value={plot.tickFontSize}
                        onChange={(event) =>
                          updateVisualizationPlot(
                            plot.id,
                            "tickFontSize",
                            event.target.value
                          )
                        }
                      />
                    </Field>

                    <Field label="Legend size">
                      <input
                        type="number"
                        min="8"
                        max="24"
                        value={plot.legendFontSize}
                        onChange={(event) =>
                          updateVisualizationPlot(
                            plot.id,
                            "legendFontSize",
                            event.target.value
                          )
                        }
                      />
                    </Field>
                  </div>

                </article>
              );
            })}
          </div>

          {renderVisualizationStatusMessage()}

          <div className="daw-modal-actions">
            <button
              type="button"
              className="daw-secondary"
              onClick={() => setIsVisualizationSettingsOpen(false)}
            >
              Done
            </button>
            {isVisualizationChecking ? null : (
              <button
                type="button"
                className="daw-primary"
                disabled={isLoading || !dataset}
                onClick={() => {
                  runVisualization(activeVisualizationPlot);
                }}
              >
                {isLoading ? t.working : "Generate visualization"}
              </button>
            )}
          </div>
        </section>
      </div>
    );
  };

  const renderCurrentStep = () => {
    if (currentStep === "source") {
      return (
        <DataSourceStep
          sourceMode={sourceMode}
          setSourceMode={setSourceMode}
          availableForms={availableForms}
          selectedForm={selectedForm}
          setSelectedFormId={setSelectedFormId}
          selectedFile={selectedFile}
          setSelectedFile={setSelectedFile}
          externalUrl={externalUrl}
          setExternalUrl={setExternalUrl}
          importFormResponses={importFormResponses}
          uploadFile={uploadFile}
          loadExternalSource={loadExternalSource}
          selectForm={selectForm}
          setActiveTab={setActiveTab}
          isLoading={isLoading}
          t={t}
        />
      );
    }

    if (currentStep === "review") {
      return (
        <DatasetReviewStep
          dataset={dataset}
          inspection={inspection}
          runInspection={runInspection}
          isLoading={isLoading}
          t={t}
        />
      );
    }

    if (currentStep === "prepare") {
      return (
        <PrepareDataStep
          dataset={dataset}
          columns={columns}
          textColumns={textColumns}
          cleaning={cleaning}
          updateCleaning={updateCleaning}
          t={t}
        />
      );
    }

    if (currentStep === "visualization") {
      return (
        <div className="daw-section-card daw-visualization-builder">
          <div className="daw-visualization-builder-header">
            <div>
              <span className="daw-kicker">VISUALIZATION</span>
              <h3>Create a visualization</h3>
              <p>
                Configure the plot, titles, colors, and font sizing before creating
                the full report.
              </p>
            </div>
          </div>

          <div className="daw-plot-summary-grid">
            {visualizationPlots.map((plot, index) => {
              const chartTypeLabel =
                chartTypes.find((type) => type.id === plot.chartType)?.label ||
                "Chart";
              const relationshipLabel = getRelationshipOption(
                plot.chartType,
                plot.comparisonMode
              )?.label;
              const plotResult = visualizationResultsByPlot[plot.id];
              const outputPlots = getVisualizationPlots(plotResult);

              return (
                <article
                  key={plot.id}
                  className={activeVisualizationPlotId === plot.id ? "active" : ""}
                >
                  <span>Plot {index + 1}</span>
                  <strong>{plot.header || plot.name}</strong>
                  <p>
                    {chartTypeLabel}
                    {relationshipLabel ? ` / ${relationshipLabel}` : ""}
                    {needsXColumn(plot.chartType)
                      ? ` / X: ${
                          toArray(plot.xColumns).join(", ") || "Not selected"
                        }`
                      : ""}
                    {needsYColumn(plot.chartType)
                      ? ` / Y: ${
                          toArray(plot.yColumns).join(", ") || "Not selected"
                        }`
                      : ""}
                  </p>
                  {outputPlots.length ? (
                    <div className="daw-plot-output-list">
                      {outputPlots.map((output, outputIndex) => {
                        const chartUrl = getVisualizationUrl(output, "chart_url");
                        const inspectUrl =
                          getVisualizationUrl(output, "explorer_url") || chartUrl;
                        const downloadUrl =
                          chartUrl || getVisualizationUrl(output, "explorer_url");
                        const outputLabel =
                          output?.chart_path
                            ? output.chart_path.split(/[\\/]/).pop()
                            : output?.explorer_path
                            ? output.explorer_path.split(/[\\/]/).pop()
                            : `Generated visualization ${outputIndex + 1}`;

                        return (
                          <div
                            className="daw-plot-output-row"
                            key={
                              output?.chart_path ||
                              output?.explorer_path ||
                              `${plot.id}_output_${outputIndex}`
                            }
                          >
                            <div className="daw-plot-output-copy">
                              <span>Generated plot</span>
                              <strong>{outputLabel}</strong>
                            </div>
                            <p className="daw-plot-output-note">
                              Preview the chart, download it, or inspect the data explorer.
                            </p>
                            <div className="daw-plot-output-actions">
                              {downloadUrl ? (
                                <a
                                  className="daw-icon-button"
                                  href={downloadUrl}
                                  download
                                  title="Download visualization"
                                  aria-label={`Download ${plot.header || plot.name}`}
                                >
                                  <Download size={17} />
                                </a>
                              ) : null}
                              {inspectUrl ? (
                                <button
                                  type="button"
                                  className="daw-icon-button"
                                  title="Inspect visualization"
                                  aria-label={`Inspect ${plot.header || plot.name}`}
                                  onClick={() =>
                                    setVisualizationPreview({
                                      url: chartUrl || inspectUrl,
                                      inspectUrl,
                                      title: plot.header || plot.name,
                                      label: outputLabel,
                                    })
                                  }
                                >
                                  <Eye size={17} />
                                </button>
                              ) : null}
                              <button
                                type="button"
                                className="daw-icon-button daw-danger-icon-button"
                                title="Delete generated plot"
                                aria-label={`Delete ${outputLabel}`}
                                onClick={() =>
                                  deleteVisualizationOutput(plot.id, outputIndex)
                                }
                              >
                                <Trash2 size={17} />
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : null}
                  <button
                    type="button"
                    className="daw-secondary"
                    onClick={() => {
                      setActiveVisualizationPlotId(plot.id);
                      setIsVisualizationSettingsOpen(true);
                    }}
                  >
                    Edit this plot
                  </button>
                </article>
              );
            })}
          </div>

          <div className="daw-visualization-actions">
            <button
              type="button"
              className="daw-secondary"
              onClick={() => setIsVisualizationSettingsOpen(true)}
              disabled={!dataset}
            >
              Edit settings
            </button>
            {isVisualizationChecking ? null : (
              <button
                type="button"
                className="daw-primary"
                onClick={() => runVisualization(activeVisualizationPlot)}
                disabled={isLoading || !dataset}
              >
                {isLoading ? t.working : "Generate visualization"}
              </button>
            )}
          </div>
        </div>
      );
    }

    return (
      <ReportBuilderStep
        dataset={dataset}
        activeLang={activeLang}
        analysisDomain={analysisDomain}
        setDomain={setDomain}
        methods={methods}
        analysisMethod={analysisMethod}
        setMethod={setMethod}
        activeMethod={activeMethod}
        params={params}
        updateParams={updateParams}
        columns={columns}
        numericColumns={numericColumns}
        runAnalysis={runAnalysis}
        runVisualization={runVisualization}
        isLoading={isLoading}
        reportOptions={reportOptions}
        updateReportOptions={updateReportOptions}
        t={t}
      />
    );
  };

  return (
    <div className="daw-page" dir={isArabic ? "rtl" : "ltr"}>
      <header className="daw-header" id="daw-top">
        <div>
          <span className="daw-kicker">{t.kicker}</span>
          <h2>{t.title}</h2>
          <p>{t.subtitle}</p>
        </div>
      </header>

      <Stepper
        currentStep={currentStep}
        setCurrentStep={setCurrentStep}
        dataset={dataset}
        t={t}
      />

      {flowToast ? (
        <div className="daw-flow-toast" role="alert" aria-live="assertive">
          <span>
            <AlertTriangle size={18} />
          </span>
          <div>
            <strong>{t.flowIssueTitle}</strong>
            <p>{flowToast}</p>
          </div>
          <button
            type="button"
            aria-label="Dismiss message"
            onClick={() => setFlowToast("")}
          >
            <X size={16} />
          </button>
        </div>
      ) : null}

      {renderVisualizationSettingsModal()}
      {renderVisualizationPreviewModal()}

      <section className={`daw-layout daw-step-${currentStep}`}>
        <main className="daw-flow" id="daw-workspace-main">
          <div className="daw-step-content">
            {renderCurrentStep()}

            {currentStep === "report" ? (
              <aside className="daw-canvas-column" id="daw-report-preview">
                <ReportCanvas
                  dataset={dataset}
                  analysisResult={analysisResult}
                  analysisPayload={analysisPayload}
                  activeMethod={activeMethod}
                  activeLang={activeLang}
                  reportOptions={reportOptions}
                  t={t}
                />
              </aside>
            ) : null}
          </div>

          <div id="daw-assistant">
            <AssistantPanel
              dataset={dataset}
              assistQuestion={assistQuestion}
              setAssistQuestion={setAssistQuestion}
              runAssistedQuestion={runAssistedQuestion}
              assistResult={assistResult}
              isLoading={isLoading}
              t={t}
            />
          </div>

          {dataset ? (
            <div
              id="daw-flow-actions"
              className={`daw-flow-actions ${
                currentStep === "source" ? "only-next" : ""
              }`}
            >
              {currentStep !== "source" ? (
                <button
                  type="button"
                  className="daw-step-back"
                  onClick={goToPreviousStep}
                >
                  {isArabic ? (
                    <ArrowRight size={16} />
                  ) : (
                    <ArrowLeft size={16} />
                  )}
                  {t.back}
                </button>
              ) : null}

              {currentStep !== "report" ? (
                <button
                  type="button"
                  className="daw-primary daw-step-next"
                  onClick={goToNextStep}
                >
                  {t.continue}
                  {isArabic ? (
                    <ArrowLeft size={16} />
                  ) : (
                    <ArrowRight size={16} />
                  )}
                </button>
              ) : null}
            </div>
          ) : null}
        </main>
      </section>

      <PageVerticalSlider />
    </div>
  );
}

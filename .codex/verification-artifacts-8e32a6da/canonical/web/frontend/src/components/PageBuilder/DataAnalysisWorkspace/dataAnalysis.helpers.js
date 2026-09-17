import { API_URL } from "./utils/api";

export const chartTypes = [
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

export const paletteOptions = [
  "viridis",
  "magma",
  "plasma",
  "crest",
  "rocket",
  "deep",
  "muted",
  "pastel",
];

export const palettePreviewColors = {
  viridis: ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"],
  magma: ["#000004", "#57106e", "#bc3754", "#f98e09", "#fcfdbf"],
  plasma: ["#0d0887", "#7e03a8", "#cc4778", "#f89540", "#f0f921"],
  crest: ["#2c115f", "#1f6f8b", "#3aa77f", "#9bd36a", "#f2f0a1"],
  rocket: ["#03051a", "#711f57", "#cb1b4f", "#f26b43", "#f6b48f"],
  deep: ["#4c72b0", "#dd8452", "#55a868", "#c44e52", "#8172b3"],
  muted: ["#4878d0", "#ee854a", "#6acc64", "#d65f5f", "#956cb4"],
  pastel: ["#a1c9f4", "#ffb482", "#8de5a1", "#ff9f9b", "#d0bbff"],
};

export const fontFamilyOptions = [
  "DejaVu Sans",
  "Arial",
  "Verdana",
  "Tahoma",
  "Times New Roman",
];

export const getVisualizationPlots = (visualizationResult) => {
  if (!visualizationResult) return [];
  if (Array.isArray(visualizationResult.plots)) return visualizationResult.plots;
  return [visualizationResult];
};

export const getVisualizationUrl = (plotResult, key) => {
  const url = plotResult?.[key] || "";
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return url;
  return `${API_URL}${url}`;
};

export const createVisualizationSavePath = (header, name) =>
  `${String(header || name || "madar-visualization")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "") || "madar-visualization"}-${Date.now()}.png`;

export const visualizationProfileCache = new Map();

export const deferEffectStateUpdate = (callback) => {
  let cancelled = false;
  queueMicrotask(() => {
    if (!cancelled) callback();
  });
  return () => {
    cancelled = true;
  };
};

export const userSafeErrorMessage = (
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

export const needsXColumn = (chartType) => !["heatmap"].includes(chartType);
export const needsYColumn = (chartType) =>
  ["bar", "line", "scatter", "box", "violin", "pie"].includes(chartType);
export const axisLabelsDisabled = (chartType) => ["pie", "heatmap"].includes(chartType);
export const toArray = (value) => (Array.isArray(value) ? value : value ? [value] : []);
export const hasColumnValue = (value) => toArray(value).filter(Boolean).length > 0;
export const arabicDigitMap = {
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
export const normalizeNumericText = (value) =>
  String(value ?? "")
    .trim()
    .replace(/[٠-٩۰-۹]/g, (digit) => arabicDigitMap[digit] || digit)
    .replace(/[%$€£₪،,\s]/g, "");
export const isNumericLikeValue = (value) => {
  if (value === null || value === undefined || value === "") return false;
  if (typeof value === "number") return Number.isFinite(value);

  const normalized = normalizeNumericText(value);
  if (!normalized) return false;

  return Number.isFinite(Number(normalized));
};

const normalizeColumnKey = (value) =>
  String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();

const hasAnyColumnHint = (column, hints) => {
  const normalized = normalizeColumnKey(column);
  return hints.some((hint) => normalized.includes(hint));
};

const phoneHints = ["phone", "mobile", "tel", "telephone", "whatsapp", "contact number"];
const idHints = [" id", "id ", "identifier", "code", "reference", "ref", "serial", "number"];
const moneyHints = [
  "amount",
  "budget",
  "cost",
  "expense",
  "fund",
  "funding",
  "price",
  "revenue",
  "salary",
  "payroll",
  "income",
  "payment",
  "paid",
  "donation",
  "grant",
];
const countHints = [
  "count",
  "quantity",
  "qty",
  "total",
  "team size",
  "people",
  "beneficiaries",
  "registered",
  "attended",
  "completed",
  "planned",
  "working days",
];
const ratingHints = ["rating", "score", "satisfaction", "readiness", "target", "scale"];
const dateHints = ["date", "time", "timestamp", "year", "month", "week", "day", "period"];

export const buildColumnProfiles = (columns = [], previewRows = []) =>
  columns.map((column) => {
    const values = previewRows
      .map((row) => row?.[column])
      .filter((value) => value !== null && value !== undefined && value !== "");
    const numericValues = values
      .filter(isNumericLikeValue)
      .map((value) => Number(normalizeNumericText(value)))
      .filter(Number.isFinite);
    const numericRatio = values.length ? numericValues.length / values.length : 0;
    const uniqueValues = new Set(values.map((value) => String(value).trim())).size;
    const normalized = normalizeColumnKey(column);
    const isPhone = hasAnyColumnHint(column, phoneHints);
    const isIdentifier =
      !isPhone &&
      (normalized === "id" ||
        normalized.endsWith(" id") ||
        normalized.startsWith("id ") ||
        hasAnyColumnHint(column, idHints));
    const isNumeric = numericRatio >= 0.6 && !isPhone && !isIdentifier;
    const min = numericValues.length ? Math.min(...numericValues) : null;
    const max = numericValues.length ? Math.max(...numericValues) : null;

    return {
      name: column,
      isNumeric,
      isText: !isNumeric,
      isPhone,
      isIdentifier,
      isMoney: isNumeric && hasAnyColumnHint(column, moneyHints),
      isCount: isNumeric && hasAnyColumnHint(column, countHints),
      isRating:
        isNumeric &&
        (hasAnyColumnHint(column, ratingHints) ||
          (numericValues.length > 0 && min >= 0 && max <= 10 && uniqueValues <= 11)),
      isDate: hasAnyColumnHint(column, dateHints),
      uniqueValues,
    };
  });

export const singleVariableCharts = ["histogram", "count"];
export const singlePairCharts = ["pie", "violin"];
export const multiSeriesCharts = ["bar", "line", "scatter", "box"];
export const categoryColorCharts = ["bar", "box", "violin", "count", "pie"];
export const chartRelationshipOptions = {
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
      label: "Single field",
      hint: "Select one field to show its distribution.",
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
      label: "Single field",
      hint: "Select one field to count each value.",
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
export const getRelationshipOptions = (chartType) =>
  chartRelationshipOptions[chartType] || chartRelationshipOptions.bar;
export const getDefaultComparisonMode = (chartType) =>
  getRelationshipOptions(chartType)[0]?.value || "1:1";
export const normalizeComparisonMode = (chartType, comparisonMode) => {
  const options = getRelationshipOptions(chartType);
  return options.some((option) => option.value === comparisonMode)
    ? comparisonMode
    : getDefaultComparisonMode(chartType);
};
export const getRelationshipOption = (chartType, comparisonMode) => {
  const options = getRelationshipOptions(chartType);
  const normalizedMode = normalizeComparisonMode(chartType, comparisonMode);
  return options.find((option) => option.value === normalizedMode) || options[0];
};
export const supportsUngroupedCategoryColors = (chartType) =>
  ["bar", "box", "violin", "count", "pie"].includes(chartType);
export const supportsHueGrouping = (chartType) =>
  ["bar", "line", "scatter", "histogram", "box", "violin", "count"].includes(
    chartType
  );
export const getSeriesCount = (plot) => {
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

export const getPalettePreview = (palette, count) => {
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

export const isTrendColumn = (column) =>
  /(date|time|timestamp|year|month|quarter|week|day|period)/i.test(
    String(column || "")
  );

export const shouldUseTrendGradient = (plot, xValue) => {
  if (!plot) return false;
  if (["heatmap", "box", "violin", "pie", "count", "histogram"].includes(plot.chartType)) {
    return true;
  }
  if (plot.chartType === "line") return true;
  if (!["bar", "scatter"].includes(plot.chartType)) return false;
  return toArray(xValue || plot.xColumns || plot.xColumn).some(isTrendColumn);
};

export const validateVisualizationPlot = (plot, numericColumns = []) => {
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

export const getFriendlyVisualizationError = (message) => {
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

export const createVisualizationPlot = (index, columns = [], numericColumns = []) => ({
  id: `plot-${index}`,
  name: `Chart ${index}`,
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
  header: `Chart ${index}`,
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

export const normalizeChartLabel = (value, fallback = "Chart") => {
  const text = String(value || "").trim();
  if (!text) return fallback;
  return text.replace(/^Plot(\s+\d+)?$/i, (match, numberPart = "") => `Chart${numberPart}`);
};

export const DATA_WORKSPACE_CACHE_VERSION = 1;
export const DATA_WORKSPACE_CACHE_TTL_MS = 24 * 60 * 60 * 1000;
export const DATA_WORKSPACE_CACHE_WRITE_DELAY_MS = 150;
export const dataWorkspaceMemoryCache = new Map();
export const dataWorkspaceCacheWriteTimers = new Map();

export const getDataWorkspaceCacheKey = (user, project) => {
  const userId = user?.id || user?.email || "anonymous";
  const projectId = project?.id || project?.slug || project?.name || "default";
  return `madar:data-workspace:${userId}:${projectId}:v${DATA_WORKSPACE_CACHE_VERSION}`;
};

export const safeReadDataWorkspaceCache = (storageKey) => {
  if (typeof window === "undefined") return null;

  try {
    const memoryValue = dataWorkspaceMemoryCache.get(storageKey);
    const memorySavedAt = Number(memoryValue?.savedAt || 0);

    if (memoryValue && Date.now() - memorySavedAt <= DATA_WORKSPACE_CACHE_TTL_MS) {
      if (!Object.prototype.hasOwnProperty.call(memoryValue, "dataset")) return memoryValue;
      const metadataOnlyValue = { ...memoryValue };
      delete metadataOnlyValue.dataset;
      dataWorkspaceMemoryCache.set(storageKey, metadataOnlyValue);
      return metadataOnlyValue;
    }

    dataWorkspaceMemoryCache.delete(storageKey);

    const rawValue = window.localStorage.getItem(storageKey);
    if (!rawValue) return null;

    const cachedValue = JSON.parse(rawValue);
    const savedAt = Number(cachedValue?.savedAt || 0);
    const isExpired = Date.now() - savedAt > DATA_WORKSPACE_CACHE_TTL_MS;

    if (isExpired) {
      window.localStorage.removeItem(storageKey);
      return null;
    }

    // Legacy versions cached dataset previews in localStorage. Remove them during migration.
    if (Object.prototype.hasOwnProperty.call(cachedValue, "dataset")) {
      delete cachedValue.dataset;
      window.localStorage.setItem(storageKey, JSON.stringify(cachedValue));
    }

    dataWorkspaceMemoryCache.set(storageKey, cachedValue);
    return cachedValue;
  } catch {
    window.localStorage.removeItem(storageKey);
    return null;
  }
};

export const safeWriteDataWorkspaceCache = (storageKey, payload) => {
  if (typeof window === "undefined") return;

  const cachedValue = {
    ...payload,
    savedAt: Date.now(),
    version: DATA_WORKSPACE_CACHE_VERSION,
  };

  // Route-to-route navigation reads this hot cache without parsing localStorage.
  dataWorkspaceMemoryCache.set(storageKey, cachedValue);

  const pendingTimer = dataWorkspaceCacheWriteTimers.get(storageKey);
  if (pendingTimer) window.clearTimeout(pendingTimer);

  const timerId = window.setTimeout(() => {
    dataWorkspaceCacheWriteTimers.delete(storageKey);

    try {
      window.localStorage.setItem(storageKey, JSON.stringify(cachedValue));
    } catch {
      // localStorage can be full or blocked; the in-memory cache still works.
    }
  }, DATA_WORKSPACE_CACHE_WRITE_DELAY_MS);

  dataWorkspaceCacheWriteTimers.set(storageKey, timerId);
};

export const getCacheableDataset = (dataset) => {
  if (!dataset?.file_path) return null;

  return {
    file_path: dataset.file_path,
    original_filename: dataset.original_filename || dataset.file_path,
    rows: dataset.rows,
    columns: Array.isArray(dataset.columns) ? dataset.columns : [],
    preview: Array.isArray(dataset.preview) ? dataset.preview.slice(0, 100) : [],
  };
};

export const getRestorableDataWorkspaceStep = (step) =>
  ["review", "prepare"].includes(step) ? step : "review";

export const mergeAnalysisResponses = (current, next) => {
  if (!current?.results) return next;
  if (!next?.results) return current;

  const results = { ...current.results };
  Object.entries(next.results).forEach(([key, value]) => {
    let outputKey = key;
    let suffix = 2;
    while (Object.prototype.hasOwnProperty.call(results, outputKey)) {
      outputKey = `${key} (${suffix++})`;
    }
    results[outputKey] = value;
  });

  return {
    ...next,
    results,
    warnings: [...(current.warnings || []), ...(next.warnings || [])],
  };
};

export const friendlyAnalysisTitle = (title) => {
  const titles = {
    "Form response overview": "Dataset overview",
    "Numeric question summary": "Column statistics",
    "Assisted analysis": "Question results",
  };
  return titles[title] || title || "Report calculations";
};

import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, ArrowLeft, ArrowRight, Check, ChevronDown, Download, Eye, X } from "lucide-react";

import { uiText } from "../constants/uiText";
import { analysisGroups } from "../constants/analysisConfig";
import { API_URL, authFetch, getFriendlyExternalError, readApiResponse } from "../utils/api";
import { cleanObject, escapeCsvValue } from "../utils/formatters";
import { getMissingRequiredParams } from "../utils/validation";

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
  { id: "count", label: "Count" },
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
const toArray = (value) => (Array.isArray(value) ? value : value ? [value] : []);
const hasColumnValue = (value) => toArray(value).filter(Boolean).length > 0;
const singleVariableCharts = ["histogram", "count"];
const singlePairCharts = ["pie", "box", "violin"];
const multiSeriesCharts = ["bar", "line", "scatter"];
const categoryColorCharts = ["bar", "box", "violin", "count", "pie"];
const supportsUngroupedCategoryColors = (chartType) =>
  ["bar", "count", "pie"].includes(chartType);
const supportsHueGrouping = (chartType) =>
  ["bar", "line", "scatter", "histogram", "box", "violin", "count"].includes(
    chartType
  );
const getSeriesCount = (plot) => {
  if (!plot || !multiSeriesCharts.includes(plot.chartType)) return 1;
  if (plot.comparisonMode === "1:M") {
    return Math.max(1, toArray(plot.yColumns).filter(Boolean).length);
  }
  if (plot.comparisonMode === "M:M") {
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
  if (plot.chartType === "line") return true;
  if (!["bar", "scatter"].includes(plot.chartType)) return false;
  return toArray(xValue || plot.xColumns || plot.xColumn).some(isTrendColumn);
};

const getComparisonHint = (plot) => {
  if (plot.chartType === "heatmap") {
    return "Heatmap uses the numeric columns in the dataset, so no axis selection is needed.";
  }

  if (singleVariableCharts.includes(plot.chartType)) {
    return "This chart uses one X variable. Pick the column you want to distribute or count.";
  }

  if (singlePairCharts.includes(plot.chartType)) {
    return "This plot type compares one label/group column with one numeric value column.";
  }

  if (plot.comparisonMode === "1:M") {
    return "Use one shared X axis, like time, with many Y series, like revenue for several projects.";
  }

  if (plot.comparisonMode === "M:M") {
    return "Pair each X variable with the Y variable in the same position. The lists must have the same length.";
  }

  return "Use one X variable and one Y variable for a direct comparison.";
};

const validateVisualizationPlot = (plot) => {
  const chartType = plot?.chartType;
  const xCount = toArray(plot?.xColumns).filter(Boolean).length;
  const yCount = toArray(plot?.yColumns).filter(Boolean).length;
  const plotName = plot?.name || "this plot";

  if (!plot) return "Choose a plot before generating.";
  if (chartType === "heatmap") return "";

  if (plot.comparisonMode !== "M:M" && xCount > 1) {
    return `${plotName} has ${xCount} X variables selected. Use one X variable per plot, or create ${xCount} separate plots.`;
  }

  if (singleVariableCharts.includes(chartType)) {
    return xCount >= 1 ? "" : `Choose one X variable for ${plotName}.`;
  }

  if (singlePairCharts.includes(chartType)) {
    return xCount === 1 && yCount === 1
      ? ""
      : `${plotName} needs exactly one X variable and one Y variable for ${chartType}.`;
  }

  if (!multiSeriesCharts.includes(chartType)) {
    return "";
  }

  if (plot.comparisonMode === "1:M") {
    return xCount === 1 && yCount >= 1
      ? ""
      : `${plotName} 1:M needs one X variable and one or more Y variables.`;
  }

  if (plot.comparisonMode === "M:M") {
    if (xCount < 1 || yCount < 1) {
      return `${plotName} M:M needs at least one X variable and one Y variable.`;
    }

    return xCount === yCount
      ? ""
      : `${plotName} M:M needs matching X and Y counts. You selected ${xCount} X and ${yCount} Y.`;
  }

  return xCount === 1 && yCount === 1
    ? ""
    : `${plotName} 1:1 needs exactly one X variable and one Y variable.`;
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

  const userApiPath = (path) => {
    if (!user?.id) {
      throw new Error(t.sessionExpired || "Your session has expired.");
    }

    return `${API_URL}/users/${encodeURIComponent(user.id)}${path}`;
  };

  const availableForms = project?.forms || [];
  const firstFormWithResponses =
    availableForms.find((form) => form.responses?.length) || availableForms[0];

  const [currentStep, setCurrentStep] = useState("source");
  const [sourceMode, setSourceMode] = useState("forms");
  const [selectedFormId, setSelectedFormId] = useState(
    firstFormWithResponses?.id || ""
  );
  const [dataset, setDataset] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [externalUrl, setExternalUrl] = useState("");
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

  const [reportOptions, setReportOptions] = useState({
    title: "",
    includeSummary: true,
    includeKpis: true,
    includeInsights: true,
    includeTables: true,
    includeCharts: true,
    includeWarnings: true,
  });
  const [isVisualizationSettingsOpen, setIsVisualizationSettingsOpen] =
    useState(false);
  const [visualizationPlots, setVisualizationPlots] = useState(() => [
    createVisualizationPlot(1),
  ]);
  const [visualizationResultsByPlot, setVisualizationResultsByPlot] = useState({});
  const [visualizationPreview, setVisualizationPreview] = useState(null);
  const [activeVisualizationPlotId, setActiveVisualizationPlotId] =
    useState("plot-1");
  const [openAxisDropdown, setOpenAxisDropdown] = useState("");
  const activeColorInputRef = useRef(null);
  const visualizationNoticeRequestRef = useRef(0);

  const [cleaning, setCleaning] = useState({
    trimText: true,
    lowercaseText: false,
    removeDuplicates: false,
    removeMissingRows: false,
    fillMissing: false,
    fillColumn: "",
    fillMethod: "mode",
    fillValue: "",
    removeOutliers: false,
    outlierColumns: [],
    dropColumns: [],
    convertColumn: "",
    convertType: "numeric",
    renameColumn: "",
    renameTo: "",
  });

  const [analysisDomain, setAnalysisDomain] = useState("finance");
  const [analysisMethod, setAnalysisMethod] = useState(
    analysisGroups.finance.methods[0].id
  );
  const [params, setParams] = useState({
    ...analysisGroups.finance.methods[0].template,
  });

  const selectedForm =
    availableForms.find((form) => form.id === selectedFormId) ||
    firstFormWithResponses;

  const formFields = selectedForm ? getFormFields(selectedForm) : [];
  const methods = analysisGroups[analysisDomain].methods;
  const activeMethod =
    methods.find((method) => method.id === analysisMethod) || methods[0];

  const columns = useMemo(() => dataset?.columns || [], [dataset]);

  const numericColumns = useMemo(() => {
    const preview = dataset?.preview || [];

    return columns.filter((column) =>
      preview.some((row) => Number.isFinite(Number(row[column])))
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
    if (!columns.length) return;

    setVisualizationPlots((currentPlots) =>
      currentPlots.map((plot) => ({
        ...plot,
        xColumn: plot.xColumn || columns[0] || "",
        yColumn: plot.yColumn || numericColumns[0] || columns[1] || "",
        xColumns: plot.xColumns?.length ? plot.xColumns : columns[0] ? [columns[0]] : [],
        yColumns: plot.yColumns?.length
          ? plot.yColumns
          : numericColumns[0]
          ? [numericColumns[0]]
          : columns[1]
          ? [columns[1]]
          : [],
      }))
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
              <p>{visualizationPreview.label}</p>
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
            {visualizationPreview.inspectUrl &&
            visualizationPreview.inspectUrl !== visualizationPreview.url ? (
              <a
                className="daw-secondary"
                href={visualizationPreview.inspectUrl}
                target="_blank"
                rel="noreferrer"
              >
                Open inspector
              </a>
            ) : null}
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

    if (cleaning.removeOutliers && cleaning.outlierColumns.length) {
      actions.push({
        type: "remove_outliers_iqr",
        params: { columns: cleaning.outlierColumns, multiplier: 1.5 },
      });
    }

    if (cleaning.dropColumns.length) {
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
        plot.id === plotId
          ? {
              ...plot,
              chartType,
              comparisonMode: multiSeriesCharts.includes(chartType)
                ? plot.comparisonMode
                : "1:1",
            }
          : plot
      )
    );
  };

  const updateVisualizationColumns = (plotId, key, values) => {
    const nextValues = values.filter(Boolean);
    const currentPlot =
      visualizationPlots.find((plot) => plot.id === plotId) ||
      activeVisualizationPlot;
    const nextPlot = currentPlot
      ? {
          ...currentPlot,
          [key]: nextValues,
          ...(key === "xColumns" ? { xColumn: nextValues[0] || "" } : {}),
          ...(key === "yColumns" ? { yColumn: nextValues[0] || "" } : {}),
        }
      : null;

    setVisualizationPlots((currentPlots) =>
      currentPlots.map((plot) =>
        plot.id === plotId
          ? {
              ...plot,
              [key]: nextValues,
              ...(key === "xColumns" ? { xColumn: nextValues[0] || "" } : {}),
              ...(key === "yColumns" ? { yColumn: nextValues[0] || "" } : {}),
            }
          : plot
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
        onChange(value ? [value] : []);
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
            {options.map((option) => {
              const isSelected = selected.includes(option);
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
                  onClick={() => toggleValue(option)}
                >
                  <span className="daw-multi-select-check">
                    {isSelected ? <Check size={13} /> : null}
                  </span>
                  <span>{option}</span>
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
      width,
      height,
    } = plot || {};
    const nextX = overrides.xColumn ?? xColumn;
    const nextY = overrides.yColumn ?? yColumn;
    const nextXLabel = Array.isArray(nextX) ? nextX.join(" / ") : nextX;
    const nextYLabel = Array.isArray(nextY) ? nextY.join(" / ") : nextY;
    const titleSuffix = overrides.titleSuffix ? ` ${overrides.titleSuffix}` : "";
    const seriesCount = Math.max(1, toArray(nextY).filter(Boolean).length);
    const seriesNames = toArray(nextY).filter(Boolean);
    const shouldUseSeriesPalette =
      multiSeriesCharts.includes(chartType) &&
      ["1:M", "M:M"].includes(comparisonMode);
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
      orientation: chartType === "bar" ? barOrientation || "vertical" : "",
      x: needsXColumn(chartType) ? nextX : "",
      y: needsYColumn(chartType) ? nextY : "",
      hue: supportsHueGrouping(chartType) ? hueColumn : "",
      title: `${fallbackTitle}${titleSuffix}`,
      x_label: String(xLabel || "").trim(),
      y_label: String(yLabel || "").trim(),
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
        categoryPalette.length > 1
          ? false
          : typeof useGradient === "boolean"
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

    if (!needsYColumn(chartType)) {
      return [
        buildSingleVisualizationConfig(plot, {
          xColumn: toArray(plot.xColumns)[0] || plot.xColumn,
        }),
      ];
    }

    if (plot.comparisonMode === "1:M") {
      return [
        buildSingleVisualizationConfig(plot, {
          xColumn: toArray(plot.xColumns)[0] || plot.xColumn,
          yColumn: toArray(plot.yColumns),
        }),
      ];
    }

    if (plot.comparisonMode === "M:M") {
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

  const profileVisualizationColumns = async (plot) => {
    const columnsToProfile = [
      ...toArray(plot?.xColumns),
      ...toArray(plot?.yColumns),
      plot?.hueColumn,
    ].filter(Boolean);

    if (!columnsToProfile.length) return null;

    const response = await authFetch(userApiPath("/visualization/columns/profile"), {
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

    return data;
  };

  const getVisualizationColorNotice = (plot, profileData, changedKey = "") => {
    const profiles = profileData?.profiles || {};
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

    if (plot?.comparisonMode !== "1:1" && toArray(plot?.yColumns).filter(Boolean).length > 1) {
      return "More than one Y variable is selected, so colors identify each series.";
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

  const setLoadedDataset = (data) => {
    setDataset(data);
    setInspection(null);
    setInspectionCache({});
    setAnalysisResult(null);
    setVisualizationResultsByPlot({});
    setVisualizationPreview(null);
    setAssistResult(null);
    setCurrentStep("review");
  };

  const uploadFile = async (file) => {
    if (!file) {
      showFlowError(t.chooseFileFirst);
      return;
    }

    const payload = new FormData();
    payload.append("file", file);

    setIsLoading(true);
    setAnalysisError("");

    try {
      const response = await authFetch(userApiPath("/data/upload"), {
        method: "POST",
        credentials: "include",
        body: payload,
      });

      const data = await readApiResponse(response);

      if (!response.ok) {
        throw new Error(data.detail || "The data could not be loaded.");
      }

      setLoadedDataset(data);
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
      const response = await authFetch(userApiPath("/data/read"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_path: inputPath }),
      });

      const data = await readApiResponse(response);

      if (!response.ok) {
        throw new Error(getFriendlyExternalError(data.detail));
      }

      setLoadedDataset({
        ...data,
        file_path: data.file_path || inputPath,
        original_filename: data.original_filename || inputPath,
      });
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

    await uploadFile(file);
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
      const response = await authFetch(userApiPath(paths[type]), {
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
      const response = await authFetch(userApiPath("/analysis/run"), {
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

    const validationMessage = validateVisualizationPlot(plot);
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
        const response = await authFetch(userApiPath("/visualization/create"), {
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

      const nextVisualizationResult =
        results.length === 1 ? results[0] : { plots: results };

      setVisualizationResultsByPlot((current) => ({
        ...current,
        [plot.id]: nextVisualizationResult,
      }));
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
      showVisualizationError(error.message);
    } finally {
      setIsLoading(false);
    }
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
      const response = await authFetch(userApiPath("/analysis/assist"), {
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
              const seriesCount = getSeriesCount(plot);
              const usesSeriesPalette =
                multiSeriesCharts.includes(chartType) &&
                ["1:M", "M:M"].includes(plot.comparisonMode);
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

                    <Field label="Comparison">
                      <select
                        value={plot.comparisonMode}
                        disabled={!multiSeriesCharts.includes(chartType)}
                        onChange={(event) =>
                          updateVisualizationPlot(
                            plot.id,
                            "comparisonMode",
                            event.target.value
                          )
                        }
                      >
                        <option value="1:1">1:1 comparison</option>
                        <option value="1:M">1:M comparison</option>
                        <option value="M:M">M:M comparison</option>
                      </select>
                    </Field>

                    <div className="daw-comparison-hint">
                      <span>{plot.comparisonMode}</span>
                      <p>{getComparisonHint(plot)}</p>
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

                    {chartType === "bar" ? (
                      <Field label="Bar direction">
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
                          <option value="vertical">Vertical bars</option>
                          <option value="horizontal">Horizontal bars</option>
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

                    {needsXColumn(chartType) || needsYColumn(chartType) ? (
                      <div className="daw-axis-select-row">
                        {needsXColumn(chartType) ? (
                          <Field
                            label={
                              plot.comparisonMode === "M:M" &&
                              multiSeriesCharts.includes(chartType)
                                ? "X variables"
                                : chartType === "pie"
                                ? "Label column"
                                : "X axis"
                            }
                          >
                            {(() => {
                              const multiple =
                                plot.comparisonMode === "M:M" &&
                                multiSeriesCharts.includes(chartType);
                              const selectedValues = toArray(plot.xColumns);

                              return renderColumnDropdown({
                                id: `${plot.id}-x`,
                                options: columns,
                                selectedValues,
                                multiple,
                                placeholder: multiple
                                  ? "Select X variables"
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
                              (plot.comparisonMode === "1:M" ||
                                plot.comparisonMode === "M:M") &&
                              multiSeriesCharts.includes(chartType)
                                ? "Y variables"
                                : chartType === "pie"
                                ? "Value column"
                                : "Y axis"
                            }
                          >
                            {(() => {
                              const yOptions = columns;
                              const multiple =
                                (plot.comparisonMode === "1:M" ||
                                  plot.comparisonMode === "M:M") &&
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
                                options: yOptions,
                                selectedValues,
                                multiple,
                                colorMap,
                                placeholder: multiple
                                  ? "Select Y variables"
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
                        value={plot.xLabel}
                        onChange={(event) =>
                          updateVisualizationPlot(plot.id, "xLabel", event.target.value)
                        }
                      />
                    </Field>

                    <Field label="Y label">
                      <input
                        value={plot.yLabel}
                        onChange={(event) =>
                          updateVisualizationPlot(plot.id, "yLabel", event.target.value)
                        }
                      />
                    </Field>

                    <Field label="Palette">
                      <select
                        value={plot.palette}
                        disabled={plot.useSingleColor && !usesSeriesPalette}
                        onChange={(event) =>
                          updateVisualizationPlot(plot.id, "palette", event.target.value)
                        }
                      >
                        {paletteOptions.map((palette) => (
                          <option key={palette} value={palette}>
                            {palette}
                          </option>
                        ))}
                      </select>
                    </Field>

                    {["bar", "line", "scatter", "histogram"].includes(chartType) ? (
                    <Field label="Trend gradient">
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
                        Adds gradient emphasis for time-based trends, lines, and ranking bars.
                      </small>
                    </Field>
                    ) : null}

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
                              disabled={
                                chartType === "histogram" &&
                                !plot.hueColumn &&
                                Boolean(plot.useGradient)
                              }
                              onChange={(event) => {
                                const nextPlot = {
                                  ...plot,
                                  useSingleColor: event.target.checked,
                                };
                                updateVisualizationPlot(
                                  plot.id,
                                  "useSingleColor",
                                  event.target.checked
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
                                updateVisualizationPlot(plot.id, "useSingleColor", true);
                              }
                            }}
                            onBlur={() => {
                              activeColorInputRef.current = null;
                            }}
                            onChange={(event) => {
                              const nextColor = event.target.value;
                              const nextPlot = {
                                ...plot,
                                color: nextColor,
                                useSingleColor: true,
                              };
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
                              refreshVisualizationSelectionNotice(
                                nextPlot,
                                "useSingleColor"
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
          numericColumns={numericColumns}
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
            <button
              type="button"
              className="daw-primary daw-open-settings-button"
              onClick={() => setIsVisualizationSettingsOpen(true)}
              disabled={!dataset}
            >
              Open plot settings
            </button>
          </div>

          <div className="daw-plot-summary-grid">
            {visualizationPlots.map((plot, index) => {
              const chartTypeLabel =
                chartTypes.find((type) => type.id === plot.chartType)?.label ||
                "Chart";
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
                    {plot.comparisonMode ? ` / ${plot.comparisonMode}` : ""}
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
                            key={`${plot.id}_output_${outputIndex}`}
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

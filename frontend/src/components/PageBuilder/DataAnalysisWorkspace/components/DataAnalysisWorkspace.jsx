import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Check, ChevronDown, Download, Eye, Plus, Trash2, X } from "lucide-react";

import { uiText } from "../constants/uiText";
import { API_URL, getFriendlyExternalError, readApiResponse } from "../utils/api";
import { downloadCsv, downloadXlsxFromCsv, sanitizeSpreadsheetCell } from "../utils/dataframeExport";
import { cleanObject, escapeCsvValue } from "../utils/formatters";
import {
  archiveItem,
  loadDataset as loadSavedDataset,
  saveDataset as saveDatasetLocally,
} from "../utils/datasetStorage";
import { apiFetch } from "../../../../utils/apiClient";

import Stepper from "./Stepper";
import DataSourceStep from "./DataSourceStep";
import DatasetReviewStep from "./DatasetReviewStep";
import PrepareDataStep from "./PrepareDataStep";
import ReportBuilderStep from "./ReportBuilderStep";
import AssistantPanel from "./AssistantPanel";
import PageVerticalSlider from "./PageVerticalSlider";
import Field from "./Field";
import {
  DataAnalysisFlowToast,
  VisualizationPreviewModal,
  VisualizationStatusMessage,
} from "./DataAnalysisStates";
import {
  axisLabelsDisabled,
  buildColumnProfiles,
  categoryColorCharts,
  chartTypes,
  createVisualizationPlot,
  createVisualizationSavePath,
  deferEffectStateUpdate,
  fontFamilyOptions,
  friendlyAnalysisTitle,
  getCacheableDataset,
  getDataWorkspaceCacheKey,
  getFriendlyVisualizationError,
  getPalettePreview,
  getRelationshipOption,
  getRelationshipOptions,
  getRestorableDataWorkspaceStep,
  getSeriesCount,
  getVisualizationPlots,
  getVisualizationUrl,
  hasColumnValue,
  multiSeriesCharts,
  needsXColumn,
  needsYColumn,
  normalizeChartLabel,
  normalizeComparisonMode,
  paletteOptions,
  safeReadDataWorkspaceCache,
  safeWriteDataWorkspaceCache,
  shouldUseTrendGradient,
  supportsHueGrouping,
  supportsUngroupedCategoryColors,
  toArray,
  userSafeErrorMessage,
  validateVisualizationPlot,
  visualizationProfileCache,
} from "../dataAnalysis.helpers";

function VisualizationSettingsModalRenderer({ renderModal }) {
  return renderModal();
}

const createDefaultCleaning = () => ({
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
  convertColumn: "",
  convertType: "numeric",
  renameColumn: "",
  renameTo: "",
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
  const dataWorkspaceCacheKey = getDataWorkspaceCacheKey(user, project);
  const archiveScope = user?.id ? `user-${user.id}` : "";
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
    "source"
  );
  const [sourceMode, setSourceMode] = useState(
    () => cachedWorkspace?.sourceMode || "forms"
  );
  const [selectedFormId, setSelectedFormId] = useState(
    () => cachedWorkspace?.selectedFormId || firstFormWithResponses?.id || ""
  );
  const [dataset, setDataset] = useState(null);
  const [isDatasetStorageReady, setIsDatasetStorageReady] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [externalUrl, setExternalUrl] = useState(
    () => cachedWorkspace?.externalUrl || ""
  );
  const [inspection, setInspection] = useState(null);
  const [inspectionCache, setInspectionCache] = useState({});
  const [analysisResult, setAnalysisResult] = useState(null);
  const [assistQuestion, setAssistQuestion] = useState("");
  const [assistResult, setAssistResult] = useState(null);
  const [, setAnalysisError] = useState("");
  const [flowToast, setFlowToast] = useState("");
  const [visualizationError, setVisualizationError] = useState("");
  const [visualizationSuccess, setVisualizationSuccess] = useState("");
  const [visualizationNotice, setVisualizationNotice] = useState("");
  const [isVisualizationChecking, setIsVisualizationChecking] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [dataframesSaved, setDataframesSaved] = useState(
    () => Boolean(cachedWorkspace?.dataframesSaved)
  );
  const [savedDataframeExport, setSavedDataframeExport] = useState(null);

  const [reportOptions] = useState(() => ({
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
      ? cachedWorkspace.visualizationPlots.map((plot, index) => ({
          ...plot,
          name: normalizeChartLabel(plot.name, `Chart ${index + 1}`),
          header: normalizeChartLabel(plot.header, `Chart ${index + 1}`),
        }))
      : [createVisualizationPlot(1)]
  );
  const [visualizationResultsByPlot, setVisualizationResultsByPlot] = useState({});
  const [visualizationPreview, setVisualizationPreview] = useState(null);
  const [activeVisualizationPlotId, setActiveVisualizationPlotId] = useState(
    () => cachedWorkspace?.activeVisualizationPlotId || "plot-1"
  );
  const [openAxisDropdown, setOpenAxisDropdown] = useState("");
  const visualizationNoticeRequestRef = useRef(0);
  const autoOverviewInspectionPathRef = useRef("");

  const getNextVisualizationNoticeRequestId = useCallback(() => {
    visualizationNoticeRequestRef.current += 1;
    return visualizationNoticeRequestRef.current;
  }, []);

  const isLatestVisualizationNoticeRequest = useCallback(
    (requestId) => visualizationNoticeRequestRef.current === requestId,
    []
  );

  const [cleaning, setCleaning] = useState(() => ({
    ...createDefaultCleaning(),
    ...(cachedWorkspace?.cleaning || {}),
  }));

  const selectedForm =
    availableForms.find((form) => form.id === selectedFormId) ||
    firstFormWithResponses;

  const formFields = selectedForm ? getFormFields(selectedForm) : [];
  const columns = useMemo(() => dataset?.columns || [], [dataset]);
  const columnSet = useMemo(() => new Set(columns), [columns]);
  const columnProfiles = useMemo(
    () => buildColumnProfiles(columns, dataset?.preview || []),
    [columns, dataset]
  );

  const numericColumns = useMemo(() => {
    return columnProfiles
      .filter((profile) => profile.isNumeric)
      .map((profile) => profile.name);
  }, [columnProfiles]);

  const textColumns = useMemo(
    () =>
      columnProfiles
        .filter((profile) => !profile.isNumeric)
        .map((profile) => profile.name),
    [columnProfiles]
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
    let cancelled = false;

    loadSavedDataset({ scope: dataWorkspaceCacheKey })
      .then((saved) => {
        if (cancelled || !saved?.dataset?.file_path) return;
        const restoredDataframesSaved = Boolean(
          saved.dataframesSaved || cachedWorkspace?.dataframesSaved
        );
        const restoredStep = getRestorableDataWorkspaceStep(cachedWorkspace?.currentStep);
        setDataset(saved.dataset);
        setDataframesSaved(restoredDataframesSaved);
        setSavedDataframeExport(saved.cleanedDataframe || null);
        setSelectedFile(saved.file instanceof File ? saved.file : null);
        setCurrentStep(
          !restoredDataframesSaved && ["visualization", "report"].includes(restoredStep)
            ? "prepare"
            : restoredStep
        );
      })
      .catch(() => {
        if (!cancelled) setFlowToast("The locally saved dataset could not be restored.");
      })
      .finally(() => {
        if (!cancelled) setIsDatasetStorageReady(true);
      });

    return () => {
      cancelled = true;
    };
  }, [cachedWorkspace?.currentStep, cachedWorkspace?.dataframesSaved, dataWorkspaceCacheKey]);

  useEffect(() => {
    if (!isDatasetStorageReady) return;

    safeWriteDataWorkspaceCache(dataWorkspaceCacheKey, {
      currentStep: getRestorableDataWorkspaceStep(currentStep),
      sourceMode,
      selectedFormId,
      externalUrl,
      cleaning,
      dataframesSaved,
      reportOptions,
      visualizationPlots,
      activeVisualizationPlotId,
    });
  }, [
    activeVisualizationPlotId,
    cleaning,
    currentStep,
    dataframesSaved,
    dataWorkspaceCacheKey,
    externalUrl,
    reportOptions,
    selectedFormId,
    sourceMode,
    visualizationPlots,
    isDatasetStorageReady,
  ]);

  useEffect(() => {
    if (!columns.length) return;

    return deferEffectStateUpdate(() => {
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
    });
  }, [columns, numericColumns]);

  useEffect(() => {
    if (!isVisualizationSettingsOpen) return undefined;

    const blurActiveColorInput = (target) => {
      const activeColorInput =
        document.activeElement instanceof HTMLInputElement &&
        document.activeElement.matches('input[type="color"]')
          ? document.activeElement
          : null;

      if (
        activeColorInput &&
        !target.closest(".daw-series-color-row") &&
        !target.closest(".daw-color-control")
      ) {
        activeColorInput.blur();
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
      if (
        document.activeElement instanceof HTMLInputElement &&
        document.activeElement.matches('input[type="color"]')
      ) {
        document.activeElement.blur();
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

  const cleaningActions = useMemo(() => {
    const actions = [];
    const confirmedDropColumns =
      cleaning.dropColumnsConfirmed && Array.isArray(cleaning.dropColumns)
        ? cleaning.dropColumns.filter((column) => columnSet.has(column))
        : [];
    const encodedColumns = Array.isArray(cleaning.encodeColumns)
      ? cleaning.encodeColumns.filter((column) => columnSet.has(column))
      : [];
    const cleanableTextColumns = textColumns.filter((column) => columnSet.has(column));

    if (cleaning.trimText && cleanableTextColumns.length) {
      actions.push({
        type: "clean_text_columns",
        params: {
          columns: cleanableTextColumns,
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

    if (cleaning.fillMissing && cleaning.fillColumn && columnSet.has(cleaning.fillColumn)) {
      const config = { method: cleaning.fillMethod };

      if (cleaning.fillMethod === "constant") {
        config.value = cleaning.fillValue;
      }

      actions.push({
        type: "fill_missing",
        params: { fill_map: { [cleaning.fillColumn]: config } },
      });
    }

    if (
      cleaning.convertColumn &&
      columnSet.has(cleaning.convertColumn) &&
      !confirmedDropColumns.includes(cleaning.convertColumn)
    ) {
      actions.push({
        type: "convert_column_types",
        params: {
          type_map: { [cleaning.convertColumn]: cleaning.convertType },
        },
      });
    }

    if (encodedColumns.length) {
      actions.push({
        type: "encode_columns",
        params: {
          columns: encodedColumns,
          method: cleaning.encodeMethod,
        },
      });
    }

    if (
      cleaning.renameColumn &&
      cleaning.renameTo.trim() &&
      columnSet.has(cleaning.renameColumn) &&
      !confirmedDropColumns.includes(cleaning.renameColumn) &&
      !encodedColumns.includes(cleaning.renameColumn)
    ) {
      actions.push({
        type: "rename_column",
        params: {
          rename_map: { [cleaning.renameColumn]: cleaning.renameTo.trim() },
        },
      });
    }

    const finalDropColumns = confirmedDropColumns.filter(
      (column) => !encodedColumns.includes(column)
    );

    if (finalDropColumns.length) {
      actions.push({
        type: "drop_columns",
        params: { columns: finalDropColumns },
      });
    }

    return actions;
  }, [cleaning, columnSet, textColumns]);

  const updateCleaning = (key, value) => {
    setCleaning((current) => ({ ...current, [key]: value }));
    setDataframesSaved(false);
    setAnalysisResult(null);
  };

  const updateVisualizationPlot = (plotId, key, value) => {
    setVisualizationPlots((currentPlots) =>
      currentPlots.map((plot) =>
        plot.id === plotId ? { ...plot, [key]: value } : plot
      )
    );
  };

  const addVisualizationPlot = () => {
    const nextIndex =
      Math.max(
        0,
        ...visualizationPlots.map((plot) => {
          const match = String(plot.id || "").match(/plot-(\d+)/);
          return match ? Number(match[1]) : 0;
        })
      ) + 1;
    const nextPlot = createVisualizationPlot(nextIndex, columns, numericColumns);

    setVisualizationPlots((currentPlots) => [...currentPlots, nextPlot]);
    setActiveVisualizationPlotId(nextPlot.id);
    setIsVisualizationSettingsOpen(true);
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
      save_path: createVisualizationSavePath(header, name),
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

    if (visualizationProfileCache.has(cacheKey)) {
      return visualizationProfileCache.get(cacheKey);
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

    visualizationProfileCache.set(cacheKey, data);
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

    const requestId = getNextVisualizationNoticeRequestId();
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
      if (!isLatestVisualizationNoticeRequest(requestId)) return;
      applyVisualizationCategoryColors(nextPlot, profileData);
      setVisualizationNotice(nextNotice);
      setIsVisualizationChecking(false);
    } catch (error) {
      if (!isLatestVisualizationNoticeRequest(requestId)) return;
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

  const setLoadedDataset = (data, sourceContext = {}) => {
    autoOverviewInspectionPathRef.current = "";
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
    setCleaning(createDefaultCleaning());
    setDataframesSaved(false);
    setSavedDataframeExport(null);
    setCurrentStep("review");
  };

  const getDatasetArchiveTitle = (data, fallback = "Dataset") =>
    data?.original_filename ||
    data?.name ||
    data?.file_path?.split(/[\\/]/).pop() ||
    fallback;

  const archiveLoadedDataset = async (data, sourceContext = {}) => {
    if (!data?.file_path) return;

    const exportResponse = await apiFetch(userApiPath("/data/export"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_path: data.file_path }),
    });
    const loadedDataframe = await readApiResponse(exportResponse);

    if (!exportResponse.ok) {
      throw new Error(loadedDataframe.detail || "The loaded dataset could not be archived.");
    }

    await archiveItem({
      type: "loaded_dataset",
      scope: archiveScope,
      title: getDatasetArchiveTitle(data, "Loaded dataset"),
      description: "Original loaded dataset before cleaning.",
      payload: {
        dataset: getCacheableDataset(data),
        loadedDataframe,
        sourceMode: sourceContext.sourceMode || sourceMode,
        selectedFormId: sourceContext.selectedFormId || selectedFormId,
        externalUrl: sourceContext.externalUrl || externalUrl,
        savedAt: Date.now(),
      },
    });
  };

  const saveDataframes = async () => {
    if (!dataset?.file_path) {
      showFlowError(t.loadDataBeforeAnalysis);
      return;
    }

    setIsLoading(true);
    setAnalysisError("");

    try {
      const cleanedResponse = await apiFetch(userApiPath("/cleaning/export"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_path: dataset.file_path,
          actions: cleaningActions,
        }),
      });
      const cleanedDataframe = await readApiResponse(cleanedResponse);

      if (!cleanedResponse.ok) {
        throw new Error(
          cleanedDataframe.detail || "The cleaned dataframe could not be exported."
        );
      }

      await saveDatasetLocally(
        {
          dataset: getCacheableDataset(dataset),
          cleanedDataframe,
          sourceMode,
          selectedFormId,
          externalUrl,
          cleaning,
          cleaningActions,
          dataframesSaved: true,
          savedAt: Date.now(),
        },
        { scope: dataWorkspaceCacheKey }
      );
      await archiveItem({
        type: "cleaned_dataset",
        scope: archiveScope,
        title:
          dataset.original_filename ||
          dataset.name ||
          dataset.file_path?.split(/[\\/]/).pop() ||
          "Saved cleaned dataset",
        description: "Cleaned dataset saved from the data workspace.",
        payload: {
          dataset: getCacheableDataset(dataset),
          cleanedDataframe,
          sourceMode,
          selectedFormId,
          externalUrl,
          cleaning,
          cleaningActions,
          savedAt: Date.now(),
        },
      });
      setDataframesSaved(true);
      setSavedDataframeExport(cleanedDataframe);
      setFlowToast("");
    } catch (error) {
      showFlowError(error.message || "The dataframes could not be saved.");
    } finally {
      setIsLoading(false);
    }
  };

  const getDataframeExportName = () =>
    getDatasetArchiveTitle(dataset, "madar-dataset");

  const downloadSavedDataframe = (format) => {
    const csv = savedDataframeExport?.csv;

    if (!dataframesSaved || !csv) {
      showFlowError(t.saveDataframesFirst || "Save your data before downloading it.");
      return;
    }

    if (format === "xlsx") {
      downloadXlsxFromCsv(csv, getDataframeExportName());
      return;
    }

    downloadCsv(csv, getDataframeExportName());
  };

  const archiveVisualizationOutput = useCallback(
    async (plotConfig, output, description = "Saved from the chart workspace.") => {
      if (!output) return;

      await archiveItem({
        type: "chart",
        scope: archiveScope,
        title:
          plotConfig?.header ||
          plotConfig?.name ||
          output.chart_path?.split(/[\\/]/).pop() ||
          "Saved plot",
        description,
        payload: {
          output,
          url: getVisualizationUrl(output, "chart_url"),
          chartType: plotConfig?.chartType || "",
          plotConfig,
          cleaningActions,
          datasetName:
            dataset?.original_filename ||
            dataset?.name ||
            dataset?.file_path?.split(/[\\/]/).pop() ||
            "",
          dataset: getCacheableDataset(dataset),
        },
      });
    },
    [archiveScope, cleaningActions, dataset]
  );

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
        throw new Error(data.detail || t.loadDataFailed || uiText.en.loadDataFailed);
      }

      await saveDatasetLocally(
        {
          dataset: getCacheableDataset(data),
          file,
          sourceMode: sourceContext.sourceMode || "upload",
          savedAt: Date.now(),
        },
        { scope: dataWorkspaceCacheKey }
      );

      setLoadedDataset(data, {
        sourceMode: sourceContext.sourceMode || "upload",
        selectedFormId: sourceContext.selectedFormId,
      });
      await archiveLoadedDataset(data, {
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

      const loadedDataset = {
        ...data,
        file_path: data.file_path || inputPath,
        original_filename: data.original_filename || inputPath,
      };

      setLoadedDataset(
        loadedDataset,
        {
          sourceMode: "external",
          externalUrl: inputPath,
        }
      );
      await saveDatasetLocally(
        {
          dataset: getCacheableDataset(loadedDataset),
          sourceMode: "external",
          savedAt: Date.now(),
        },
        { scope: dataWorkspaceCacheKey }
      );
      await archiveLoadedDataset(loadedDataset, {
        sourceMode: "external",
        externalUrl: inputPath,
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
      .map((row) => row.map((value) => escapeCsvValue(sanitizeSpreadsheetCell(value))).join(","))
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

  useEffect(() => {
    const filePath = dataset?.file_path;
    if (!filePath || autoOverviewInspectionPathRef.current === filePath) return;

    autoOverviewInspectionPathRef.current = filePath;
    setCurrentStep("review");
    runInspection("overview");
    // Auto-inspection should run once per dataset file; runInspection also depends on mutable cache state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset?.file_path]);

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

      await Promise.all(
        results.map((result) =>
          archiveVisualizationOutput(plot, result, "Generated plot saved from the chart workspace.")
        )
      );

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
          ? "Chart created successfully."
          : `${results.length} charts created successfully.`
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

  const deleteVisualizationOutput = async (plotId, outputIndex) => {
    const plotConfig =
      visualizationPlots.find((plot) => plot.id === plotId) || null;
    const output = getVisualizationPlots(visualizationResultsByPlot[plotId])[
      outputIndex
    ];

    if (output) {
      try {
        await archiveVisualizationOutput(
          plotConfig,
          output,
          "Deleted plot saved from the chart workspace."
        );
      } catch {
        showVisualizationError("The plot could not be archived before deleting.");
        return;
      }
    }

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

    const outputs = Object.values(analysisResult.results).filter(Boolean);
    return {
      kpis: outputs.flatMap((output) =>
        (output.kpis || []).map((item) => ({
          ...item,
          analysisTitle: output.title || "Backend analysis",
        }))
      ),
      tables: outputs.flatMap((output) =>
        (output.tables || []).map((item) => ({
          ...item,
          analysisTitle: output.title || "Backend analysis",
        }))
      ),
      charts: outputs.flatMap((output) => output.charts || []),
      summaries: outputs.map((output) => output.summary).filter(Boolean),
      warnings: outputs.flatMap((output) => output.warnings || []),
    };
  }, [analysisResult]);

  const reportMetrics = useMemo(() => {
    const backendMetrics = Array.isArray(analysisPayload?.kpis)
      ? analysisPayload.kpis
      : [];
    const assistedMetrics = Array.isArray(assistResult?.kpis)
      ? assistResult.kpis
      : [];

    return [
      ...backendMetrics.map((metric, index) => ({
        ...metric,
        id: `backend-metric-${index}`,
        sourceGroup: friendlyAnalysisTitle(metric.analysisTitle),
        displayLabel: metric.label,
      })),
      ...assistedMetrics.map((metric, index) => ({
        ...metric,
        id: `assisted-metric-${index}`,
        sourceGroup: "Question results",
        displayLabel: metric.label,
      })),
    ].map((metric) => {
      if (metric.sourceGroup !== "Column statistics") return metric;
      const separatorIndex = String(metric.label || "").lastIndexOf(" - ");
      if (separatorIndex < 0) return metric;
      return {
        ...metric,
        sourceGroup: `Column: ${metric.label.slice(0, separatorIndex)}`,
        displayLabel: metric.label.slice(separatorIndex + 3),
      };
    });
  }, [analysisPayload, assistResult]);

  const reportTables = useMemo(() => {
    const backendTables = Array.isArray(analysisPayload?.tables)
      ? analysisPayload.tables
      : [];
    const assistedTables = Array.isArray(assistResult?.tables)
      ? assistResult.tables
      : [];

    return [
      ...backendTables.map((table, index) => ({
        ...table,
        id: `backend-table-${index}`,
        sourceGroup: friendlyAnalysisTitle(table.analysisTitle),
        displayLabel: table.title,
      })),
      ...assistedTables.map((table, index) => ({
        ...table,
        id: `assisted-table-${index}`,
        sourceGroup: "Question results",
        displayLabel: table.title,
      })),
    ];
  }, [analysisPayload, assistResult]);

  const reportGeneratedPlots = useMemo(
    () =>
      Object.values(visualizationResultsByPlot)
        .flatMap((result) => getVisualizationPlots(result))
        .map((result, index) => ({
          id: result.chart_path || `generated-plot-${index + 1}`,
          title:
            result.chart_path?.split(/[\\/]/).pop() ||
            `Chart ${index + 1}`,
          src: getVisualizationUrl(result, "chart_url"),
          sourceGroup: "Charts",
          displayLabel:
            result.chart_path?.split(/[\\/]/).pop() ||
            `Chart ${index + 1}`,
        }))
        .filter((plot) => plot.src),
    [visualizationResultsByPlot]
  );

  const archiveReportDocument = useCallback(
    async (document) => {
      if (!document?.blocks?.length) return;

      const datasetName =
        dataset?.original_filename ||
        dataset?.name ||
        dataset?.file_path?.split(/[\\/]/).pop() ||
        "Current dataset";
      const reportTitle = document.report?.title || "Untitled report";
      const reportKey =
        document.archiveId ||
        `${dataWorkspaceCacheKey}-${dataset?.file_path || datasetName}`
          .replace(/[^\w.-]+/g, "-")
          .slice(0, 140);

      try {
        await archiveItem({
          id: reportKey.startsWith("report-") ? reportKey : `report-${reportKey}`,
          type: "report",
          scope: archiveScope,
          title: reportTitle,
          description: `Report draft for ${datasetName}.`,
          payload: {
            ...document,
            datasetName,
          },
        });
      } catch {
        showFlowError("The report could not be saved to the archive.");
      }
    },
    [archiveScope, dataWorkspaceCacheKey, dataset]
  );

  const goToPreviousStep = () => {
    const order = ["source", "review", "prepare", "visualization", "report"];
    const currentIndex = order.indexOf(currentStep);
    setCurrentStep(order[Math.max(0, currentIndex - 1)]);
  };

  const showSavedDataRequiredWarning = () => {
    showFlowError(
      t.saveDataframesFirst ||
        "Save dataframes after cleaning your data before opening Charts or Report."
    );
    setCurrentStep("prepare");
  };

  const goToNextStep = () => {
    if (currentStep === "prepare" && !dataframesSaved) {
      showSavedDataRequiredWarning();
      return;
    }

    const order = ["source", "review", "prepare", "visualization", "report"];
    const currentIndex = order.indexOf(currentStep);
    setCurrentStep(order[Math.min(order.length - 1, currentIndex + 1)]);
  };

  const renderVisualizationSettingsModal = () => {
    if (!isVisualizationSettingsOpen) return null;

    const plot = activeVisualizationPlot || visualizationPlots[0];
    const index = Math.max(
      0,
      visualizationPlots.findIndex((currentPlot) => currentPlot.id === plot?.id)
    );
    if (!plot) return null;

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
              <span className="daw-kicker">Charts</span>
              <h3 id="daw-visualization-settings-title">
                Chart setup
              </h3>
              <p>Chart details for this report.</p>
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
            {(() => {
              const chartType = plot.chartType;
              const relationshipOptions = getRelationshipOptions(chartType);
              const activeComparisonMode = normalizeComparisonMode(
                chartType,
                plot.comparisonMode
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
                      <span>Chart {index + 1}</span>
                      <h4>{plot.header || plot.name}</h4>
                    </div>
                  </div>

                  <div className="daw-modal-grid">
                    <Field label="Chart name">
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
                        placeholder={`Chart ${index + 1}`}
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
                        placeholder={`${selectedChartLabel} chart`}
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
                        Apply the selected palette as a gradient.
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
                                    onFocus={() => {
                                      setOpenAxisDropdown("");
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
                            onFocus={() => {
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
                          Turn off to use the selected palette.
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
                                  onFocus={() => {
                                    setOpenAxisDropdown("");
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
            })()}
          </div>

          <VisualizationStatusMessage
            error={visualizationError}
            success={visualizationSuccess}
            notice={visualizationNotice}
            issueTitle={t.flowIssueTitle}
            onDismiss={() => {
              setVisualizationError("");
              setVisualizationSuccess("");
              setVisualizationNotice("");
            }}
          />

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
                {isLoading ? t.working : "Create chart"}
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
        <>
          <PrepareDataStep
            dataset={dataset}
            columns={columns}
            textColumns={textColumns}
            cleaning={cleaning}
            updateCleaning={updateCleaning}
            onSaveDataframes={saveDataframes}
            onDownloadDataframe={downloadSavedDataframe}
            isSavingDataframes={isLoading}
            dataframesSaved={dataframesSaved}
            canDownloadDataframes={Boolean(savedDataframeExport?.csv)}
            t={t}
          />
        </>
      );
    }

    if (currentStep === "visualization") {
      return (
        <div className="daw-section-card daw-visualization-builder">
          <div className="daw-visualization-builder-header">
            <div>
              <span className="daw-kicker">Charts</span>
              <h3>Create chart</h3>
              <p>Charts prepared for this report.</p>
            </div>
            <button
              type="button"
              className="daw-secondary daw-add-chart-button"
              onClick={addVisualizationPlot}
              disabled={!dataset}
            >
              <Plus size={16} />
              Add chart
            </button>
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
                  <div className="daw-plot-card-header">
                    <div>
                      <span>Chart {index + 1}</span>
                      <strong>{plot.header || plot.name}</strong>
                    </div>
                    <button
                      type="button"
                      className="daw-secondary"
                      onClick={() => {
                        setActiveVisualizationPlotId(plot.id);
                        setIsVisualizationSettingsOpen(true);
                      }}
                    >
                      Edit chart
                    </button>
                  </div>

                  <div className="daw-plot-meta-row">
                    <span>{chartTypeLabel}</span>
                    {relationshipLabel ? <span>{relationshipLabel}</span> : null}
                    {needsXColumn(plot.chartType) ? (
                      <span>X: {toArray(plot.xColumns).join(", ") || "Not selected"}</span>
                    ) : null}
                    {needsYColumn(plot.chartType) ? (
                      <span>Y: {toArray(plot.yColumns).join(", ") || "Not selected"}</span>
                    ) : null}
                  </div>
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
                            : `Chart ${outputIndex + 1}`;

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
                              <span>Chart</span>
                              <strong>{outputLabel}</strong>
                            </div>
                            <div className="daw-plot-output-actions">
                              {downloadUrl ? (
                                <a
                                  className="daw-icon-button"
                                  href={downloadUrl}
                                  download
                                  title="Download chart"
                                  aria-label={`Download ${plot.header || plot.name}`}
                                >
                                  <Download size={17} />
                                </a>
                              ) : null}
                              {inspectUrl ? (
                                <button
                                  type="button"
                                  className="daw-icon-button"
                                  title="Inspect chart"
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
                                title="Delete chart"
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
                  ) : (
                    <div className="daw-plot-empty-output">
                      Create this chart to generate a preview file.
                    </div>
                  )}
                </article>
              );
            })}
          </div>

          <div className="daw-visualization-actions">
            <button
              type="button"
              className="daw-secondary daw-add-chart-button"
              onClick={addVisualizationPlot}
              disabled={!dataset}
            >
              <Plus size={16} />
              Add chart
            </button>
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
                {isLoading ? t.working : "Create chart"}
              </button>
            )}
          </div>
        </div>
      );
    }

    return (
      <>
        <ReportBuilderStep
          dataset={dataset}
          availablePlots={reportGeneratedPlots}
          availableMetrics={reportMetrics}
          availableTables={reportTables}
          onDocumentChange={archiveReportDocument}
          archiveScope={archiveScope}
          datasetName={
            dataset?.original_filename ||
            dataset?.name ||
            dataset?.file_path?.split(/[\\/]/).pop() ||
            "Current dataset"
          }
        />
        <AssistantPanel
          dataset={dataset}
          assistQuestion={assistQuestion}
          setAssistQuestion={setAssistQuestion}
          runAssistedQuestion={runAssistedQuestion}
          assistResult={assistResult}
          isLoading={isLoading}
          t={t}
        />
      </>
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
        dataframesSaved={dataframesSaved}
        onLockedStep={showSavedDataRequiredWarning}
        t={t}
      />

      <DataAnalysisFlowToast
        message={flowToast}
        title={t.flowIssueTitle}
        onDismiss={() => setFlowToast("")}
      />

      <VisualizationSettingsModalRenderer renderModal={renderVisualizationSettingsModal} />
      <VisualizationPreviewModal
        preview={visualizationPreview}
        onClose={() => setVisualizationPreview(null)}
      />

      <section className={`daw-layout daw-step-${currentStep}`}>
        <main className="daw-flow" id="daw-workspace-main">
          <div className="daw-step-content">
            {renderCurrentStep()}

          </div>

          {currentStep !== "source" && currentStep !== "report" && currentStep !== "visualization" ? (
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
          ) : null}

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

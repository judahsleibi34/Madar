import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReportLibraryPanel from "./report-builder/ReportLibraryPanel";
import ReportPageCanvas from "./report-builder/ReportPageCanvas";
import ReportPropertiesPanel from "./report-builder/ReportPropertiesPanel";
import { reportBlockDefaults } from "./report-builder/reportBuilderConfig";
import { archiveItem, listArchiveItems } from "../utils/datasetStorage";
import "../../../../styles/admin/PageBuilder/data-analysis/24-report-builder.css";

const escapeHtml = (value = "") =>
  String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

const isUnsafeFileNameCharacter = (character) =>
  '<>:"/\\|?*'.includes(character) || character.charCodeAt(0) < 32;

const normalizeFileName = (value = "report") =>
  String(value || "report")
    .trim()
    .split("")
    .map((character) => (isUnsafeFileNameCharacter(character) ? "-" : character))
    .join("")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 90) || "report";

const createReportArchiveId = () =>
  `report-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const textToHtml = (value = "") =>
  escapeHtml(value)
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => `<p>${line}</p>`)
    .join("") || "<p></p>";

const renderReportBlockHtml = (block) => {
  const style = [
    block.backgroundColor ? `background:${escapeHtml(block.backgroundColor)}` : "",
    block.textColor ? `color:${escapeHtml(block.textColor)}` : "",
  ]
    .filter(Boolean)
    .join(";");
  const styleAttr = style ? ` style="${style}"` : "";
  const title = escapeHtml(block.title || "");

  if (block.type === "spacer") {
    return `<div class="report-spacer" style="height:${Number(block.spacerHeight || 40)}px"></div>`;
  }

  if (block.type === "heading") {
    return `<section class="report-block report-heading"${styleAttr}><h2>${title}</h2></section>`;
  }

  if (block.type === "text") {
    return `<section class="report-block"${styleAttr}>${
      block.hideTitle ? "" : `<h3>${title}</h3>`
    }${textToHtml(block.body)}</section>`;
  }

  if (block.type === "metric") {
    return `<section class="report-block report-metric"${styleAttr}><h3>${title}</h3><strong>${escapeHtml(
      block.body || ""
    )}</strong></section>`;
  }

  if (block.type === "chart" && block.src) {
    return `<section class="report-block"${styleAttr}><h3>${title}</h3><img class="report-chart" src="${escapeHtml(
      block.src
    )}" alt="${title || "Chart"}" /></section>`;
  }

  if (block.type === "image" && block.src) {
    return `<section class="report-block report-image"${styleAttr}><img src="${escapeHtml(
      block.src
    )}" alt="${title || "Report image"}" /><p>${escapeHtml(block.body || "")}</p></section>`;
  }

  if (block.type === "table" && block.rows?.length) {
    const columns = Object.keys(block.rows[0]);
    const header = columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("");
    const rows = block.rows
      .map(
        (row) =>
          `<tr>${columns
            .map((column) => `<td>${escapeHtml(row[column] ?? "")}</td>`)
            .join("")}</tr>`
      )
      .join("");
    return `<section class="report-block"${styleAttr}><h3>${title}</h3><table><thead><tr>${header}</tr></thead><tbody>${rows}</tbody></table></section>`;
  }

  return "";
};

const buildReportHtml = ({ report, blocks }) => {
  const title = report.title?.trim() || "Untitled report";
  const body = blocks.length
    ? blocks.map(renderReportBlockHtml).join("")
    : `<section class="report-empty"><p>No blocks yet.</p></section>`;

  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(title)}</title>
  <style>
    @page { size: A4; margin: 18mm; }
    * { box-sizing: border-box; }
    body { margin: 0; background: #f4f6fb; color: #172033; font-family: Arial, Helvetica, sans-serif; }
    .report-page { max-width: 794px; min-height: 1123px; margin: 0 auto; padding: 56px 68px; background: #ffffff; }
    .report-header { display: flex; align-items: center; gap: 18px; border-bottom: 1px solid #d8deeb; padding-bottom: 18px; margin-bottom: 28px; background: ${escapeHtml(
      report.headerBackground || "transparent"
    )}; }
    .report-header img { max-width: 86px; max-height: 58px; object-fit: contain; }
    h1 { margin: 0; font-size: 28px; line-height: 1.2; }
    h2 { margin: 0 0 10px; font-size: 22px; line-height: 1.25; }
    h3 { margin: 0 0 8px; font-size: 16px; line-height: 1.3; }
    p { margin: 0 0 10px; color: #46546d; font-size: 12px; line-height: 1.65; }
    .report-block { margin-bottom: 22px; padding: 0; break-inside: avoid; }
    .report-heading { border-bottom: 1px solid #e3e8f2; padding-bottom: 8px; }
    .report-metric strong { display: block; font-size: 30px; line-height: 1.1; color: #172033; }
    .report-chart, .report-image img { width: 100%; max-height: 520px; object-fit: contain; border: 1px solid #e3e8f2; }
    .report-image p { text-align: center; margin-top: 8px; }
    table { width: 100%; border-collapse: collapse; font-size: 11px; break-inside: auto; }
    th, td { border: 1px solid #d8deeb; padding: 7px 8px; text-align: left; vertical-align: top; }
    th { background: #eef3fb; color: #172033; font-weight: 700; }
    tr { break-inside: avoid; }
    .report-empty { border: 1px dashed #b9c3d7; border-radius: 8px; padding: 32px; text-align: center; }
    @media print {
      body { background: #ffffff; }
      .report-page { margin: 0; max-width: none; box-shadow: none; }
    }
  </style>
</head>
<body>
  <main class="report-page">
    <header class="report-header">
      ${report.logo ? `<img src="${escapeHtml(report.logo)}" alt="Report logo" />` : ""}
      <h1>${escapeHtml(title)}</h1>
    </header>
    ${body}
  </main>
</body>
</html>`;
};

export default function ReportBuilderStep({
  availablePlots = [],
  availableMetrics = [],
  availableTables = [],
  onDocumentChange,
  archiveScope = "",
  datasetName = "",
}) {
  const nextBlockId = useRef(1);
  const [reportArchiveId, setReportArchiveId] = useState(() => createReportArchiveId());
  const [report, setReport] = useState({
    title: "Untitled report",
    titleDirection: "auto",
    headerBackground: "",
    logo: "",
  });
  const [blocks, setBlocks] = useState([]);
  const [selectedBlockId, setSelectedBlockId] = useState("");
  const [isPreviewMode, setIsPreviewMode] = useState(false);
  const [savedReports, setSavedReports] = useState([]);
  const [selectedSavedReportId, setSelectedSavedReportId] = useState("");
  const [saveStatus, setSaveStatus] = useState("");
  const selectedBlock = blocks.find((block) => block.id === selectedBlockId) || null;

  const updateReport = (key, value) => setReport((current) => ({ ...current, [key]: value }));

  const loadSavedReports = useCallback(async () => {
    const items = await listArchiveItems({ scope: archiveScope });
    const reports = items.filter((item) => item.type === "report");
    setSavedReports(reports);
    return reports;
  }, [archiveScope]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadSavedReports().catch(() => setSaveStatus("Saved reports could not be loaded."));
    }, 0);

    return () => window.clearTimeout(timer);
  }, [loadSavedReports]);

  useEffect(() => {
    if (typeof onDocumentChange !== "function" || !blocks.length) return undefined;

    const timeoutId = window.setTimeout(() => {
      onDocumentChange({
        archiveId: reportArchiveId,
        report,
        blocks,
        savedAt: Date.now(),
      });
    }, 800);

    return () => window.clearTimeout(timeoutId);
  }, [blocks, onDocumentChange, report, reportArchiveId]);

  const buildReportDocument = () => ({
    archiveId: reportArchiveId,
    report,
    blocks,
    savedAt: Date.now(),
    datasetName,
  });

  const saveReport = async () => {
    const title = report.title?.trim() || "Untitled report";
    const document = buildReportDocument();

    try {
      await archiveItem({
        id: reportArchiveId,
        type: "report",
        scope: archiveScope,
        title,
        description: datasetName ? `Report draft for ${datasetName}.` : "Saved report draft.",
        payload: document,
      });
      setSelectedSavedReportId(reportArchiveId);
      setSaveStatus(`Saved "${title}".`);
      await loadSavedReports();
    } catch {
      setSaveStatus("The report could not be saved.");
    }
  };

  const loadReport = (reportId) => {
    setSelectedSavedReportId(reportId);
    const item = savedReports.find((savedReport) => savedReport.id === reportId);
    const document = item?.payload;
    if (!document?.report) return;

    const loadedBlocks = Array.isArray(document.blocks) ? document.blocks : [];
    setReport({
      title: document.report.title || item.title || "Untitled report",
      titleDirection: document.report.titleDirection || "auto",
      headerBackground: document.report.headerBackground || "",
      logo: document.report.logo || "",
    });
    setBlocks(loadedBlocks);
    setSelectedBlockId("");
    setIsPreviewMode(false);
    setReportArchiveId(item.id || document.archiveId || createReportArchiveId());
    nextBlockId.current =
      Math.max(
        0,
        ...loadedBlocks.map((block) => Number(String(block.id || "").match(/(\d+)$/)?.[1] || 0))
      ) + 1;
    setSaveStatus(`Opened "${item.title || document.report.title || "Untitled report"}".`);
  };

  const createNewReport = () => {
    setReportArchiveId(createReportArchiveId());
    setReport({
      title: "Untitled report",
      titleDirection: "auto",
      headerBackground: "",
      logo: "",
    });
    setBlocks([]);
    setSelectedBlockId("");
    setSelectedSavedReportId("");
    setIsPreviewMode(false);
    nextBlockId.current = 1;
    setSaveStatus("New report started.");
  };

  const getGeneratedContent = (type, sourceId = "") => {
    if (type === "chart" && !availablePlots.length) return;
    if (type === "metric" && !availableMetrics.length) return;
    if (type === "table" && !availableTables.length) return;

    const metric = availableMetrics.find((item) => item.id === sourceId) || availableMetrics[0];
    const table = availableTables.find((item) => item.id === sourceId) || availableTables[0];
    const plot = availablePlots.find((item) => item.id === sourceId) || availablePlots[0];

    if (type === "chart") {
      return { title: plot.title, body: "", src: plot.src, sourceId: plot.id };
    }
    if (type === "metric") {
      return {
        title: metric.label,
        body: metric.display_value || String(metric.value ?? ""),
        sourceId: metric.id,
      };
    }
    if (type === "table") {
      return { title: table.title, body: "", rows: table.rows || [], sourceId: table.id };
    }
    return {};
  };

  const reportVariables = useMemo(
    () => [
      ...availableMetrics.map((item) => ({
        id: item.id,
        type: "metric",
        label: item.displayLabel || item.label || "Number",
        group: item.sourceGroup || "Report variables",
        value: item.display_value || String(item.value ?? ""),
      })),
      ...availableTables.map((item) => ({
        id: item.id,
        type: "table",
        label: item.displayLabel || item.title || "Table",
        group: item.sourceGroup || "Report variables",
        value: `${Array.isArray(item.rows) ? item.rows.length : 0} rows`,
      })),
      ...availablePlots.map((item) => ({
        id: item.id,
        type: "chart",
        label: item.displayLabel || item.title || "Chart",
        group: item.sourceGroup || "Charts",
        value: "Chart",
      })),
    ],
    [availableMetrics, availablePlots, availableTables]
  );

  const insertBlock = (type, index = blocks.length, sourceId = "") => {
    const generatedContent = getGeneratedContent(type, sourceId);
    if (!generatedContent) return;

    const id = `report-block-${nextBlockId.current++}`;
    setBlocks((current) => {
      const next = [...current];
      next.splice(Math.max(0, Math.min(index, next.length)), 0, {
        id,
        type,
        ...reportBlockDefaults[type],
        ...generatedContent,
      });
      return next;
    });
    setSelectedBlockId(id);
  };

  const insertParagraph = (index) => {
    const id = `report-block-${nextBlockId.current++}`;
    setBlocks((current) => {
      const next = [...current];
      next.splice(Math.max(0, Math.min(index, next.length)), 0, {
        id,
        type: "text",
        title: "",
        body: "",
        hideTitle: true,
      });
      return next;
    });
    setSelectedBlockId(id);
    window.requestAnimationFrame(() => {
      document
        .querySelector(`[data-report-block-id="${id}"] .daw-report-block-body`)
        ?.focus();
    });
  };

  const moveBlockToIndex = (blockId, targetIndex) => {
    setBlocks((current) => {
      const sourceIndex = current.findIndex((block) => block.id === blockId);
      if (sourceIndex < 0) return current;
      const next = [...current];
      const [moving] = next.splice(sourceIndex, 1);
      const adjustedIndex = sourceIndex < targetIndex ? targetIndex - 1 : targetIndex;
      next.splice(Math.max(0, Math.min(adjustedIndex, next.length)), 0, moving);
      return next;
    });
    setSelectedBlockId(blockId);
  };

  const addBlock = (type) => insertBlock(type, blocks.length);
  const addGeneratedSource = (type, sourceId) => insertBlock(type, blocks.length, sourceId);

  const insertImage = (src, fileName) => {
    const id = `report-block-${nextBlockId.current++}`;
    setBlocks((current) => [
      ...current,
      {
        id,
        type: "image",
        title: fileName || "Image",
        body: "",
        src,
        imageWidthPercent: 76,
        imageRatio: "original",
        imageOffsetX: 0,
        imageOffsetY: 0,
      },
    ]);
    setSelectedBlockId(id);
  };

  const updateSelectedBlock = (key, value) => {
    setBlocks((current) => current.map((block) =>
      block.id === selectedBlockId ? { ...block, [key]: value } : block
    ));
  };

  const updateBlock = (blockId, key, value) => {
    setBlocks((current) => current.map((block) =>
      block.id === blockId ? { ...block, [key]: value } : block
    ));
  };

  const updateGeneratedSource = (type, sourceId) => {
    const sources =
      type === "metric"
        ? availableMetrics
        : type === "table"
        ? availableTables
        : availablePlots;
    const source = sources.find((item) => item.id === sourceId);
    if (!source) return;

    setBlocks((current) =>
      current.map((block) => {
        if (block.id !== selectedBlockId) return block;
        if (type === "metric") {
          return {
            ...block,
            sourceId,
            title: source.label,
            body: source.display_value || String(source.value ?? ""),
          };
        }
        if (type === "table") {
          return { ...block, sourceId, title: source.title, rows: source.rows || [] };
        }
        return { ...block, sourceId, title: source.title, src: source.src };
      })
    );
  };

  const moveSelectedBlock = (direction) => {
    setBlocks((current) => {
      const index = current.findIndex((block) => block.id === selectedBlockId);
      const nextIndex = index + direction;
      if (index < 0 || nextIndex < 0 || nextIndex >= current.length) return current;
      const next = [...current];
      [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
      return next;
    });
  };

  const removeSelectedBlock = () => {
    setBlocks((current) => current.filter((block) => block.id !== selectedBlockId));
    setSelectedBlockId("");
  };

  const handleLogoChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => updateReport("logo", String(reader.result || ""));
    reader.readAsDataURL(file);
  };

  const exportFileName = normalizeFileName(report.title || "report");

  const exportWord = () => {
    const html = buildReportHtml({ report, blocks });
    const blob = new Blob(["\ufeff", html], { type: "application/msword;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${exportFileName}.doc`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const exportPdf = () => {
    const html = buildReportHtml({ report, blocks });
    const printWindow = window.open("", "_blank");
    if (!printWindow) return;
    printWindow.document.open();
    printWindow.document.write(html);
    printWindow.document.close();
    window.setTimeout(() => {
      printWindow.focus();
      printWindow.print();
    }, 350);
  };

  return (
    <section className={`daw-report-builder ${isPreviewMode ? "is-preview" : ""}`} aria-label="Report builder">
      <ReportLibraryPanel
        logo={report.logo}
        onLogoChange={handleLogoChange}
        onRemoveLogo={() => updateReport("logo", "")}
        onAddBlock={addBlock}
        onAddGeneratedSource={addGeneratedSource}
        reportVariables={reportVariables}
        reportTitle={report.title}
        onReportTitleChange={(value) => updateReport("title", value)}
        savedReports={savedReports}
        selectedSavedReportId={selectedSavedReportId}
        onSelectSavedReport={loadReport}
        onCreateNewReport={createNewReport}
        onSaveReport={saveReport}
        saveStatus={saveStatus}
        availability={{
          chart: availablePlots.length > 0,
          metric: availableMetrics.length > 0,
          table: availableTables.length > 0,
        }}
        isPreviewMode={isPreviewMode}
        isExportDisabled={!blocks.length}
        onExportPdf={exportPdf}
        onExportWord={exportWord}
        onTogglePreview={() => {
          setIsPreviewMode((current) => !current);
          setSelectedBlockId("");
        }}
      />
      <ReportPageCanvas
        report={report}
        blocks={blocks}
        selectedBlockId={selectedBlockId}
        onSelectBlock={setSelectedBlockId}
        onUpdateReport={updateReport}
        onUpdateBlock={updateBlock}
        onInsertImage={insertImage}
        onInsertBlock={insertBlock}
        onInsertParagraph={insertParagraph}
        onMoveBlockToIndex={moveBlockToIndex}
        isPreviewMode={isPreviewMode}
        onTogglePreview={() => {
          setIsPreviewMode((current) => !current);
          setSelectedBlockId("");
        }}
      />
      <ReportPropertiesPanel
        report={report}
        selectedBlock={selectedBlock}
        onUpdateReport={updateReport}
        onUpdateBlock={updateSelectedBlock}
        onMoveBlock={moveSelectedBlock}
        onRemoveBlock={removeSelectedBlock}
        availableMetrics={availableMetrics}
        availableTables={availableTables}
        availablePlots={availablePlots}
        onSelectGeneratedSource={updateGeneratedSource}
      />
    </section>
  );
}

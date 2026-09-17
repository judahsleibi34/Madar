import { useMemo, useState } from "react";
import { BarChart3, Download, Eye, FileText, ImagePlus, LayoutDashboard, Table2 } from "lucide-react";
import { REPORT_BLOCK_DRAG_TYPE, reportBlockTypes } from "./reportBuilderConfig";

export default function ReportLibraryPanel({
  logo,
  onLogoChange,
  onRemoveLogo,
  onAddBlock,
  onAddGeneratedSource,
  reportVariables = [],
  reportTitle = "",
  onReportTitleChange,
  savedReports = [],
  selectedSavedReportId = "",
  onSelectSavedReport,
  onCreateNewReport,
  onSaveReport,
  saveStatus = "",
  availability = {},
  isPreviewMode = false,
  onTogglePreview,
  onExportPdf,
  onExportWord,
  isExportDisabled = false,
}) {
  const [logoFileName, setLogoFileName] = useState("");

  const handleLogoChange = (event) => {
    setLogoFileName(event.target.files?.[0]?.name || "");
    onLogoChange?.(event);
  };

  const handleRemoveLogo = () => {
    setLogoFileName("");
    onRemoveLogo?.();
  };

  const groupedVariables = useMemo(
    () =>
      reportVariables.reduce((groups, variable) => {
        const group = variable.group || "Report variables";
        if (!groups[group]) groups[group] = [];
        groups[group].push(variable);
        return groups;
      }, {}),
    [reportVariables]
  );

  const variableIcons = {
    metric: LayoutDashboard,
    table: Table2,
    chart: BarChart3,
  };

  return (
    <aside className="daw-report-panel daw-report-library">
      <div className="daw-report-panel-heading">
        <span>Report</span>
        <h3>Blocks</h3>
        <p>Choose the sections for this report.</p>
      </div>

      {onTogglePreview ? (
        <button type="button" className="daw-report-preview-button" onClick={onTogglePreview}>
          <Eye size={15} />
          {isPreviewMode ? "Back to editing" : "Preview report"}
        </button>
      ) : null}

      <div className="daw-report-save-panel">
        <label>
          <span>Report file name</span>
          <input
            type="text"
            value={reportTitle}
            placeholder="Untitled report"
            onChange={(event) => onReportTitleChange?.(event.target.value)}
          />
        </label>

        <label>
          <span>Work on saved report</span>
          <select
            value={selectedSavedReportId}
            onChange={(event) => onSelectSavedReport?.(event.target.value)}
          >
            <option value="">Current report</option>
            {savedReports.map((savedReport) => (
              <option key={savedReport.id} value={savedReport.id}>
                {savedReport.title || savedReport.payload?.report?.title || "Untitled report"}
              </option>
            ))}
          </select>
        </label>

        <div className="daw-report-save-actions">
          <button type="button" className="daw-report-preview-button" onClick={onCreateNewReport}>
            New report
          </button>
          <button type="button" className="daw-report-preview-button" onClick={onSaveReport}>
            Save report
          </button>
        </div>

        {saveStatus ? <p>{saveStatus}</p> : null}
      </div>

      <div className="daw-report-export-actions" aria-label="Report export options">
        <button
          type="button"
          className="daw-report-preview-button"
          disabled={isExportDisabled}
          onClick={onExportPdf}
        >
          <Download size={15} />
          Export PDF
        </button>
        <button
          type="button"
          className="daw-report-preview-button"
          disabled={isExportDisabled}
          onClick={onExportWord}
        >
          <FileText size={15} />
          Export Word
        </button>
      </div>

      <label className="daw-report-logo-control">
        <span><ImagePlus size={16} /> Report logo</span>
        <span className="daw-report-file-button">
          <input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" onChange={handleLogoChange} />
          <strong>Choose logo</strong>
          <em>{logoFileName || (logo ? "Logo selected" : "No file selected")}</em>
        </span>
      </label>
      {logo ? (
        <button type="button" className="daw-report-remove-logo" onClick={handleRemoveLogo}>Remove logo</button>
      ) : null}

      <div className="daw-report-block-library">
        <div className="daw-report-library-heading">
          <strong>Library</strong>
        </div>
        {reportBlockTypes.filter(({ type }) => type !== "image").map(({ type, label, description, icon: Icon }) => {
          const requiresOutput = ["metric", "chart", "table"].includes(type);
          const isAvailable = !requiresOutput || availability[type];
          return (
          <button
            key={type}
            type="button"
            draggable={isAvailable}
            disabled={!isAvailable}
            title={isAvailable ? `Click to add ${label}, or drag it into the document` : `No generated ${label.toLowerCase()} is available`}
            onClick={() => onAddBlock(type)}
            onDragStart={(event) => {
              event.dataTransfer.effectAllowed = "copy";
              event.dataTransfer.setData(REPORT_BLOCK_DRAG_TYPE, type);
              event.currentTarget.classList.add("is-dragging");
            }}
            onDragEnd={(event) => event.currentTarget.classList.remove("is-dragging")}
          >
            <Icon size={18} />
            <span><strong>{label}</strong><small>{description}</small></span>
          </button>
          );
        })}
        {!availability.metric && !availability.chart && !availability.table ? (
          <div className="daw-report-no-generated-blocks">
            <p>No saved charts or report tables yet.</p>
          </div>
        ) : null}
      </div>

      <div className="daw-report-variable-library">
        <div className="daw-report-library-heading">
          <strong>Variables</strong>
          <span>{reportVariables.length ? `${reportVariables.length} ready` : "Save data first"}</span>
        </div>
        {Object.entries(groupedVariables).map(([group, variables]) => (
          <section key={group}>
            <strong>{group}</strong>
            {variables.map((variable) => {
              const Icon = variableIcons[variable.type] || LayoutDashboard;
              return (
                <button
                  key={`${variable.type}-${variable.id}`}
                  type="button"
                  onClick={() => onAddGeneratedSource?.(variable.type, variable.id)}
                >
                  <Icon size={16} />
                  <span>
                    <strong>{variable.label}</strong>
                    <small>{variable.value}</small>
                  </span>
                </button>
              );
            })}
          </section>
        ))}
        {!reportVariables.length ? (
          <div className="daw-report-no-generated-blocks">
            <p>Save the dataframes in Prepare, then create charts or tables to place them here.</p>
          </div>
        ) : null}
      </div>
    </aside>
  );
}

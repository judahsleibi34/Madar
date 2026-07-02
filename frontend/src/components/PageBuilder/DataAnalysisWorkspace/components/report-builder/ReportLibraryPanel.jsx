import { useState } from "react";
import { Eye, ImagePlus } from "lucide-react";
import { REPORT_BLOCK_DRAG_TYPE, reportBlockTypes } from "./reportBuilderConfig";

export default function ReportLibraryPanel({
  logo,
  onLogoChange,
  onRemoveLogo,
  onAddBlock,
  availability = {},
  onGenerateMetrics,
  isGeneratingMetrics = false,
  isPreviewMode = false,
  onTogglePreview,
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
            <p>No saved numbers, charts, or tables yet.</p>
            <button
              type="button"
              className="daw-primary"
              onClick={onGenerateMetrics}
              disabled={isGeneratingMetrics}
            >
              {isGeneratingMetrics ? "Working..." : "Create metrics"}
            </button>
          </div>
        ) : null}
      </div>
    </aside>
  );
}

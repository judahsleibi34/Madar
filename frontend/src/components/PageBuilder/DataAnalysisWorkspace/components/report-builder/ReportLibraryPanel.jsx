import { ImagePlus } from "lucide-react";
import { REPORT_BLOCK_DRAG_TYPE, reportBlockTypes } from "./reportBuilderConfig";

export default function ReportLibraryPanel({
  logo,
  onLogoChange,
  onRemoveLogo,
  onAddBlock,
  availability = {},
  onGenerateMetrics,
  isGeneratingMetrics = false,
}) {
  return (
    <aside className="daw-report-panel daw-report-library">
      <div className="daw-report-panel-heading">
        <span>Report setup</span>
        <h3>Brand and content</h3>
        <p>Build the report from reusable blocks.</p>
      </div>

      <label className="daw-report-logo-control">
        <span><ImagePlus size={16} /> Report logo</span>
        <input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" onChange={onLogoChange} />
      </label>
      {logo ? (
        <button type="button" className="daw-report-remove-logo" onClick={onRemoveLogo}>Remove logo</button>
      ) : null}

      <div className="daw-report-block-library">
        <strong>Add a block</strong>
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
            <p>No generated metrics, plots, or tables are available yet.</p>
            <button
              type="button"
              className="daw-primary"
              onClick={onGenerateMetrics}
              disabled={isGeneratingMetrics}
            >
              {isGeneratingMetrics ? "Generating..." : "Generate metrics"}
            </button>
          </div>
        ) : null}
      </div>
    </aside>
  );
}

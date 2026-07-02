import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Check, ChevronDown, Search, Trash2 } from "lucide-react";

export default function ReportPropertiesPanel({
  report,
  selectedBlock,
  onUpdateReport,
  onUpdateBlock,
  onMoveBlock,
  onRemoveBlock,
  availableMetrics = [],
  availableTables = [],
  availablePlots = [],
  onSelectGeneratedSource,
}) {
  const [isSourcePickerOpen, setIsSourcePickerOpen] = useState(false);
  const [sourceSearch, setSourceSearch] = useState("");
  const selectedBlockType = selectedBlock?.type || "";
  const generatedSources = useMemo(() => {
    if (selectedBlockType === "metric") return availableMetrics;
    if (selectedBlockType === "table") return availableTables;
    if (selectedBlockType === "chart") return availablePlots;
    return [];
  }, [availableMetrics, availablePlots, availableTables, selectedBlockType]);
  const selectedSource = generatedSources.find(
    (source) => source.id === selectedBlock?.sourceId
  );
  const groupedSources = useMemo(() => {
    const query = sourceSearch.trim().toLocaleLowerCase();
    return generatedSources.reduce((groups, source) => {
      const label = String(source.displayLabel || source.label || source.title || "Result");
      const group = String(source.sourceGroup || "Other report results");
      if (query && !`${group} ${label}`.toLocaleLowerCase().includes(query)) return groups;
      if (!groups[group]) groups[group] = [];
      groups[group].push({ ...source, pickerLabel: label });
      return groups;
    }, {});
  }, [generatedSources, sourceSearch]);

  return (
    <aside className="daw-report-panel daw-report-properties">
      <div className="daw-report-panel-heading">
        <span>Details</span>
        <h3>{selectedBlock ? "Selected block" : "Report settings"}</h3>
      </div>

      {selectedBlock ? (
        <>
          {generatedSources.length ? (
            <div className="daw-report-source-field">
              <span>
                {selectedBlock.type === "metric"
                  ? "Choose a number"
                  : selectedBlock.type === "table"
                  ? "Choose table"
                  : "Choose chart"}
              </span>
              <button
                type="button"
                className="daw-report-source-trigger"
                aria-expanded={isSourcePickerOpen}
                onClick={() => setIsSourcePickerOpen((open) => !open)}
              >
                <span>{selectedSource?.displayLabel || selectedSource?.label || selectedSource?.title || "Choose a result"}</span>
                <ChevronDown size={16} />
              </button>
              {isSourcePickerOpen ? (
                <div className="daw-report-source-popover">
                  <label className="daw-report-source-search">
                    <Search size={15} />
                    <input
                      autoFocus
                      value={sourceSearch}
                      placeholder="Find a number or column..."
                      onChange={(event) => setSourceSearch(event.target.value)}
                    />
                  </label>
                  <div className="daw-report-source-list">
                    {Object.entries(groupedSources).map(([group, sources]) => (
                      <section key={group}>
                        <strong>{group}</strong>
                        {sources.map((source) => (
                          <button
                            key={source.id}
                            type="button"
                            className={source.id === selectedBlock.sourceId ? "active" : ""}
                            onClick={() => {
                              onSelectGeneratedSource?.(selectedBlock.type, source.id);
                              setIsSourcePickerOpen(false);
                              setSourceSearch("");
                            }}
                          >
                            <span>{source.pickerLabel}</span>
                            {source.id === selectedBlock.sourceId ? <Check size={14} /> : null}
                          </button>
                        ))}
                      </section>
                    ))}
                    {!Object.keys(groupedSources).length ? (
                      <p>No matching report results.</p>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
          {selectedBlock.type !== "spacer" && selectedBlock.type !== "text" ? (
            <label><span>Title</span><input value={selectedBlock.title} onChange={(event) => onUpdateBlock("title", event.target.value)} /></label>
          ) : null}
          {selectedBlock.type === "spacer" ? (
            <label>
              <span>Space height: {selectedBlock.spacerHeight || 40}px</span>
              <input
                type="range"
                min="12"
                max="240"
                value={selectedBlock.spacerHeight || 40}
                onChange={(event) => onUpdateBlock("spacerHeight", Number(event.target.value))}
              />
            </label>
          ) : selectedBlock.type !== "image" && selectedBlock.type !== "text" ? (
            <label className="daw-report-color-property">
              <span>Text color</span>
              <input
                type="color"
                value={selectedBlock.textColor || "var(--theme-text)"}
                onChange={(event) => onUpdateBlock("textColor", event.target.value)}
              />
            </label>
          ) : null}
          {selectedBlock.type === "image" ? (
            <>
              <label>
                <span>Image caption</span>
                <textarea
                  rows="3"
                  value={selectedBlock.body || ""}
                  placeholder="Write a caption below the image..."
                  onChange={(event) => onUpdateBlock("body", event.target.value)}
                />
              </label>
              <label>
                <span>Image width: {selectedBlock.imageWidthPercent || 76}%</span>
                <input
                  type="range"
                  min="20"
                  max="100"
                  value={selectedBlock.imageWidthPercent || 76}
                  onChange={(event) => onUpdateBlock("imageWidthPercent", Number(event.target.value))}
                />
              </label>
              <label>
                <span>Aspect ratio</span>
                <select value={selectedBlock.imageRatio || "original"} onChange={(event) => onUpdateBlock("imageRatio", event.target.value)}>
                  <option value="original">Original</option>
                  <option value="1 / 1">Square (1:1)</option>
                  <option value="4 / 3">Standard (4:3)</option>
                  <option value="16 / 9">Wide (16:9)</option>
                </select>
              </label>
            </>
          ) : null}
          <div className="daw-report-block-actions">
            <button type="button" onClick={() => onMoveBlock(-1)}><ArrowUp size={16} /> Move up</button>
            <button type="button" onClick={() => onMoveBlock(1)}><ArrowDown size={16} /> Move down</button>
            <button type="button" className="is-danger" onClick={onRemoveBlock}><Trash2 size={16} /> Delete</button>
          </div>
        </>
      ) : (
        <>
          <label><span>Report title</span><input value={report.title} onChange={(event) => onUpdateReport("title", event.target.value)} /></label>
        </>
      )}
    </aside>
  );
}

import { useState } from "react";
import { Eye, GripVertical, LayoutDashboard, Pencil } from "lucide-react";
import { REPORT_BLOCK_DRAG_TYPE, reportBlockTypes } from "./reportBuilderConfig";
import InlineEditable from "./InlineEditable";
import DocumentToolbar from "./DocumentToolbar";
import ResizableImage from "./ResizableImage";

export default function ReportPageCanvas({
  report,
  blocks,
  selectedBlockId,
  onSelectBlock,
  onUpdateReport,
  onUpdateBlock,
  onInsertImage,
  onInsertBlock,
  onInsertParagraph,
  onMoveBlockToIndex,
  isPreviewMode = false,
  onTogglePreview,
}) {
  const [isHeaderEditing, setIsHeaderEditing] = useState(false);
  const [activeDropIndex, setActiveDropIndex] = useState(null);

  const handleDrop = (event, index) => {
    event.preventDefault();
    const movingBlockId = event.dataTransfer.getData("application/x-madar-report-existing-block");
    if (movingBlockId) {
      onMoveBlockToIndex(movingBlockId, index);
      setActiveDropIndex(null);
      return;
    }
    const type = event.dataTransfer.getData(REPORT_BLOCK_DRAG_TYPE);
    if (reportBlockTypes.some((item) => item.type === type && type !== "image")) {
      onInsertBlock(type, index);
    }
    setActiveDropIndex(null);
  };

  const renderDropZone = (index) => isPreviewMode ? null : (
    <div
      className={`daw-report-drop-zone ${activeDropIndex === index ? "is-active" : ""}`}
      onDragEnter={(event) => {
        event.preventDefault();
        setActiveDropIndex(index);
      }}
      onDragOver={(event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
      }}
      onDrop={(event) => handleDrop(event, index)}
    >
      <button
        type="button"
        onClick={() => onInsertBlock("spacer", index)}
        title="Add blank space here"
      >
        + Add space
      </button>
    </div>
  );

  return (
    <div className={`daw-report-canvas-shell ${isPreviewMode ? "is-preview" : ""}`}>
      <div className="daw-report-preview-actions">
        <button type="button" className="daw-secondary" onClick={onTogglePreview}>
          {isPreviewMode ? <Pencil size={16} /> : <Eye size={16} />}
          {isPreviewMode ? "Back to editing" : "Preview report"}
        </button>
      </div>
      <div className="daw-report-page">
        <div className="daw-report-header-shell">
          {isHeaderEditing && !isPreviewMode ? (
            <DocumentToolbar
              onInsertImage={onInsertImage}
              blockColor={report.headerBackground}
              onBlockColor={(value) => onUpdateReport("headerBackground", value)}
              onContentFormatted={(editable) => {
                onUpdateReport("title", editable.innerHTML);
                onUpdateReport("titleDirection", editable.dir);
              }}
            />
          ) : null}
          <header
            className="daw-report-page-header"
            style={{
              "--daw-header-background": report.headerBackground || "transparent",
            }}
          >
            {report.logo ? <img src={report.logo} alt="Report logo" /> : null}
            <div>
            <InlineEditable
              className="daw-report-inline-title"
              value={report.title}
              direction={report.titleDirection}
              placeholder="Untitled report"
              editable={!isPreviewMode}
              onFocus={() => setIsHeaderEditing(true)}
              onChange={(value, direction) => {
                onUpdateReport("title", value);
                onUpdateReport("titleDirection", direction);
              }}
            />
            </div>
          </header>
        </div>

        <div className="daw-report-page-blocks">
          {blocks.length ? (
            <>
              {blocks.map((block, index) => {
            const blockType = reportBlockTypes.find((item) => item.type === block.type);
            return (
              <div className="daw-report-block-position" key={block.id}>
                {renderDropZone(index)}
                <div className="daw-report-block-shell">
                {selectedBlockId === block.id && !isHeaderEditing && !isPreviewMode ? (
                  <DocumentToolbar
                    onInsertImage={onInsertImage}
                    blockColor={block.backgroundColor}
                    onBlockColor={(value) => onUpdateBlock(block.id, "backgroundColor", value)}
                    textColor={block.textColor}
                    onTextColor={(value) => onUpdateBlock(block.id, "textColor", value)}
                    onContentFormatted={(editable) => {
                      const isTitle = editable.classList.contains("daw-report-block-title");
                      onUpdateBlock(block.id, isTitle ? "title" : "body", editable.innerHTML);
                      onUpdateBlock(
                        block.id,
                        isTitle ? "titleDirection" : "bodyDirection",
                        editable.dir
                      );
                    }}
                  />
                ) : null}
                <article
                  data-report-block-id={block.id}
                  tabIndex={isPreviewMode ? undefined : 0}
                  className={`daw-report-page-block is-${block.type} ${selectedBlockId === block.id ? "is-selected" : ""}`}
                  style={{
                    "--daw-block-background": block.backgroundColor || "transparent",
                    "--daw-block-text": block.textColor || "#1a2744",
                  }}
                  onClick={(event) => {
                    if (isPreviewMode) return;
                    setIsHeaderEditing(false);
                    onSelectBlock(block.id);
                    if (!event.target.closest(".daw-report-editable, button, input, select, textarea")) {
                      event.currentTarget.focus({ preventScroll: true });
                    }
                  }}
                  onKeyDown={(event) => {
                    if (isPreviewMode) return;
                    if (
                      event.key === "Enter" &&
                      !event.shiftKey &&
                      !event.target.closest(".daw-report-editable, button, input, select, textarea")
                    ) {
                      event.preventDefault();
                      onInsertParagraph(index + 1);
                    }
                  }}
                >
                  {!isPreviewMode ? <button
                    type="button"
                    className="daw-report-drag-handle"
                    draggable
                    title="Drag to move this block"
                    aria-label="Drag to move this block"
                    onDragStart={(event) => {
                      event.dataTransfer.effectAllowed = "move";
                      event.dataTransfer.setData("application/x-madar-report-existing-block", block.id);
                    }}
                  >
                    <GripVertical size={16} />
                  </button> : null}
                  <div>
                  {block.type === "spacer" ? (
                    <div
                      className="daw-report-spacer-block"
                      style={{ height: `${block.spacerHeight || 40}px` }}
                    >
                      {!isPreviewMode ? <span>Blank space · {block.spacerHeight || 40}px</span> : null}
                    </div>
                  ) : block.type === "chart" && block.src ? (
                    <>
                      <InlineEditable
                        className="daw-report-block-title"
                        editable={!isPreviewMode}
                        value={block.title}
                        direction={block.titleDirection}
                        placeholder="Chart title"
                        onChange={(value, direction) => {
                          onUpdateBlock(block.id, "title", value);
                          onUpdateBlock(block.id, "titleDirection", direction);
                        }}
                      />
                      <img className="daw-report-generated-chart" src={block.src} alt={block.title || "Generated chart"} />
                    </>
                  ) : block.type === "table" && block.rows?.length ? (
                    <>
                      <InlineEditable
                        className="daw-report-block-title"
                        editable={!isPreviewMode}
                        value={block.title}
                        direction={block.titleDirection}
                        placeholder="Table title"
                        onChange={(value, direction) => {
                          onUpdateBlock(block.id, "title", value);
                          onUpdateBlock(block.id, "titleDirection", direction);
                        }}
                      />
                      <div className="daw-report-generated-table-wrap">
                        <table className="daw-report-generated-table">
                          <thead>
                            <tr>{Object.keys(block.rows[0]).map((column) => <th key={column}>{column}</th>)}</tr>
                          </thead>
                          <tbody>
                            {block.rows.map((row, rowIndex) => (
                              <tr key={rowIndex}>{Object.keys(block.rows[0]).map((column) => <td key={column}>{String(row[column] ?? "")}</td>)}</tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  ) : block.type === "image" ? (
                    <ResizableImage
                      src={block.src}
                      alt={block.title || "Report content"}
                      widthPercent={block.imageWidthPercent}
                      ratio={block.imageRatio}
                      offsetX={block.imageOffsetX}
                      offsetY={block.imageOffsetY}
                      onUpdate={(changes) => {
                        Object.entries(changes).forEach(([key, value]) => onUpdateBlock(block.id, key, value));
                      }}
                    >
                      <InlineEditable
                        className="daw-report-image-caption"
                        editable={!isPreviewMode}
                        value={block.body}
                        direction={block.bodyDirection}
                        placeholder="Add an image caption..."
                        multiline
                        onChange={(value, direction) => {
                          onUpdateBlock(block.id, "body", value);
                          onUpdateBlock(block.id, "bodyDirection", direction);
                        }}
                      />
                    </ResizableImage>
                  ) : (
                    <>
                      {!block.hideTitle ? (
                        <InlineEditable
                          className="daw-report-block-title"
                          editable={!isPreviewMode}
                          value={block.title}
                          direction={block.titleDirection}
                          placeholder={`${blockType?.label || "Block"} title`}
                          onEnter={() => onInsertParagraph(index + 1)}
                          onChange={(value, direction) => {
                            onUpdateBlock(block.id, "title", value);
                            onUpdateBlock(block.id, "titleDirection", direction);
                          }}
                        />
                      ) : null}
                      <InlineEditable
                        className="daw-report-block-body"
                        editable={!isPreviewMode}
                        value={block.body}
                        direction={block.bodyDirection}
                        placeholder="Write here..."
                        multiline
                        onChange={(value, direction) => {
                          onUpdateBlock(block.id, "body", value);
                          onUpdateBlock(block.id, "bodyDirection", direction);
                        }}
                      />
                    </>
                  )}
                  </div>
                </article>
                </div>
              </div>
            );
              })}
              {renderDropZone(blocks.length)}
            </>
          ) : (
            <div
              className={`daw-report-empty-canvas ${activeDropIndex === 0 ? "is-drop-active" : ""}`}
              onDragEnter={(event) => { event.preventDefault(); setActiveDropIndex(0); }}
              onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; }}
              onDrop={(event) => handleDrop(event, 0)}
            >
              <LayoutDashboard size={28} />
              <strong>Your report is empty</strong>
              <span>Click a library item or drag it here to begin.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

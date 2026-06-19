import { useRef, useState } from "react";
import ReportLibraryPanel from "./report-builder/ReportLibraryPanel";
import ReportPageCanvas from "./report-builder/ReportPageCanvas";
import ReportPropertiesPanel from "./report-builder/ReportPropertiesPanel";
import { reportBlockDefaults } from "./report-builder/reportBuilderConfig";
import "../../../../styles/admin/PageBuilder/data-analysis/24-report-builder.css";

export default function ReportBuilderStep({
  availablePlots = [],
  availableMetrics = [],
  availableTables = [],
  onGenerateMetrics,
  isGeneratingMetrics = false,
}) {
  const nextBlockId = useRef(1);
  const [report, setReport] = useState({
    title: "Untitled report",
    titleDirection: "auto",
    headerBackground: "",
    logo: "",
  });
  const [blocks, setBlocks] = useState([]);
  const [selectedBlockId, setSelectedBlockId] = useState("");
  const [isPreviewMode, setIsPreviewMode] = useState(false);
  const selectedBlock = blocks.find((block) => block.id === selectedBlockId) || null;

  const updateReport = (key, value) => setReport((current) => ({ ...current, [key]: value }));

  const insertBlock = (type, index = blocks.length) => {
    if (type === "chart" && !availablePlots.length) return;
    if (type === "metric" && !availableMetrics.length) return;
    if (type === "table" && !availableTables.length) return;

    const id = `report-block-${nextBlockId.current++}`;
    const generatedContent =
      type === "chart"
        ? { title: availablePlots[0].title, body: "", src: availablePlots[0].src, sourceId: availablePlots[0].id }
        : type === "metric"
        ? { title: availableMetrics[0].label, body: availableMetrics[0].display_value || String(availableMetrics[0].value ?? ""), sourceId: availableMetrics[0].id }
        : type === "table"
        ? { title: availableTables[0].title, body: "", rows: availableTables[0].rows || [], sourceId: availableTables[0].id }
        : {};
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

  return (
    <section className={`daw-report-builder ${isPreviewMode ? "is-preview" : ""}`} aria-label="Report builder">
      <ReportLibraryPanel
        logo={report.logo}
        onLogoChange={handleLogoChange}
        onRemoveLogo={() => updateReport("logo", "")}
        onAddBlock={addBlock}
        availability={{
          chart: availablePlots.length > 0,
          metric: availableMetrics.length > 0,
          table: availableTables.length > 0,
        }}
        onGenerateMetrics={onGenerateMetrics}
        isGeneratingMetrics={isGeneratingMetrics}
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

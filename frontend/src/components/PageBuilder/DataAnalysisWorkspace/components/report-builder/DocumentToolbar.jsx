import { useEffect, useRef } from "react";
import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  Baseline,
  Bold,
  Eraser,
  Highlighter,
  ImagePlus,
  Italic,
  List,
  ListOrdered,
  PaintBucket,
  Redo2,
  Underline,
  Undo2,
} from "lucide-react";

const commandButtons = [
  { command: "undo", label: "Undo", icon: Undo2 },
  { command: "redo", label: "Redo", icon: Redo2 },
  { command: "bold", label: "Bold", icon: Bold },
  { command: "italic", label: "Italic", icon: Italic },
  { command: "underline", label: "Underline", icon: Underline },
  { command: "insertUnorderedList", label: "Bulleted list", icon: List },
  { command: "insertOrderedList", label: "Numbered list", icon: ListOrdered },
  { command: "justifyLeft", label: "Align left", icon: AlignLeft },
  { command: "justifyCenter", label: "Align center", icon: AlignCenter },
  { command: "justifyRight", label: "Align right", icon: AlignRight },
  { command: "justifyFull", label: "Justify", icon: AlignJustify },
];

export default function DocumentToolbar({
  onInsertImage,
  blockColor = "#ffffff",
  onBlockColor,
  textColor = "#1a2744",
  onTextColor,
  onContentFormatted,
}) {
  const imageInputRef = useRef(null);
  const selectionRangeRef = useRef(null);

  useEffect(() => {
    const rememberSelection = () => {
      const selection = window.getSelection();
      if (!selection?.rangeCount) return;
      const range = selection.getRangeAt(0);
      const node = range.commonAncestorContainer;
      const element = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      if (element?.closest?.(".daw-report-editable")) {
        selectionRangeRef.current = range.cloneRange();
      }
    };

    document.addEventListener("selectionchange", rememberSelection);
    return () => document.removeEventListener("selectionchange", rememberSelection);
  }, []);

  const restoreSelection = () => {
    const range = selectionRangeRef.current;
    if (!range || !range.commonAncestorContainer?.isConnected) return null;
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    const node = range.commonAncestorContainer;
    const element = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
    return element?.closest?.(".daw-report-editable") || null;
  };

  const getSelectionOffsets = (editable, range) => {
    if (!editable || !range) return null;
    const before = document.createRange();
    before.selectNodeContents(editable);
    before.setEnd(range.startContainer, range.startOffset);
    return {
      start: before.toString().length,
      end: before.toString().length + range.toString().length,
    };
  };

  const restoreSelectionOffsets = (editable, offsets) => {
    if (!editable?.isConnected || !offsets) return;
    const walker = document.createTreeWalker(editable, NodeFilter.SHOW_TEXT);
    const range = document.createRange();
    let node = walker.nextNode();
    let position = 0;
    let startSet = false;

    while (node) {
      const nextPosition = position + node.textContent.length;
      if (!startSet && offsets.start <= nextPosition) {
        range.setStart(node, Math.max(0, offsets.start - position));
        startSet = true;
      }
      if (startSet && offsets.end <= nextPosition) {
        range.setEnd(node, Math.max(0, offsets.end - position));
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        selectionRangeRef.current = range.cloneRange();
        return;
      }
      position = nextPosition;
      node = walker.nextNode();
    }
  };

  const runCommand = (command, value = null) => {
    const editable = restoreSelection();
    const activeRange = window.getSelection()?.rangeCount
      ? window.getSelection().getRangeAt(0).cloneRange()
      : null;
    const offsets = getSelectionOffsets(editable, activeRange);
    document.execCommand("styleWithCSS", false, true);
    document.execCommand(command, false, value);
    if (editable) {
      onContentFormatted?.(editable);
      window.requestAnimationFrame(() => restoreSelectionOffsets(editable, offsets));
    }
    return { editable, hasSelection: Boolean(activeRange && !activeRange.collapsed) };
  };

  const setDirection = (direction) => {
    const editable = restoreSelection() || document.activeElement?.closest?.(".daw-report-editable");
    if (!editable) return;
    editable.dir = direction;
    editable.style.textAlign = direction === "rtl" ? "right" : "left";
    onContentFormatted?.(editable);
  };

  const handleImage = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => onInsertImage(String(reader.result || ""), file.name);
    reader.readAsDataURL(file);
    event.target.value = "";
  };

  const applyTextColor = (color) => {
    const result = runCommand("foreColor", color);
    if (!result.editable || !result.hasSelection) {
      onTextColor?.(color);
    }
  };

  const applyHighlightColor = (color) => {
    runCommand("backColor", color);
  };

  return (
    <div className="daw-document-toolbar" role="toolbar" aria-label="Document formatting">
      <div className="daw-document-toolbar-row">
        <select
          aria-label="Text style"
          defaultValue="p"
          onChange={(event) => runCommand("formatBlock", event.target.value)}
        >
          <option value="p">Paragraph</option>
          <option value="h1">Heading 1</option>
          <option value="h2">Heading 2</option>
          <option value="h3">Heading 3</option>
        </select>

        {commandButtons.slice(0, 5).map(({ command, label, icon: Icon }) => (
          <button
            key={command}
            type="button"
            title={label}
            aria-label={label}
            onMouseDown={(event) => {
              event.preventDefault();
              runCommand(command);
            }}
          >
            <Icon size={16} />
          </button>
        ))}
      </div>

      <div className="daw-document-toolbar-row">
        {commandButtons.slice(5).map(({ command, label, icon: Icon }) => (
          <button
            key={command}
            type="button"
            title={label}
            aria-label={label}
            onMouseDown={(event) => {
              event.preventDefault();
              runCommand(command);
            }}
          >
            <Icon size={16} />
          </button>
        ))}

        <button type="button" title="Left-to-right" onMouseDown={(event) => { event.preventDefault(); setDirection("ltr"); }}>LTR</button>
        <button type="button" title="Right-to-left" onMouseDown={(event) => { event.preventDefault(); setDirection("rtl"); }}>RTL</button>
        <button type="button" title="Insert image" aria-label="Insert image" onClick={() => imageInputRef.current?.click()}><ImagePlus size={16} /></button>
        <label className="daw-toolbar-color" title="Text color">
          <Baseline size={16} />
          <input
            type="color"
            value={textColor || "#1a2744"}
            onInput={(event) => applyTextColor(event.currentTarget.value)}
            onChange={(event) => applyTextColor(event.currentTarget.value)}
          />
        </label>
        <label className="daw-toolbar-color" title="Highlight color">
          <Highlighter size={16} />
          <input
            type="color"
            defaultValue="#fef08a"
            onInput={(event) => applyHighlightColor(event.currentTarget.value)}
            onChange={(event) => applyHighlightColor(event.currentTarget.value)}
          />
        </label>
        {onBlockColor ? (
          <>
            <label className="daw-toolbar-color" title="Block background color">
              <PaintBucket size={16} />
              <input
                type="color"
                value={blockColor || "#ffffff"}
                onInput={(event) => onBlockColor(event.currentTarget.value)}
                onChange={(event) => onBlockColor(event.currentTarget.value)}
              />
            </label>
            <button type="button" title="Clear block background" aria-label="Clear block background" onClick={() => onBlockColor("")}><Eraser size={16} /></button>
          </>
        ) : null}
      </div>
      <input ref={imageInputRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml" onChange={handleImage} hidden />
    </div>
  );
}

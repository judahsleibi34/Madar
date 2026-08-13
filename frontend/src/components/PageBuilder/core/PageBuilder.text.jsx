export const splitLines = (value) =>
  String(value || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

export const splitEditableLines = (value) => {
  const text = String(value ?? "");
  return text === "" ? [""] : text.split("\n");
};

export const getListItems = (element) =>
  Array.isArray(element?.listItems) && element.listItems.length
    ? element.listItems
    : splitLines(element?.content);

export const getRichTextRanges = (element, field, itemIndex = null) =>
  [
    ...(element?.richTextColors || []),
    ...(element?.richTextSizes || []),
    ...(element?.richTextStyles || []),
  ].filter((range) => range.field === field && (range.itemIndex ?? null) === itemIndex);

const richTextPresentationProperties = new Set([
  "color",
  "backgroundColor",
  "fontSize",
  "fontFamily",
  "fontWeight",
  "fontStyle",
  "textDecoration",
  "opacity",
  "highlight",
]);

export const replaceRichTextRangeStyle = (
  ranges = [],
  targetRange,
  property,
  value
) => {
  if (!targetRange || !richTextPresentationProperties.has(property)) return ranges;

  const targetStart = Number(targetRange.start) || 0;
  const targetEnd = Number(targetRange.end) || 0;
  if (targetEnd <= targetStart) return ranges;

  const sameTarget = (range) =>
    range.field === targetRange.field &&
    (range.itemIndex ?? null) === (targetRange.itemIndex ?? null);
  const hasPresentation = (range) =>
    [...richTextPresentationProperties].some((key) => range[key] !== undefined);

  const nextRanges = (ranges || []).flatMap((range) => {
    const rangeStart = Number(range.start) || 0;
    const rangeEnd = Number(range.end) || 0;
    if (!sameTarget(range) || rangeEnd <= targetStart || rangeStart >= targetEnd) {
      return [range];
    }

    const fragments = [];
    if (rangeStart < targetStart) {
      fragments.push({ ...range, end: targetStart });
    }

    const overlap = {
      ...range,
      start: Math.max(rangeStart, targetStart),
      end: Math.min(rangeEnd, targetEnd),
    };
    delete overlap[property];
    if (hasPresentation(overlap)) fragments.push(overlap);

    if (rangeEnd > targetEnd) {
      fragments.push({ ...range, start: targetEnd });
    }
    return fragments;
  });

  return [...nextRanges, { ...targetRange, [property]: value }];
};

export const collapseAccidentalTextDuplication = (value) => {
  const text = String(value ?? "");
  if (text.length < 48) return text;

  for (let unitLength = 24; unitLength <= text.length / 2; unitLength += 1) {
    if (text.length % unitLength !== 0) continue;

    const unit = text.slice(0, unitLength);
    const copies = text.length / unitLength;
    if (copies >= 2 && unit.repeat(copies) === text) return unit;
  }

  return text;
};

export const getEditableTextWithLineBreaks = (root) => {
  if (!root) return "";

  const blockNames = new Set([
    "ADDRESS", "ARTICLE", "ASIDE", "BLOCKQUOTE", "DIV", "FIGCAPTION", "FIGURE",
    "FOOTER", "H1", "H2", "H3", "H4", "H5", "H6", "HEADER", "LI", "MAIN",
    "NAV", "P", "SECTION",
  ]);

  const readChildren = (nodes) => {
    const children = [...(nodes || [])];
    let output = "";

    children.forEach((child, index) => {
      const isBlock = child.nodeType === 1 && blockNames.has(child.nodeName);
      if (isBlock && output && !output.endsWith("\n")) output += "\n";
      output += readNode(child);
      if (isBlock && index < children.length - 1 && !output.endsWith("\n")) output += "\n";
    });

    return output;
  };

  const readNode = (node) => {
    if (node.nodeType === 3) return node.data || "";
    if (node.nodeName === "BR") return "\n";
    return readChildren(node.childNodes);
  };

  const blocks = [...root.children].filter((node) => node.hasAttribute("data-builder-text-block"));
  if (blocks.length) {
    return blocks.map((block) => {
      const isEmptyPlaceholder =
        block.childNodes.length === 1 && block.firstChild?.nodeName === "BR";
      return isEmptyPlaceholder ? "" : readNode(block);
    }).join("\n");
  }

  return readChildren(root.childNodes);
};

export const getTextBlockFormats = (element) => {
  const lineCount = String(element?.content ?? "").split("\n").length;
  const fallback = element?.type === "heading"
    ? `h${Math.max(1, Math.min(3, Number(element?.headingLevel) || 1))}`
    : "text";
  const saved = Array.isArray(element?.textBlockFormats) ? element.textBlockFormats : [];

  return Array.from({ length: lineCount }, (_, index) => {
    const format = String(saved[index] || fallback).toLowerCase();
    return ["h1", "h2", "h3", "text", "bullets", "numbers"].includes(format) ? format : fallback;
  });
};

export const getEditableTextBlockFormats = (root, fallback = "text") => {
  if (!root) return [];
  const blocks = [...root.children].filter((node) => node.hasAttribute("data-builder-text-block"));
  if (!blocks.length) return [fallback];
  return blocks.map((node) => {
    const format = String(node.dataset.builderTextBlock || node.tagName || fallback).toLowerCase();
    return ["h1", "h2", "h3", "bullets", "numbers"].includes(format) ? format : "text";
  });
};

export const getTextBlockIndexesForRange = (value, startOffset = 0, endOffset = startOffset) => {
  const text = String(value ?? "");
  const start = Math.max(0, Math.min(Number(startOffset) || 0, text.length));
  const end = Math.max(start, Math.min(Number(endOffset) || 0, text.length));
  const lineAt = (offset) => text.slice(0, offset).split("\n").length - 1;
  const first = lineAt(start);
  const last = lineAt(end > start && text[end - 1] === "\n" ? end - 1 : end);
  return Array.from({ length: last - first + 1 }, (_, index) => first + index);
};

export const renderRichTextBlocks = (element, ranges = []) => {
  const lines = String(element?.content ?? "").split("\n");
  const formats = getTextBlockFormats(element);
  const hasMixedBlockFormats = new Set(formats).size > 1;
  let lineStart = 0;

  return lines.map((line, index) => {
    const format = formats[index];
    const Tag = ["h1", "h2", "h3"].includes(format) ? format : "p";
    const lineEnd = lineStart + line.length;
    const lineRanges = ranges
      .filter((range) =>
        range.end > lineStart &&
        range.start < lineEnd &&
        !(hasMixedBlockFormats && range.fontSize && (range.start < lineStart || range.end > lineEnd))
      )
      .map((range) => ({
        ...range,
        start: Math.max(0, range.start - lineStart),
        end: Math.min(line.length, range.end - lineStart),
      }));
    const rendered = line ? renderRichText(line, lineRanges) : <br />;
    lineStart = lineEnd + 1;
    return <Tag data-builder-text-block={format} key={`${index}_${format}`}>{rendered}</Tag>;
  });
};
export const renderRichText = (value, ranges = []) => {
  const text = String(value ?? "");
  const parts = [];
  let runStart = 0;
  let runColor = null;
  let runBackgroundColor = null;
  let runFontSize = null;
  let runFontFamily = null;
  let runFontWeight = null;
  let runFontStyle = null;
  let runTextDecoration = null;
  let runOpacity = null;
  let runHighlight = false;

  for (let index = 0; index <= text.length; index += 1) {
    const activeRanges =
      index < text.length
        ? [...ranges].reverse().filter((range) => index >= range.start && index < range.end)
        : [];
    const color = activeRanges.find((range) => range.color)?.color || null;
    const backgroundColor = activeRanges.find((range) => range.backgroundColor)?.backgroundColor || null;
    const fontSize = activeRanges.find((range) => range.fontSize)?.fontSize || null;
    const fontFamily = activeRanges.find((range) => range.fontFamily)?.fontFamily || null;
    const fontWeight = activeRanges.find((range) => range.fontWeight)?.fontWeight || null;
    const fontStyle = activeRanges.find((range) => range.fontStyle)?.fontStyle || null;
    const textDecoration = activeRanges.find((range) => range.textDecoration)?.textDecoration || null;
    const opacity = activeRanges.find((range) => range.opacity !== undefined)?.opacity ?? null;
    const highlight = activeRanges.some((range) => range.highlight);

    if (index === 0) {
      runColor = color;
      runBackgroundColor = backgroundColor;
      runFontSize = fontSize;
      runFontFamily = fontFamily;
      runFontWeight = fontWeight;
      runFontStyle = fontStyle;
      runTextDecoration = textDecoration;
      runOpacity = opacity;
      runHighlight = highlight;
    }
    if (
      color === runColor &&
      backgroundColor === runBackgroundColor &&
      fontSize === runFontSize &&
      fontFamily === runFontFamily &&
      fontWeight === runFontWeight &&
      fontStyle === runFontStyle &&
      textDecoration === runTextDecoration &&
      opacity === runOpacity &&
      highlight === runHighlight &&
      index < text.length
    ) continue;

    const content = text.slice(runStart, index);

    if (content) {
      const style = {
        ...(runColor ? { color: runColor } : {}),
        ...(runBackgroundColor ? { backgroundColor: runBackgroundColor } : {}),
        ...(runFontSize
          ? { fontSize: `calc(${runFontSize} * var(--builder-text-fit-scale, 1))` }
          : {}),
        ...(runFontFamily ? { fontFamily: runFontFamily } : {}),
        ...(runFontWeight ? { fontWeight: runFontWeight } : {}),
        ...(runFontStyle ? { fontStyle: runFontStyle } : {}),
        ...(runTextDecoration ? { textDecoration: runTextDecoration } : {}),
        ...(runOpacity !== null ? { opacity: runOpacity } : {}),
        ...(runHighlight
          ? {
              backgroundColor: "rgba(133, 44, 33, 0.22)",
              boxShadow: "0 0 0 2px rgba(133, 44, 33, 0.08)",
            }
          : {}),
      };

      parts.push(
        Object.keys(style).length > 0 ? (
          <span style={style} key={`${runStart}_${runColor || ""}_${runBackgroundColor || ""}_${runFontSize || ""}_${runFontFamily || ""}_${runFontWeight || ""}_${runFontStyle || ""}_${runTextDecoration || ""}_${runOpacity ?? ""}_${runHighlight ? "editing" : ""}`}>
            {content}
          </span>
        ) : (
          content
        )
      );
    }

    runStart = index;
    runColor = color;
    runBackgroundColor = backgroundColor;
    runFontSize = fontSize;
    runFontFamily = fontFamily;
    runFontWeight = fontWeight;
    runFontStyle = fontStyle;
    runTextDecoration = textDecoration;
    runOpacity = opacity;
    runHighlight = highlight;
  }

  return parts.length ? parts : text;
};



export const getFloatingToolbarPlacement = ({
  anchorRect,
  toolbarRect,
  horizontalBounds,
  viewportHeight,
  gap = 10,
  aboveGap = 28,
  margin = 12,
}) => {
  const toolbarWidth = Math.max(0, Number(toolbarRect?.width) || 0);
  const toolbarHeight = Math.max(0, Number(toolbarRect?.height) || 0);
  const minLeft = Math.max(margin, Number(horizontalBounds?.left) || margin);
  const maxRight = Math.max(
    minLeft,
    Number(horizontalBounds?.right) || minLeft + toolbarWidth
  );
  const maxLeft = Math.max(minLeft, maxRight - toolbarWidth);
  const centeredLeft = (Number(anchorRect?.left) || 0)
    + (Number(anchorRect?.width) || 0) / 2
    - toolbarWidth / 2;
  const left = Math.min(Math.max(centeredLeft, minLeft), maxLeft);
  const minTop = margin;
  const maxBottom = Math.max(minTop, (Number(viewportHeight) || 0) - margin);
  const anchorTop = Number(anchorRect?.top) || minTop;
  const anchorBottom = Number(anchorRect?.bottom) || anchorTop;
  const spaceAbove = anchorTop - minTop;
  const spaceBelow = maxBottom - anchorBottom;
  const placement = spaceAbove >= toolbarHeight + aboveGap || spaceAbove >= spaceBelow
    ? "above"
    : "below";
  const desiredTop = placement === "above"
    ? anchorTop - aboveGap - toolbarHeight
    : anchorBottom + gap;
  const top = Math.min(
    Math.max(desiredTop, minTop),
    Math.max(minTop, maxBottom - toolbarHeight)
  );

  return { left, top, placement };
};
export const getCanvasTextSelectionRange = (event) => {
  const selection = window.getSelection();

  if (!selection || selection.rangeCount === 0) return null;

  const range = selection.getRangeAt(0);
  if (!event.currentTarget.contains(range.commonAncestorContainer)) return null;

  const startRange = range.cloneRange();
  startRange.selectNodeContents(event.currentTarget);
  startRange.setEnd(range.startContainer, range.startOffset);

  const endRange = range.cloneRange();
  endRange.selectNodeContents(event.currentTarget);
  endRange.setEnd(range.endContainer, range.endOffset);

  return {
    collapsed: selection.isCollapsed,
    start: getEditableTextWithLineBreaks(startRange.cloneContents()).length,
    end: getEditableTextWithLineBreaks(endRange.cloneContents()).length,
  };
};

export const createInputTextSelection = ({
  elementId,
  field,
  itemIndex = null,
  selectionStart,
  selectionEnd,
}) => ({
  elementId,
  field,
  itemIndex,
  start: selectionStart,
  end: selectionEnd,
});
export const createDomTextRange = (root, startOffset, endOffset) => {
  if (!root?.ownerDocument) return null;

  const documentRef = root.ownerDocument;
  const walker = documentRef.createTreeWalker(root, 4);
  const range = documentRef.createRange();
  const start = Math.max(0, Number(startOffset) || 0);
  const end = Math.max(start, Number(endOffset) || 0);
  let consumed = 0;
  let startPoint = null;
  let endPoint = null;
  let node = walker.nextNode();

  while (node) {
    const nextConsumed = consumed + node.data.length;
    if (!startPoint && start <= nextConsumed) {
      startPoint = { node, offset: Math.min(node.data.length, start - consumed) };
    }
    if (!endPoint && end <= nextConsumed) {
      endPoint = { node, offset: Math.min(node.data.length, end - consumed) };
      break;
    }
    consumed = nextConsumed;
    node = walker.nextNode();
  }

  if (!startPoint || !endPoint) return null;
  range.setStart(startPoint.node, startPoint.offset);
  range.setEnd(endPoint.node, endPoint.offset);
  return range;
};

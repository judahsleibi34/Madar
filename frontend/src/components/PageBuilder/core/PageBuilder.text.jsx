export const splitLines = (value) =>
  String(value || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

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
export const renderRichText = (value, ranges = []) => {
  const text = String(value ?? "");
  const parts = [];
  let runStart = 0;
  let runColor = null;
  let runBackgroundColor = null;
  let runFontSize = null;
  let runFontWeight = null;
  let runFontStyle = null;
  let runTextDecoration = null;
  let runHighlight = false;

  for (let index = 0; index <= text.length; index += 1) {
    const activeRanges =
      index < text.length
        ? [...ranges].reverse().filter((range) => index >= range.start && index < range.end)
        : [];
    const color = activeRanges.find((range) => range.color)?.color || null;
    const backgroundColor = activeRanges.find((range) => range.backgroundColor)?.backgroundColor || null;
    const fontSize = activeRanges.find((range) => range.fontSize)?.fontSize || null;
    const fontWeight = activeRanges.find((range) => range.fontWeight)?.fontWeight || null;
    const fontStyle = activeRanges.find((range) => range.fontStyle)?.fontStyle || null;
    const textDecoration = activeRanges.find((range) => range.textDecoration)?.textDecoration || null;
    const highlight = activeRanges.some((range) => range.highlight);

    if (index === 0) {
      runColor = color;
      runBackgroundColor = backgroundColor;
      runFontSize = fontSize;
      runFontWeight = fontWeight;
      runFontStyle = fontStyle;
      runTextDecoration = textDecoration;
      runHighlight = highlight;
    }
    if (
      color === runColor &&
      backgroundColor === runBackgroundColor &&
      fontSize === runFontSize &&
      fontWeight === runFontWeight &&
      fontStyle === runFontStyle &&
      textDecoration === runTextDecoration &&
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
        ...(runFontWeight ? { fontWeight: runFontWeight } : {}),
        ...(runFontStyle ? { fontStyle: runFontStyle } : {}),
        ...(runTextDecoration ? { textDecoration: runTextDecoration } : {}),
        ...(runHighlight
          ? {
              backgroundColor: "rgba(133, 44, 33, 0.22)",
              boxShadow: "0 0 0 2px rgba(133, 44, 33, 0.08)",
            }
          : {}),
      };

      parts.push(
        Object.keys(style).length > 0 ? (
          <span style={style} key={`${runStart}_${runColor || ""}_${runBackgroundColor || ""}_${runFontSize || ""}_${runFontWeight || ""}_${runFontStyle || ""}_${runTextDecoration || ""}_${runHighlight ? "editing" : ""}`}>
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
    runFontWeight = fontWeight;
    runFontStyle = fontStyle;
    runTextDecoration = textDecoration;
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
  const placement = spaceAbove >= toolbarHeight + gap || spaceAbove >= spaceBelow
    ? "above"
    : "below";
  const desiredTop = placement === "above"
    ? anchorTop - gap - toolbarHeight
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
  if (selection.isCollapsed) return { collapsed: true };

  const range = selection.getRangeAt(0);
  if (!event.currentTarget.contains(range.commonAncestorContainer)) return null;

  const startRange = range.cloneRange();
  startRange.selectNodeContents(event.currentTarget);
  startRange.setEnd(range.startContainer, range.startOffset);

  const endRange = range.cloneRange();
  endRange.selectNodeContents(event.currentTarget);
  endRange.setEnd(range.endContainer, range.endOffset);

  return {
    collapsed: false,
    start: startRange.toString().length,
    end: endRange.toString().length,
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

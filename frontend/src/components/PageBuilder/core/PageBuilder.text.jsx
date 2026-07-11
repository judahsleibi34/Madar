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

export const renderRichText = (value, ranges = []) => {
  const text = String(value ?? "");
  const parts = [];
  let runStart = 0;
  let runColor = null;
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
    const fontSize = activeRanges.find((range) => range.fontSize)?.fontSize || null;
    const fontWeight = activeRanges.find((range) => range.fontWeight)?.fontWeight || null;
    const fontStyle = activeRanges.find((range) => range.fontStyle)?.fontStyle || null;
    const textDecoration = activeRanges.find((range) => range.textDecoration)?.textDecoration || null;
    const highlight = activeRanges.some((range) => range.highlight);

    if (index === 0) {
      runColor = color;
      runFontSize = fontSize;
      runFontWeight = fontWeight;
      runFontStyle = fontStyle;
      runTextDecoration = textDecoration;
      runHighlight = highlight;
    }
    if (
      color === runColor &&
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
        ...(runFontSize ? { fontSize: runFontSize } : {}),
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
          <span style={style} key={`${runStart}_${runColor || ""}_${runFontSize || ""}_${runFontWeight || ""}_${runFontStyle || ""}_${runTextDecoration || ""}_${runHighlight ? "editing" : ""}`}>
            {content}
          </span>
        ) : (
          content
        )
      );
    }

    runStart = index;
    runColor = color;
    runFontSize = fontSize;
    runFontWeight = fontWeight;
    runFontStyle = fontStyle;
    runTextDecoration = textDecoration;
    runHighlight = highlight;
  }

  return parts.length ? parts : text;
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

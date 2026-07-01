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
  (element?.richTextColors || []).filter(
    (range) => range.field === field && (range.itemIndex ?? null) === itemIndex
  );

export const renderRichText = (value, ranges = []) => {
  const text = String(value ?? "");
  const parts = [];
  let runStart = 0;
  let runColor = null;

  for (let index = 0; index <= text.length; index += 1) {
    const color =
      index < text.length
        ? [...ranges]
            .reverse()
            .find((range) => index >= range.start && index < range.end)?.color || null
        : null;

    if (index === 0) runColor = color;
    if (color === runColor && index < text.length) continue;

    const content = text.slice(runStart, index);

    if (content) {
      parts.push(
        runColor ? (
          <span style={{ color: runColor }} key={`${runStart}_${runColor}`}>
            {content}
          </span>
        ) : (
          content
        )
      );
    }

    runStart = index;
    runColor = color;
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

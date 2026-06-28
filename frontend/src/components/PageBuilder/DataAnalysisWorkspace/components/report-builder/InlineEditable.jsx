export default function InlineEditable({
  value,
  placeholder,
  ariaLabel,
  className = "",
  multiline = false,
  direction = "auto",
  onFocus,
  onChange,
  onEnter,
  editable = true,
}) {
  const handleKeyDown = (event) => {
    if (!multiline && event.key === "Enter") {
      event.preventDefault();
      if (onEnter) {
        onEnter();
      } else {
        event.currentTarget.blur();
      }
    }
  };

  const getPlainEditableText = (element) => {
    const text = element.textContent || "";
    return multiline ? text.replace(/\r\n/g, "\n") : text.replace(/\s*\n\s*/g, " ");
  };

  const commonProps = {
    className: `daw-report-editable ${className}`,
    contentEditable: editable,
    suppressContentEditableWarning: true,
    role: "textbox",
    "aria-multiline": multiline,
    "aria-label": ariaLabel || placeholder || "Editable report text",
    dir: direction,
    "data-placeholder": placeholder,
    onKeyDown: handleKeyDown,
    onFocus,
    onBlur: (event) => {
      onChange(getPlainEditableText(event.currentTarget), event.currentTarget.dir);
    },
    onPaste: (event) => {
      event.preventDefault();
      const text = event.clipboardData.getData("text/plain");
      document.execCommand("insertText", false, text);
    },
  };

  return (
    <div {...commonProps}>
      {String(value || "")}
    </div>
  );
}

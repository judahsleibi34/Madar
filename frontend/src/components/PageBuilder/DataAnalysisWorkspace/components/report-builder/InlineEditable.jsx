export default function InlineEditable({
  value,
  placeholder,
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

  const commonProps = {
    className: `daw-report-editable ${className}`,
    contentEditable: editable,
    suppressContentEditableWarning: true,
    role: "textbox",
    "aria-multiline": multiline,
    dir: direction,
    "data-placeholder": placeholder,
    onKeyDown: handleKeyDown,
    onFocus,
    onPaste: (event) => {
      event.preventDefault();
      document.execCommand("insertText", false, event.clipboardData.getData("text/plain"));
    },
  };

  if (multiline) {
    return (
      <div
        {...commonProps}
        onBlur={(event) => onChange(event.currentTarget.innerHTML, event.currentTarget.dir)}
        dangerouslySetInnerHTML={{ __html: value }}
      />
    );
  }

  return (
    <div
      {...commonProps}
    onBlur={(event) => onChange(event.currentTarget.innerHTML, event.currentTarget.dir)}
    dangerouslySetInnerHTML={{ __html: value }}
    />
  );
}

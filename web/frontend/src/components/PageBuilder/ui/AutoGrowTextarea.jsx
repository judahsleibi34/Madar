import { useLayoutEffect, useRef } from "react";

export default function AutoGrowTextarea({ value = "", className = "", onInput, ...props }) {
  const textareaRef = useRef(null);

  const resize = (node = textareaRef.current) => {
    if (!node) return;
    node.style.removeProperty("--auto-grow-height");
    node.style.setProperty("--auto-grow-height", `${Math.max(72, node.scrollHeight)}px`);
  };

  useLayoutEffect(() => {
    resize();
  }, [value]);

  return (
    <textarea
      {...props}
      ref={textareaRef}
      rows={3}
      value={value}
      className={`auto-grow-textarea ${className}`.trim()}
      onInput={(event) => {
        resize(event.currentTarget);
        onInput?.(event);
      }}
    />
  );
}

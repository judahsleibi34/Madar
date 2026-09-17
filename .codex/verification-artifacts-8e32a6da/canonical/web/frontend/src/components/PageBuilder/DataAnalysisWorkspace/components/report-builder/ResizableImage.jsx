import { useRef } from "react";

const clamp = (value, minimum, maximum) => Math.min(Math.max(value, minimum), maximum);

export default function ResizableImage({
  src,
  alt,
  widthPercent = 76,
  ratio = "original",
  offsetX = 0,
  offsetY = 0,
  onUpdate,
  children,
}) {
  const frameRef = useRef(null);
  const interactionRef = useRef(null);

  const startMove = (event) => {
    if (event.target.closest(".daw-report-image-resize-handle, .daw-report-editable, button, input, textarea")) return;
    const frame = frameRef.current;
    const page = frame?.closest(".daw-report-page");
    if (!frame || !page) return;

    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    interactionRef.current = {
      mode: "move",
      startX: event.clientX,
      startY: event.clientY,
      offsetX,
      offsetY,
      frameRect: frame.getBoundingClientRect(),
      pageRect: page.getBoundingClientRect(),
    };
  };

  const startResize = (event) => {
    const frame = frameRef.current;
    const page = frame?.closest(".daw-report-page");
    if (!frame || !page) return;

    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    interactionRef.current = {
      mode: "resize",
      startX: event.clientX,
      width: frame.getBoundingClientRect().width,
      maximumWidth: page.getBoundingClientRect().width - 40,
    };
  };

  const handlePointerMove = (event) => {
    const interaction = interactionRef.current;
    if (!interaction) return;

    if (interaction.mode === "resize") {
      const width = clamp(interaction.width + event.clientX - interaction.startX, 120, interaction.maximumWidth);
      onUpdate({ imageWidthPercent: Math.round((width / interaction.maximumWidth) * 100) });
      return;
    }

    const deltaX = event.clientX - interaction.startX;
    const deltaY = event.clientY - interaction.startY;
    const desiredLeft = interaction.frameRect.left + deltaX;
    const desiredTop = interaction.frameRect.top + deltaY;
    const left = clamp(desiredLeft, interaction.pageRect.left + 20, interaction.pageRect.right - interaction.frameRect.width - 20);
    const top = clamp(desiredTop, interaction.pageRect.top + 20, interaction.pageRect.bottom - interaction.frameRect.height - 20);

    onUpdate({
      imageOffsetX: Math.round(interaction.offsetX + left - interaction.frameRect.left),
      imageOffsetY: Math.round(interaction.offsetY + top - interaction.frameRect.top),
    });
  };

  const finishInteraction = (event) => {
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    interactionRef.current = null;
  };

  return (
    <div
      ref={frameRef}
      className="daw-report-image-frame"
      style={{
        width: `${clamp(widthPercent, 20, 100)}%`,
        aspectRatio: ratio === "original" ? "auto" : ratio,
        transform: `translate(${offsetX}px, ${offsetY}px)`,
      }}
      onPointerDown={startMove}
      onPointerMove={handlePointerMove}
      onPointerUp={finishInteraction}
      onPointerCancel={finishInteraction}
    >
      <img className={`daw-report-content-image ${ratio === "original" ? "" : "has-fixed-ratio"}`} src={src} alt={alt} draggable="false" />
      {children}
      <button
        type="button"
        className="daw-report-image-resize-handle"
        aria-label="Resize image"
        title="Drag to resize image"
        onPointerDown={startResize}
        onPointerMove={handlePointerMove}
        onPointerUp={finishInteraction}
        onPointerCancel={finishInteraction}
      />
    </div>
  );
}

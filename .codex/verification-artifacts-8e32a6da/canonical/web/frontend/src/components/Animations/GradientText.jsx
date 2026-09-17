export default function GradientText({
  children,
  className = "",
  colors = ["var(--theme-secondary)", "var(--theme-primary)", "var(--theme-primary-hover)"],
  animationSpeed = 8,
  direction = "horizontal",
  pauseOnHover = false,
  yoyo = true,
  showBorder = false,
}) {
  const angle =
    direction === "vertical"
      ? "180deg"
      : direction === "diagonal"
        ? "135deg"
        : "90deg";

  return (
    <span
      className={[
        "gradient-text",
        showBorder ? "gradient-text-bordered" : "",
        pauseOnHover ? "gradient-text-pause-hover" : "",
        yoyo ? "gradient-text-yoyo" : "",
        className,
      ].filter(Boolean).join(" ")}
      style={{
        "--gradient-text-colors": colors.join(", "),
        "--gradient-text-speed": `${animationSpeed}s`,
        "--gradient-text-angle": angle,
      }}
    >
      {children}
    </span>
  );
}

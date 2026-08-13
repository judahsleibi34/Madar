export default function LoadingBar({
  className = "",
  label = "Loading",
  mode = "page",
}) {
  return (
    <div
      className={["app-loading", `app-loading-${mode}`, className]
        .filter(Boolean)
        .join(" ")}
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="app-loading-track" aria-hidden="true"><span /></div>
      <span className="app-loading-label">{label}</span>
    </div>
  );
}

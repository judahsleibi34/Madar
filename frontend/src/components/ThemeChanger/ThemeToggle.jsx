import { Moon, Sun } from "lucide-react";
import "./ThemeToggle.css";

export default function ThemeToggle({
  mode = "light",
  onChange,
  label = "Theme",
  compact = false,
  showLabel,
  showSwitch,
  className = "",
}) {
  const isDark = mode === "dark";
  const shouldShowLabel = showLabel ?? !compact;
  const shouldShowSwitch = showSwitch ?? !compact;

  const handleToggle = () => {
    const nextMode = isDark ? "light" : "dark";

    if (typeof onChange === "function") {
      onChange(nextMode);
    }
  };

  return (
    <button
      type="button"
      className={[
        "theme-toggle",
        isDark ? "is-dark" : "is-light",
        compact ? "is-compact" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      onClick={handleToggle}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      title={isDark ? "Switch to light theme" : "Switch to dark theme"}
    >
      <span className="theme-toggle-left">
        <span className="theme-toggle-icon" aria-hidden="true">
          {isDark ? <Moon size={17} /> : <Sun size={17} />}
        </span>

        {shouldShowLabel && <span className="theme-toggle-label">{label}</span>}
      </span>

      {shouldShowSwitch && (
        <span className="theme-toggle-switch" aria-hidden="true">
          <span className="theme-toggle-thumb" />
        </span>
      )}
    </button>
  );
}

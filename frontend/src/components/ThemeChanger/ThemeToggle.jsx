import { Moon, Sun } from "lucide-react";
import "./ThemeToggle.css";

export default function ThemeToggle({
  mode = "light",
  onChange,
  label = "Theme",
  compact = false,
  className = "",
}) {
  const isDark = mode === "dark";

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

        {!compact && <span className="theme-toggle-label">{label}</span>}
      </span>

      {!compact && (
        <span className="theme-toggle-switch" aria-hidden="true">
          <span className="theme-toggle-thumb" />
        </span>
      )}
    </button>
  );
}
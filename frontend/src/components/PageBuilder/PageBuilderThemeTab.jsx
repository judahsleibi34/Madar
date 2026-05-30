export default function PageBuilderThemeTab({
  project,
  updateProject,
  setThemeMode,
}) {
  return (
    <div className="workspace-page">
      <div className="workspace-header">
        <div>
          <h2>Theme</h2>
          <p>Global design system values applied to the builder and preview shell.</p>
        </div>

        <div className="header-actions">
          <button
            type="button"
            className={project.theme?.mode === "light" ? "active" : ""}
            onClick={() => setThemeMode("light")}
          >
            Light
          </button>

          <button
            type="button"
            className={project.theme?.mode === "dark" ? "active" : ""}
            onClick={() => setThemeMode("dark")}
          >
            Dark
          </button>
        </div>
      </div>

      <section className="theme-grid">
        {[
          ["background", "App background"],
          ["surface", "Surface"],
          ["softSurface", "Soft surface"],
          ["text", "Text"],
          ["muted", "Muted"],
          ["primary", "Primary"],
          ["accent", "Accent"],
          ["accentDark", "Accent dark"],
        ].map(([key, label]) => (
          <label className="theme-control" key={key}>
            {label}
            <input
              type="color"
              value={project.theme?.[key] || "#000000"}
              onChange={(event) =>
                updateProject((prev) => ({
                  ...prev,
                  theme: {
                    ...prev.theme,
                    [key]: event.target.value,
                  },
                }))
              }
            />
          </label>
        ))}

        <label className="theme-control">
          Radius
          <input
            type="number"
            value={project.theme?.radius || 18}
            onChange={(event) =>
              updateProject((prev) => ({
                ...prev,
                theme: {
                  ...prev.theme,
                  radius: Number(event.target.value),
                },
              }))
            }
          />
        </label>

        <label className="theme-control">
          Font family
          <input
            value={project.theme?.fontFamily || "Inter"}
            onChange={(event) =>
              updateProject((prev) => ({
                ...prev,
                theme: {
                  ...prev.theme,
                  fontFamily: event.target.value,
                },
              }))
            }
          />
        </label>
      </section>
    </div>
  );
}
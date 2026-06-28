# Theme Variables

Edit public website design values in `src/styles/variables.css`.

- Colors: `--color-*`
- Typography: `--font-*` and `--line-height-*`
- Spacing: `--space-*`
- Radius: `--radius-*`
- Shadows: `--shadow-*`
- Layout widths and layering: `--container-*` and `--z-*`

`variables.css` aliases the existing core theme in `src/styles/core/tokens.css`, so current light/dark theme behavior stays intact while giving future redesign work one stable place to start.

For a redesign, adjust variables first. Component CSS should use these variables for reusable colors, spacing, radii, shadows, and typography; keep hardcoded values only for highly specific layout geometry or one-off animation math.

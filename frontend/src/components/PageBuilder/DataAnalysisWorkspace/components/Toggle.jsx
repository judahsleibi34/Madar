export default function Toggle({ checked, onChange, children, description = "" }) {
  return (
    <label className="daw-toggle">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span>
        <span className="daw-toggle-title">{children}</span>
        {description ? (
          <span className="daw-toggle-description">{description}</span>
        ) : null}
      </span>
    </label>
  );
}

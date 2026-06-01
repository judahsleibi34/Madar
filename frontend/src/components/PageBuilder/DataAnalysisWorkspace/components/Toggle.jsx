export default function Toggle({ checked, onChange, children }) {
  return (
    <label className="daw-toggle">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span>{children}</span>
    </label>
  );
}

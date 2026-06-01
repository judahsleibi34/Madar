export default function Field({ label, children, wide = false }) {
  return (
    <label className={`daw-field${wide ? " wide" : ""}`}>
      <span>{label}</span>
      {children}
    </label>
  );
}

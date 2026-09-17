export default function EmptyState({ title, children, className = "" }) {
  return (
    <div className={["daw-empty", className].filter(Boolean).join(" ")}>
      <strong>{title}</strong>
      {children ? <p>{children}</p> : null}
    </div>
  );
}

export default function EmptyState({ title, children }) {
  return (
    <div className="daw-empty">
      <strong>{title}</strong>
      {children ? <p>{children}</p> : null}
    </div>
  );
}

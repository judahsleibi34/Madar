export default function PageBuilderTopbar({
  project,
  displayName,
  activeHelper,
}) {
  return (
    <header className="builder-topbar">
      <div className="builder-brand">
        <h1>{displayName || project.name}</h1>
        <p>{activeHelper}</p>
      </div>
    </header>
  );
}


export default function ResponsesHeader({ t }) {
  return (
    <header className="workspace-header responses-results-header app-page-intro">
      <div>
        <h1>{t.title}</h1>
        <p>{t.subtitle}</p>
      </div>
    </header>
  );
}

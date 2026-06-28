export default function ResponsesHeader({ t }) {
  return (
    <div className="workspace-header responses-results-header">
      <div>
        <span className="workspace-kicker">{t.kicker}</span>
        <h2>{t.title}</h2>
        <p>{t.subtitle}</p>
      </div>
    </div>
  );
}

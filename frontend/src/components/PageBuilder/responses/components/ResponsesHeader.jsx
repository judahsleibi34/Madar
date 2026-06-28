export default function ResponsesHeader({ t, selectedForm, selectForm, copyResults }) {
  return (
    <div className="workspace-header responses-results-header">
      <div>
        <span className="workspace-kicker">{t.kicker}</span>
        <h2>{t.title}</h2>
        <p>{t.subtitle}</p>
      </div>

      <div className="responses-header-actions">
        <button type="button" onClick={copyResults}>
          {t.copy}
        </button>

        <button
          type="button"
          className="primary-action"
          onClick={() => {
            if (selectedForm) selectForm(selectedForm.id);
            window.location.href = "/page-builder";
          }}
        >
          {t.openBuilder}
        </button>
      </div>
    </div>
  );
}

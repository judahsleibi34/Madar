export default function ResponseSettingsPanel({ form, t, updateActiveForm, showToast }) {
  const resumeLaterEnabled = form?.resumeLaterEnabled !== false;
  const canUpdate = typeof updateActiveForm === "function";

  const toggleResumeLater = (event) => {
    if (!canUpdate) return;
    const enabled = event.target.checked;
    updateActiveForm((currentForm) => ({
      ...currentForm,
      resumeLaterEnabled: enabled,
    }));
    showToast?.(enabled ? t.resumeSettingEnabled : t.resumeSettingDisabled);
  };

  return (
    <section className="response-settings-panel" aria-labelledby="response-settings-heading">
      <header className="response-settings-header">
        <h2 id="response-settings-heading">{t.draftSettingsTitle}</h2>
        <p>{t.draftSettingsText}</p>
      </header>

      <div className="response-setting-row">
        <div>
          <strong>{t.allowResumeLater}</strong>
          <p>{t.allowResumeLaterText}</p>
        </div>
        <label className="response-setting-switch">
          <input
            type="checkbox"
            role="switch"
            checked={resumeLaterEnabled}
            disabled={!canUpdate}
            onChange={toggleResumeLater}
          />
          <span aria-hidden="true" />
          <span className="sr-only">{t.allowResumeLater}</span>
        </label>
      </div>
    </section>
  );
}

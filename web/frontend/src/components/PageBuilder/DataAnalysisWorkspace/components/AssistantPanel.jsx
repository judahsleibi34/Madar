import Field from './Field';
import ResultView from './ResultView';

export default function AssistantPanel({
  dataset,
  assistQuestion,
  setAssistQuestion,
  runAssistedQuestion,
  assistResult,
  isLoading,
  t,
}) {
  return (
    <section className="daw-card daw-assistant-card">
      <div className="daw-section-heading">
        <span>{t.optional}</span>
        <h3>{t.askAssistant}</h3>
        <p>{t.assistantSubtitle}</p>
      </div>

      <Field label={t.assistant}>
        <textarea
          value={assistQuestion}
          rows={4}
          disabled={!dataset}
          placeholder={dataset ? t.assistantPlaceholder : t.assistantWaiting}
          onChange={(event) => setAssistQuestion(event.target.value)}
          onKeyDown={(event) => {
            if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
              runAssistedQuestion();
            }
          }}
        />
      </Field>

      <button
        type="button"
        className="daw-primary"
        disabled={!dataset || isLoading || !assistQuestion.trim()}
        onClick={runAssistedQuestion}
      >
        {isLoading ? t.working : t.ask}
      </button>

      {assistResult ? (
        <div className="daw-assistant-result">
          <ResultView value={assistResult} t={t} />
        </div>
      ) : null}
    </section>
  );
}

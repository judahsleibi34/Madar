export default function ResponsesSummary({
  t,
  allForms,
  totalResponses,
  fields,
  completionRate,
}) {
  return (
    <section className="results-summary-grid">
      <article>
        <span>{t.forms}</span>
        <strong>{allForms.length}</strong>
      </article>

      <article>
        <span>{t.submissions}</span>
        <strong>{totalResponses}</strong>
      </article>

      <article>
        <span>{t.questions}</span>
        <strong>{fields.length}</strong>
      </article>

      <article>
        <span>{t.completion}</span>
        <strong>{completionRate}%</strong>
      </article>
    </section>
  );
}

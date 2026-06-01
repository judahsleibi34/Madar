import EmptyState from './EmptyState';
import ResultView from './ResultView';

export default function DatasetReviewStep({ dataset, inspection, runInspection, isLoading, t }) {
  const reviewActions = [
    {
      id: "overview",
      label: t.overview,
      hint: t.reviewOverviewHint || "Understand what is inside the dataset.",
    },
    {
      id: "statistics",
      label: t.statistics,
      hint: t.reviewStatisticsHint || "See totals, common answers, and numeric summaries.",
    },
    {
      id: "missing",
      label: t.missing,
      hint: t.reviewMissingHint || "Find empty answers that may affect reporting.",
    },
    {
      id: "quality",
      label: t.quality,
      hint: t.reviewQualityHint || "Check readiness, duplicates, and cleanup advice.",
    },
  ];

  return (
    <section className="daw-card daw-section-card">
      <div className="daw-section-heading">
        <span>{t.review}</span>
        <h3>{t.reviewTitle}</h3>
        <p>{t.reviewSubtitle}</p>
      </div>

      {!dataset ? (
        <EmptyState title={t.noDataset}>{t.noDatasetHint}</EmptyState>
      ) : (
        <div className="daw-review-shell">
          <aside className="daw-review-sidebar" aria-label={t.review}>
            {reviewActions.map((action) => (
              <button
                key={action.id}
                type="button"
                className={inspection?.type === action.id ? "active" : ""}
                disabled={isLoading}
                onClick={() => runInspection(action.id)}
              >
                <strong>{action.label}</strong>
                <span>{action.hint}</span>
              </button>
            ))}
          </aside>

          <div className="daw-inspection-box">
            {inspection ? (
              <ResultView value={inspection.data} type={inspection.type} t={t} />
            ) : (
              <EmptyState title={t.review}>{t.inspectionWaiting}</EmptyState>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

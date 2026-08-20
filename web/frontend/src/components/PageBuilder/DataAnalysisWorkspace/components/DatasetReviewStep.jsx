import { useEffect, useRef } from 'react';
import EmptyState from './EmptyState';
import ResultView from './ResultView';

export default function DatasetReviewStep({ dataset, inspection, runInspection, isLoading, t }) {
  const inspectionBoxRef = useRef(null);
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
      id: "quality",
      label: t.quality,
      hint: t.reviewQualityHint || "Inspect qualitative columns, unique values, and field coverage.",
    },
    {
      id: "missing",
      label: t.missing,
      hint: t.reviewMissingHint || "Find empty answers that may affect reporting.",
    },
  ];

  const resetInspectionScroll = () => {
    if (!inspectionBoxRef.current) return;
    inspectionBoxRef.current.scrollTo({ top: 0, left: 0, behavior: "auto" });
  };

  useEffect(() => {
    resetInspectionScroll();
  }, [inspection?.type]);

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
                onClick={() => {
                  resetInspectionScroll();
                  runInspection(action.id);
                }}
              >
                <strong>{action.label}</strong>
                <span>{action.hint}</span>
              </button>
            ))}
          </aside>

          <div className="daw-inspection-box" ref={inspectionBoxRef}>
            {inspection ? (
              <ResultView value={inspection.data} type={inspection.type} t={t} />
            ) : (
              <EmptyState title={t.review} className="daw-empty-fill">
                {t.inspectionWaiting}
              </EmptyState>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

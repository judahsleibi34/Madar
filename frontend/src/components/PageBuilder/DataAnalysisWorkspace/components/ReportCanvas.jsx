import EmptyState from './EmptyState';
import DataPreviewGrid from './DataPreviewGrid';
import ResultView from './ResultView';
import { getDatasetTitle, methodLabel } from '../utils/formatters';

export default function ReportCanvas({
  dataset,
  analysisResult,
  analysisPayload,
  activeMethod,
  activeLang,
  reportOptions,
  t,
}) {
  const reportTitle = reportOptions?.title?.trim();

  return (
    <article className="daw-card daw-report-canvas">
      <div className="daw-report-header">
        <div>
          <span>{t.reportCanvas}</span>
          <h3>
            {analysisResult && reportTitle
              ? reportTitle
              : analysisResult
              ? methodLabel(activeMethod, activeLang)
              : getDatasetTitle(dataset, t)}
          </h3>
          <p>
            {dataset
              ? `${dataset.rows || 0} ${t.rows} · ${dataset.columns?.length || 0} ${t.columns}`
              : t.noDatasetHint}
          </p>
        </div>
      </div>

      {!dataset ? (
        <EmptyState title={t.noDataset}>{t.noDatasetHint}</EmptyState>
      ) : analysisResult ? (
        <ResultView value={analysisPayload} reportOptions={reportOptions} t={t} />
      ) : (
        <>
          <div className="daw-dataset-stats">
            <article>
              <span>{t.rows}</span>
              <strong>{dataset.rows || 0}</strong>
            </article>

            <article>
              <span>{t.columns}</span>
              <strong>{dataset.columns?.length || 0}</strong>
            </article>
          </div>

          <DataPreviewGrid columns={dataset.columns || []} rows={dataset.preview || []} t={t} />
        </>
      )}
    </article>
  );
}

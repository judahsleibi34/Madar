import EmptyState from './EmptyState';
import ReportTable from './ReportTable';
import { displayValue, toLabel, valueDir } from '../utils/formatters';

const isPlainObject = (value) =>
  value && typeof value === "object" && !Array.isArray(value);

const objectToRows = (items, mapValue) =>
  Object.entries(items || {}).map(([key, value]) => mapValue(key, value));

const compactList = (value, t) => {
  if (!Array.isArray(value)) return displayValue(value, t);
  if (!value.length) return "-";
  return value.slice(0, 4).map((item) => displayValue(item, t)).join(", ");
};

const percentage = (value) => {
  const number = Number(value || 0);
  return `${Number.isInteger(number) ? number : Number(number.toFixed(2))}%`;
};

const friendlyType = (type, t) => t.typeLabels?.[type] || toLabel(type || "text");

const translatedAction = (action, t) => {
  const actionMap = {
    "Review or fill empty answers before reporting.": t.actionReviewMissing,
    "Remove duplicate rows before reporting.": t.actionRemoveDuplicates,
    "Check columns that may have mixed formats.": t.actionCheckMixedFormats,
    "No major cleanup needed before reporting.": t.actionNoCleanupNeeded,
  };

  return actionMap[action] || action;
};

const translatedReadiness = (value, fallbackReady, t) => {
  if (value === "Ready to use") return t.readyToUse || value;
  if (value === "Needs review") return t.needsReview || value;
  return value || fallbackReady;
};

const SummaryCards = ({ cards }) => (
  <div className="daw-review-summary-grid">
    {cards.map((card) => (
      <article key={card.label} className={card.tone ? `tone-${card.tone}` : ""}>
        <span>{card.label}</span>
        <strong>{card.value}</strong>
        {card.help ? <small>{card.help}</small> : null}
      </article>
    ))}
  </div>
);

const InsightList = ({ title, items = [] }) => {
  if (!items.length) return null;

  return (
    <section className="daw-friendly-panel">
      <h4>{title}</h4>
      <ul>
        {items.map((item, index) => (
          <li key={`${title}_${index}`}>{item}</li>
        ))}
      </ul>
    </section>
  );
};

const WarningList = ({ warnings, t }) => {
  if (!Array.isArray(warnings) || !warnings.length) return null;

  return (
    <InsightList
      title={t.warnings}
      items={warnings.map((warning) => displayValue(warning, t))}
    />
  );
};

const profileRows = (profiles = {}, t) =>
  objectToRows(profiles, (column, profile) => ({
    [t.field || "Field"]: column,
    [t.bestUse || "Best use"]: friendlyType(profile.type, t),
    [t.filledAnswers || "Filled answers"]: profile.count,
    [t.emptyAnswers || "Empty answers"]: profile.missing_values,
    [t.emptyPercent || "Empty %"]: percentage(profile.missing_percentage),
    [t.differentAnswers || "Different answers"]: profile.unique_count,
    [t.examples || "Examples"]: compactList(profile.sample, t),
  }));

const renderMissing = (value, t) => {
  const rows = objectToRows(value, (column, report) => ({
    [t.field || "Field"]: column,
    [t.emptyAnswers || "Empty answers"]: report.missing_count,
    [t.emptyPercent || "Empty %"]: percentage(report.missing_percentage),
    [t.status || "Status"]: Number(report.missing_count || 0) ? t.needsAttention || "Needs attention" : t.complete || "Complete",
  }));
  const emptyFields = rows.filter((row) => Number(row[t.emptyAnswers || "Empty answers"] || 0) > 0);

  return (
    <div className="daw-report-result">
      <SummaryCards
        cards={[
          {
            label: t.fieldsChecked || "Fields checked",
            value: rows.length,
            help: t.columnsReviewed || "Columns reviewed for empty answers.",
          },
          {
            label: t.fieldsWithGaps || "Fields with gaps",
            value: emptyFields.length,
            tone: emptyFields.length ? "warn" : "good",
            help: emptyFields.length ? t.reviewBeforeReporting || "Review these before reporting." : t.noMissingAnswers || "No missing answers found.",
          },
        ]}
      />
      <InsightList
        title={t.whatThisMeans || "What this means"}
        items={[
          emptyFields.length
            ? t.fieldsHaveEmptyAnswers?.(emptyFields.length) || `${emptyFields.length} field${emptyFields.length === 1 ? "" : "s"} have empty answers.`
            : t.allFieldsComplete || "All checked fields are complete.",
        ]}
      />
      <ReportTable table={{ title: t.missing, rows }} t={t} variant="compact" />
    </div>
  );
};

const renderStatistics = (value, t) => {
  const numericRows = objectToRows(value.numeric_columns, (column, stats) => ({
    [t.field || "Field"]: column,
    [t.type || "Type"]: t.numberType || "Number",
    [t.filledAnswers || "Filled answers"]: stats.filled_values ?? stats.count,
    [t.average || "Average"]: stats.mean,
    [t.middle || "Middle"]: stats.median,
    [t.lowest || "Lowest"]: stats.min,
    [t.highest || "Highest"]: stats.max,
    [t.total || "Total"]: stats.sum,
    [t.emptyAnswers || "Empty answers"]: stats.missing_values,
    [t.emptyPercent || "Empty %"]: percentage(stats.missing_percentage),
  }));
  const categoryRows = objectToRows(value.categorical_columns, (column, stats) => ({
    [t.field || "Field"]: column,
    [t.type || "Type"]: t.textChoiceType || "Text or choice",
    [t.filledAnswers || "Filled answers"]: stats.filled_values ?? stats.count,
    [t.differentAnswers || "Different answers"]: stats.unique_count,
    [t.mostCommon || "Most common"]: compactList(stats.most_common, t),
    [t.examples || "Examples"]: compactList(stats.examples || stats.unique_values_sample, t),
    [t.emptyAnswers || "Empty answers"]: stats.missing_values,
    [t.emptyPercent || "Empty %"]: percentage(stats.missing_percentage),
  }));
  const hasNumeric = numericRows.length > 0;
  const hasCategories = categoryRows.length > 0;

  return (
    <div className="daw-report-result">
      <SummaryCards
        cards={[
          { label: t.rowsAnalyzed || "Rows analyzed", value: value.rows ?? "-", help: t.responsesIncluded || "Responses included in this check." },
          { label: t.numberFields || "Number fields", value: numericRows.length, help: t.numberFieldsHint || "Fields where averages and totals apply." },
          { label: t.textFields || "Text fields", value: categoryRows.length, help: t.textFieldsHint || "Fields summarized by common answers." },
        ]}
      />
      <InsightList
        title={t.whatThisMeans || "What this means"}
        items={[
          hasNumeric
            ? t.numericStatsHint || "Numeric fields include averages, totals, lowest, and highest values."
            : t.noNumericStatsHint || "No number fields were detected, so this dataset is summarized by common answers instead of averages.",
          hasCategories
            ? t.categoryStatsHint || "Text and choice fields show the most common answer and example values."
            : t.noCategoryStatsHint || "No text or choice fields were detected.",
        ]}
      />
      <WarningList warnings={value.warnings} t={t} />
      {hasNumeric ? <ReportTable table={{ title: t.numberSummaries || "Number summaries", rows: numericRows }} t={t} variant="compact" /> : null}
      {hasCategories ? <ReportTable table={{ title: t.answerSummaries || "Answer summaries", rows: categoryRows }} t={t} variant="compact" /> : null}
    </div>
  );
};

const renderOverview = (value, t) => {
  const rows = objectToRows(value.unique_values, (column, details) => ({
    [t.field || "Field"]: column,
    [t.differentAnswers || "Different answers"]: details.count,
    [t.emptyAnswers || "Empty answers"]: details.missing_values,
    [t.examples || "Examples"]: compactList(details.sample, t),
  }));

  return (
    <div className="daw-report-result">
      <SummaryCards
        cards={[
          { label: t.rows || "Rows", value: value.rows ?? "-", help: t.rowsLoadedHint || "Records loaded from the source." },
          {
            label: t.fields || "Fields",
            value: Array.isArray(value.columns) ? value.columns.length : rows.length,
            help: t.fieldsAvailableHint || "Columns available for reporting.",
          },
        ]}
      />
      <InsightList
        title={t.whatThisMeans || "What this means"}
        items={[
          t.datasetShape?.(value.rows ?? 0, Array.isArray(value.columns) ? value.columns.length : rows.length) || `The dataset has ${value.rows ?? 0} row${Number(value.rows) === 1 ? "" : "s"} and ${Array.isArray(value.columns) ? value.columns.length : rows.length} fields.`,
          t.confirmExpectedFields || "Use this view to confirm the expected fields were imported before building a report.",
        ]}
      />
      <WarningList warnings={value.warnings} t={t} />
      <ReportTable table={{ title: t.overview, rows }} t={t} variant="compact" />
      <ReportTable table={{ title: t.fieldGuide || "Field guide", rows: profileRows(value.profiles, t) }} t={t} variant="compact" />
    </div>
  );
};

const renderQuality = (value, t) => {
  const actions = Array.isArray(value.recommended_actions)
    ? value.recommended_actions.map((action) => translatedAction(action, t))
    : [];
  const score = Number(value.quality_score ?? 0);
  const summaryRows = [
    { [t.check || "Check"]: t.readyForReporting || "Ready for reporting", [t.result || "Result"]: translatedReadiness(value.readiness, score >= 90 ? t.readyToUse || "Ready to use" : t.needsReview || "Needs review", t) },
    { [t.check || "Check"]: t.completeAnswers || "Complete answers", [t.result || "Result"]: percentage(value.completion_percentage) },
    { [t.check || "Check"]: t.emptyCells || "Empty cells", [t.result || "Result"]: value.missing_cells },
    { [t.check || "Check"]: t.duplicateRows || "Duplicate rows", [t.result || "Result"]: value.duplicate_rows },
    { [t.check || "Check"]: t.rowsChecked || "Rows checked", [t.result || "Result"]: value.rows },
    { [t.check || "Check"]: t.fieldsCheckedShort || "Fields checked", [t.result || "Result"]: value.columns },
  ];
  const typeRows = objectToRows(value.profiles, (column, profile) => ({
    [t.field || "Field"]: column,
    [t.bestUse || "Best use"]: friendlyType(profile.type, t),
    [t.emptyAnswers || "Empty answers"]: profile.missing_values,
    [t.emptyPercent || "Empty %"]: percentage(profile.missing_percentage),
    [t.differentAnswers || "Different answers"]: profile.unique_count,
  }));

  return (
    <div className="daw-report-result">
      <SummaryCards
        cards={[
          {
            label: t.qualityScore || "Quality score",
            value: `${score}%`,
            tone: score >= 90 ? "good" : "warn",
            help: t.qualityScoreHint || "Based on missing answers and duplicates.",
          },
          {
            label: t.completeAnswers || "Complete answers",
            value: percentage(value.completion_percentage),
            help: t.completeAnswersHint || "How much of the dataset is filled.",
          },
          {
            label: t.duplicateRows || "Duplicate rows",
            value: value.duplicate_rows ?? 0,
            tone: Number(value.duplicate_rows || 0) ? "warn" : "good",
            help: t.duplicateRowsHint || "Repeated records found.",
          },
        ]}
      />
      <InsightList title={t.recommendedNextSteps || "Recommended next steps"} items={actions} />
      <WarningList warnings={value.warnings} t={t} />
      <ReportTable table={{ title: t.quality, rows: summaryRows }} t={t} variant="compact" />
      <ReportTable table={{ title: t.fieldQuality || "Field quality", rows: typeRows }} t={t} variant="compact" />
    </div>
  );
};

export default function ResultView({ value, type, reportOptions = {}, t }) {
  if (!value) {
    return <EmptyState title={t.noResult}>{t.reportWaiting}</EmptyState>;
  }

  if (
    type === "missing" ||
    (isPlainObject(value) &&
      Object.values(value).length > 0 &&
      Object.values(value).every(
        (item) =>
          isPlainObject(item) &&
          "missing_count" in item &&
          "missing_percentage" in item
      ))
  ) {
    return renderMissing(value, t);
  }

  if (type === "statistics" || (isPlainObject(value) && ("numeric_columns" in value || "categorical_columns" in value))) {
    return renderStatistics(value, t);
  }

  if (type === "overview" || (isPlainObject(value) && "unique_values" in value)) {
    return renderOverview(value, t);
  }

  if (type === "quality" || (isPlainObject(value) && "duplicate_rows" in value)) {
    return renderQuality(value, t);
  }

  const isReportObject =
    value &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    ("summary" in value ||
      "insights" in value ||
      "kpis" in value ||
      "tables" in value ||
      "charts" in value);

  if (isReportObject) {
    const kpis = Array.isArray(value.kpis) ? value.kpis : [];
    const insights = Array.isArray(value.insights) ? value.insights : [];
    const warnings = Array.isArray(value.warnings) ? value.warnings : [];
    const tables = Array.isArray(value.tables) ? value.tables : [];
    const charts = Array.isArray(value.charts) ? value.charts : [];
    const showSummary = reportOptions.includeSummary !== false;
    const showKpis = reportOptions.includeKpis !== false;
    const showInsights = reportOptions.includeInsights !== false;
    const showWarnings = reportOptions.includeWarnings !== false;
    const showTables = reportOptions.includeTables !== false;
    const showCharts = reportOptions.includeCharts !== false;

    return (
      <div className="daw-report-result">
        {showSummary && value.summary ? (
          <section className="daw-report-summary">
            <span>{t.summary}</span>
            <p>{value.summary}</p>
          </section>
        ) : null}

        {showWarnings ? <WarningList warnings={warnings} t={t} /> : null}

        {showKpis && kpis.length ? (
          <section className="daw-kpi-grid">
            {kpis.map((kpi, index) => (
              <article key={`kpi_${index}`}>
                <span>{kpi.label || kpi.name || t.result}</span>
                <strong>{displayValue(kpi.value ?? kpi.amount ?? kpi.result, t)}</strong>
                {kpi.unit ? <small>{kpi.unit}</small> : null}
              </article>
            ))}
          </section>
        ) : null}

        {showInsights && insights.length ? (
          <InsightList title={t.insights} items={insights.map((insight) => displayValue(insight, t))} />
        ) : null}

        {showTables ? tables.map((table, index) => (
          <ReportTable key={`table_${index}`} table={table} t={t} />
        )) : null}

        {showCharts && charts.length ? (
          <section className="daw-report-block">
            <h4>{t.charts}</h4>
            <div className="daw-chart-list">
              {charts.map((chart, index) => (
                <article key={`chart_${index}`}>
                  <strong>{chart.title || chart.name || `${t.charts} ${index + 1}`}</strong>
                  <p>{chart.type || chart.chart_type || "-"}</p>
                </article>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    );
  }

  if (value && typeof value === "object" && !Array.isArray(value)) {
    return (
      <div className="daw-object-grid">
        {Object.entries(value).map(([key, item]) => (
          <article key={key}>
            <span>{toLabel(key)}</span>
            <strong dir={valueDir(item)}>{displayValue(item, t)}</strong>
          </article>
        ))}
      </div>
    );
  }

  return <pre className="daw-json-output">{displayValue(value, t)}</pre>;
}

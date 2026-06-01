import Field from './Field';
import Toggle from './Toggle';
import ColumnSelect from './ColumnSelect';
import MultiColumnSelect from './MultiColumnSelect';
import EmptyState from './EmptyState';
import { analysisGroups, reportGroupText } from '../constants/analysisConfig';
import { methodLabel, toLabel } from '../utils/formatters';

export default function ReportBuilderStep({
  dataset,
  activeLang,
  analysisDomain,
  setDomain,
  methods,
  analysisMethod,
  setMethod,
  activeMethod,
  params,
  updateParams,
  columns,
  numericColumns,
  runAnalysis,
  isLoading,
  reportOptions,
  updateReportOptions,
  t,
}) {
  const groups = reportGroupText[activeLang];
  const getParamValue = (key) =>
    Object.prototype.hasOwnProperty.call(params || {}, key)
      ? params[key]
      : activeMethod.template[key];

  const renderParamControl = ([key, value]) => {
    const label = toLabel(key, activeLang);

    const optional =
      key.includes("group") ||
      key.includes("category") ||
      key.includes("expense_column") ||
      key.includes("transaction_id") ||
      key.includes("numerator") ||
      key.includes("denominator");

    if (Array.isArray(value)) {
      return (
        <MultiColumnSelect
          key={key}
          label={label}
          value={value}
          columns={key.includes("numeric") || key.includes("value") ? numericColumns : columns}
          onChange={(nextValue) => updateParams(key, nextValue)}
          activeLang={activeLang}
          t={t}
        />
      );
    }

    if (key === "rows" || key === "max_rating") {
      return (
        <Field key={key} label={label}>
          <input
            type="number"
            min="1"
            value={value}
            onChange={(event) => updateParams(key, Number(event.target.value || 1))}
          />
        </Field>
      );
    }

    if (key === "operation") {
      return (
        <Field key={key} label={label}>
          <select value={value || "sum"} onChange={(event) => updateParams(key, event.target.value)}>
            {[
              "sum",
              "mean",
              "median",
              "min",
              "max",
              "count",
              "rate",
              "ratio",
              "percentage",
              "difference",
              "variance",
              "gap",
            ].map((option) => (
              <option key={option} value={option}>
                {toLabel(option, activeLang)}
              </option>
            ))}
          </select>
        </Field>
      );
    }

    if (key === "question") {
      return (
        <Field key={key} label={label}>
          <textarea
            value={value || ""}
            rows={3}
            onChange={(event) => updateParams(key, event.target.value)}
          />
        </Field>
      );
    }

    if (key.endsWith("_column") || key === "column") {
      const numericHints = [
        "amount",
        "cost",
        "revenue",
        "actual",
        "target",
        "price",
        "quantity",
        "budget",
        "baseline",
        "endline",
        "value",
        "numerator",
        "denominator",
        "rating",
      ];

      return (
        <ColumnSelect
          key={key}
          label={label}
          value={value}
          columns={numericHints.some((hint) => key.includes(hint)) ? numericColumns : columns}
          optional={optional}
          onChange={(nextValue) => updateParams(key, nextValue)}
          activeLang={activeLang}
          t={t}
        />
      );
    }

    return (
      <Field key={key} label={label}>
        <input
          type="text"
          value={value || ""}
          onChange={(event) => updateParams(key, event.target.value)}
        />
      </Field>
    );
  };

  return (
    <section className="daw-card daw-section-card">
      <div className="daw-section-heading">
        <span>{t.report}</span>
        <h3>{t.reportTitle}</h3>
        <p>{t.reportSubtitle}</p>
      </div>

      {!dataset ? (
        <EmptyState title={t.noDataset}>{t.noDatasetHint}</EmptyState>
      ) : (
        <>
          <div className="daw-group-grid" aria-label={t.reportGroup}>
            {Object.keys(analysisGroups).map((key) => (
              <button
                key={key}
                type="button"
                className={analysisDomain === key ? "active" : ""}
                onClick={() => setDomain(key)}
              >
                <strong>{groups[key]?.label || key}</strong>
                <span>{groups[key]?.description}</span>
              </button>
            ))}
          </div>

          <div className="daw-form-grid">
            <Field label={t.reportType} wide>
              <select value={analysisMethod} onChange={(event) => setMethod(event.target.value)}>
                {methods.map((method) => (
                  <option key={method.id} value={method.id}>
                    {methodLabel(method, activeLang)}
                  </option>
                ))}
              </select>
            </Field>

            {Object.keys(activeMethod.template).map((key) =>
              renderParamControl([key, getParamValue(key)])
            )}
          </div>

          <section className="daw-report-customize">
            <div className="daw-section-heading compact">
              <span>{t.optional}</span>
              <h4>{t.customizeReport}</h4>
              <p>{t.customizeReportHint}</p>
            </div>

            <Field label={t.reportDisplayTitle} wide>
              <input
                type="text"
                value={reportOptions.title}
                placeholder={methodLabel(activeMethod, activeLang)}
                onChange={(event) => updateReportOptions("title", event.target.value)}
              />
            </Field>

            <div className="daw-report-options-grid">
              <Toggle
                checked={reportOptions.includeSummary}
                onChange={(value) => updateReportOptions("includeSummary", value)}
              >
                {t.includeSummary}
              </Toggle>
              <Toggle
                checked={reportOptions.includeKpis}
                onChange={(value) => updateReportOptions("includeKpis", value)}
              >
                {t.includeKpis}
              </Toggle>
              <Toggle
                checked={reportOptions.includeInsights}
                onChange={(value) => updateReportOptions("includeInsights", value)}
              >
                {t.includeInsights}
              </Toggle>
              <Toggle
                checked={reportOptions.includeTables}
                onChange={(value) => updateReportOptions("includeTables", value)}
              >
                {t.includeTables}
              </Toggle>
              <Toggle
                checked={reportOptions.includeCharts}
                onChange={(value) => updateReportOptions("includeCharts", value)}
              >
                {t.includeCharts}
              </Toggle>
              <Toggle
                checked={reportOptions.includeWarnings}
                onChange={(value) => updateReportOptions("includeWarnings", value)}
              >
                {t.includeWarnings}
              </Toggle>
            </div>
          </section>

          <div className="daw-report-submit-row">
            <div>
              <strong>{t.readyToGenerate}</strong>
              <span>{t.generateReportHint}</span>
            </div>
            <button
              type="button"
              className="daw-primary"
              disabled={isLoading || !dataset}
              onClick={runAnalysis}
            >
              {isLoading ? t.working : t.runReport}
            </button>
          </div>
        </>
      )}
    </section>
  );
}

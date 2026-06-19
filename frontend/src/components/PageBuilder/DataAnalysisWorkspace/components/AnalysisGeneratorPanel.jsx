import Field from "./Field";
import ColumnSelect from "./ColumnSelect";
import MultiColumnSelect from "./MultiColumnSelect";
import { analysisGroups, reportGroupText } from "../constants/analysisConfig";
import { toLabel } from "../utils/formatters";

const isOptionalField = (key) =>
  key.includes("group") ||
  key.includes("category") ||
  key.includes("expense_column") ||
  key.includes("transaction_id") ||
  key.includes("numerator") ||
  key.includes("denominator") ||
  key === "rows" ||
  key === "max_rating" ||
  key === "separator";

const needsNumericColumns = (key) =>
  [
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
    "salary",
    "payroll",
    "attended",
    "working_days",
    "numerator",
    "denominator",
    "rating",
  ].some((hint) => key.includes(hint));

export default function AnalysisGeneratorPanel({
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
  generatedCount,
  t,
}) {
  const groups = reportGroupText[activeLang] || reportGroupText.en;

  const renderField = (key, defaultValue) => {
    const value = Object.prototype.hasOwnProperty.call(params || {}, key)
      ? params[key]
      : defaultValue;
    const label = toLabel(key, activeLang);

    if (Array.isArray(defaultValue)) {
      return (
        <MultiColumnSelect
          key={key}
          label={label}
          value={Array.isArray(value) ? value : []}
          columns={needsNumericColumns(key) ? numericColumns : columns}
          onChange={(nextValue) => updateParams(key, nextValue)}
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
            {["sum", "mean", "median", "min", "max", "count", "rate", "ratio", "percentage", "difference"].map((item) => (
              <option key={item} value={item}>{toLabel(item, activeLang)}</option>
            ))}
          </select>
        </Field>
      );
    }

    if (key === "question") {
      return (
        <Field key={key} label={label} wide>
          <textarea value={value || ""} rows="3" onChange={(event) => updateParams(key, event.target.value)} />
        </Field>
      );
    }

    if (key.endsWith("_column") || key === "column") {
      return (
        <ColumnSelect
          key={key}
          label={label}
          value={value || ""}
          columns={needsNumericColumns(key) ? numericColumns : columns}
          optional={isOptionalField(key)}
          onChange={(nextValue) => updateParams(key, nextValue)}
          t={t}
        />
      );
    }

    return (
      <Field key={key} label={label}>
        <input value={value || ""} onChange={(event) => updateParams(key, event.target.value)} />
      </Field>
    );
  };

  return (
    <section className="daw-analysis-generator">
      <div className="daw-analysis-generator-heading">
        <div>
          <strong>Create report calculations</strong>
          <span>Choose the kind of report, then tell us which columns contain the needed information.</span>
        </div>
        {generatedCount ? <em>{generatedCount} outputs ready</em> : null}
      </div>

      <div className="daw-analysis-domain-grid">
        {Object.keys(analysisGroups).map((domain) => (
          <button
            key={domain}
            type="button"
            className={analysisDomain === domain ? "active" : ""}
            onClick={() => setDomain(domain)}
          >
            <strong>{groups[domain]?.label || domain}</strong>
            <span>{groups[domain]?.description}</span>
          </button>
        ))}
      </div>

      <div className="daw-form-grid">
        <Field label="What would you like to calculate?" wide>
          <select value={analysisMethod} onChange={(event) => setMethod(event.target.value)}>
            {methods.map((method) => (
              <option key={method.id} value={method.id}>{method.label}</option>
            ))}
          </select>
        </Field>
        {Object.entries(activeMethod?.template || {}).map(([key, value]) => renderField(key, value))}
      </div>

      <div className="daw-analysis-generator-action">
        <span>The new numbers and tables will be added to your report choices. You can run more than one calculation.</span>
        <button type="button" className="daw-primary" onClick={runAnalysis} disabled={isLoading}>
          {isLoading ? t.working : "Create this calculation"}
        </button>
      </div>
    </section>
  );
}

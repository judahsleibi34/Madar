import Field from "./Field";
import ColumnSelect from "./ColumnSelect";
import MultiColumnSelect from "./MultiColumnSelect";
import { analysisGroups, reportGroupText } from "../constants/analysisConfig";
import { columnLabel, toLabel, valueDir } from "../utils/formatters";

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

export default function AnalysisGeneratorPanel({
  activeLang,
  analysisDomain,
  methods,
  analysisMethod,
  setMethod,
  activeMethod,
  params,
  updateParams,
  columns,
  numericColumns = [],
  runAnalysis,
  isLoading,
  generatedCount,
  t,
}) {
  const groups = reportGroupText[activeLang] || reportGroupText.en;
  const availableNumericColumns = numericColumns;
  const activeTemplate = activeMethod?.template || {};
  const allRecipes = Object.entries(analysisGroups).flatMap(([domain, group]) =>
    group.methods.map((method) => ({
      ...method,
      domain,
      domainLabel: groups[domain]?.label || domain,
    }))
  );
  const currentRecipe = allRecipes.find(
    (recipe) => recipe.domain === analysisDomain && recipe.id === analysisMethod
  );
  const measurableRecipe =
    allRecipes.find((recipe) => recipe.id === "numeric_question_summary") ||
    allRecipes.find((recipe) => Array.isArray(recipe.template?.numeric_columns));
  const selectedColumnCount = Object.values(params || {}).reduce((count, value) => {
    if (Array.isArray(value)) return count + value.length;
    return value ? count + 1 : count;
  }, 0);

  const chooseRecipe = (domain, methodId) => {
    if (domain !== analysisDomain) {
      setMethod(methodId, domain);
      return;
    }

    setMethod(methodId);
  };

  const measureAllVariables = () => {
    if (!measurableRecipe) return;
    chooseRecipe(measurableRecipe.domain, measurableRecipe.id);
    updateParams("numeric_columns", availableNumericColumns);
  };

  const assignColumnToActiveRecipe = (column) => {
    const entries = Object.entries(activeTemplate);
    const multiField = entries.find(([, defaultValue]) => Array.isArray(defaultValue));

    if (multiField) {
      const [key] = multiField;
      const selected = Array.isArray(params?.[key]) ? params[key] : [];
      updateParams(
        key,
        selected.includes(column)
          ? selected.filter((item) => item !== column)
          : [...selected, column]
      );
      return;
    }

    const emptyColumnField = entries.find(([key, defaultValue]) => {
      if (!(key.endsWith("_column") || key === "column")) return false;
      const value = Object.prototype.hasOwnProperty.call(params || {}, key)
        ? params[key]
        : defaultValue;
      return !value || isOptionalField(key);
    });

    if (emptyColumnField) {
      updateParams(emptyColumnField[0], column);
    }
  };

  const isColumnSelected = (column) =>
    Object.values(params || {}).some((value) =>
      Array.isArray(value) ? value.includes(column) : value === column
    );

  const getColumnsForField = (key) => {
    if (
      key.includes("numeric") ||
      key.includes("value") ||
      key.includes("amount") ||
      key.includes("cost") ||
      key.includes("revenue") ||
      key.includes("price") ||
      key.includes("quantity") ||
      key.includes("budget") ||
      key.includes("actual") ||
      key.includes("target") ||
      key.includes("baseline") ||
      key.includes("endline") ||
      key.includes("completed") ||
      key.includes("planned") ||
      key === "columns"
    ) {
      return availableNumericColumns;
    }

    return columns;
  };

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
          columns={getColumnsForField(key)}
          activeLang={activeLang}
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
          columns={getColumnsForField(key)}
          optional={isOptionalField(key)}
          onChange={(nextValue) => updateParams(key, nextValue)}
          activeLang={activeLang}
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
          <strong>Build measurable variables</strong>
          <span>Choose a calculation, then map the dataset fields it should measure.</span>
        </div>
        <div className="daw-analysis-generator-badges">
          <em>{selectedColumnCount} mapped</em>
          {generatedCount ? <em>{generatedCount} ready</em> : null}
        </div>
      </div>

      <div className="daw-variable-builder">
        <aside className="daw-variable-recipes" aria-label="Variable recipes">
          <div className="daw-variable-panel-heading">
            <strong>Calculation</strong>
            <span>{currentRecipe?.domainLabel || groups[analysisDomain]?.label}</span>
          </div>
          <button
            type="button"
            className="daw-variable-auto"
            onClick={measureAllVariables}
            disabled={!availableNumericColumns.length || !measurableRecipe}
          >
            <strong>Measure all numeric variables</strong>
            <span>{availableNumericColumns.length} measurable columns detected</span>
          </button>
          <div className="daw-variable-recipe-list">
            {allRecipes.map((recipe) => (
              <button
                key={`${recipe.domain}_${recipe.id}`}
                type="button"
                className={recipe.domain === analysisDomain && recipe.id === analysisMethod ? "active" : ""}
                onClick={() => chooseRecipe(recipe.domain, recipe.id)}
              >
                <strong>{recipe.label}</strong>
                <span>{recipe.domainLabel}</span>
              </button>
            ))}
          </div>
        </aside>

        <div className="daw-variable-workspace">
          <div className="daw-variable-panel-heading">
            <strong>Available variables</strong>
            <span>{columns.length ? `${columns.length} columns in this dataset` : t.loadDataToChooseColumns}</span>
          </div>
          <div className="daw-variable-column-grid">
            {columns.length ? (
              columns.map((column) => (
                <button
                  key={column}
                  type="button"
                  className={isColumnSelected(column) ? "selected" : ""}
                  title={column}
                  dir={activeLang === "ar" ? "rtl" : valueDir(column)}
                  onClick={() => assignColumnToActiveRecipe(column)}
                >
                  {columnLabel(column, activeLang)}
                </button>
              ))
            ) : (
              <em>{t.loadDataToChooseColumns}</em>
            )}
          </div>
        </div>
      </div>

      <div className="daw-form-grid">
        <Field label="Selected calculation" wide>
          <select value={analysisMethod} onChange={(event) => setMethod(event.target.value)}>
            {methods.map((method) => (
              <option key={method.id} value={method.id}>{method.label}</option>
            ))}
          </select>
        </Field>
        {Object.entries(activeMethod?.template || {}).map(([key, value]) => renderField(key, value))}
      </div>

      <div className="daw-analysis-generator-action">
        <span>Created variables appear in the report builder library and source picker.</span>
        <button type="button" className="daw-primary" onClick={runAnalysis} disabled={isLoading}>
          {isLoading ? t.working : "Create variables"}
        </button>
      </div>
    </section>
  );
}

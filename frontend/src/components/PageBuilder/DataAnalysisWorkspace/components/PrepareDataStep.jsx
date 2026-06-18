import EmptyState from './EmptyState';
import Field from './Field';
import Toggle from './Toggle';
import ColumnSelect from './ColumnSelect';
import MultiColumnSelect from './MultiColumnSelect';

export default function PrepareDataStep({
  dataset,
  columns,
  textColumns,
  cleaning,
  updateCleaning,
  t,
}) {
  const labellingHelp =
    cleaning.encodeMethod === "label"
      ? t.labelEncodingHint ||
        "Best when one answer should become one code. Example: Red, Blue, Green become 1, 2, 3."
      : t.oneHotEncodingHint ||
        "Best for answer choices. Example: Red creates a Red yes/no column, Blue creates a Blue yes/no column.";

  return (
    <section className="daw-card daw-section-card">
      <div className="daw-section-heading">
        <span>{t.prepare}</span>
        <h3>{t.prepareTitle}</h3>
        <p>{t.prepareSubtitle}</p>
      </div>

      {!dataset ? (
        <EmptyState title={t.noDataset}>{t.noDatasetHint}</EmptyState>
      ) : (
        <div className="daw-cleaning-stack">
          <div className="daw-cleaning-intro">
            <strong>{t.cleaningIntroTitle || "Start with the safe fixes"}</strong>
            <p>
              {t.cleaningIntroText ||
                "These changes help tidy the data without changing its meaning. You can leave everything as-is and continue."}
            </p>
          </div>

          <details open>
            <summary>
              <span>{t.basicCleaning}</span>
            </summary>

            <div className="daw-cleaning-grid">
              <div className="daw-cleaning-option">
                <Toggle
                  checked={cleaning.trimText}
                  onChange={(value) => updateCleaning("trimText", value)}
                >
                  {t.trimText}
                </Toggle>
                <p>{t.trimTextHint || "Fix extra spaces before and after answers."}</p>
              </div>

              <div className="daw-cleaning-option">
                <Toggle
                  checked={cleaning.lowercaseText}
                  onChange={(value) => updateCleaning("lowercaseText", value)}
                >
                  {t.lowercaseText}
                </Toggle>
                <p>{t.lowercaseTextHint || "Make text answers easier to group together."}</p>
              </div>

              <div className="daw-cleaning-option">
                <Toggle
                  checked={cleaning.removeDuplicates}
                  onChange={(value) => updateCleaning("removeDuplicates", value)}
                >
                  {t.removeDuplicates}
                </Toggle>
                <p>{t.removeDuplicatesHint || "Remove repeated rows from the dataset."}</p>
              </div>

              <div className="daw-cleaning-option">
                <Toggle
                  checked={cleaning.removeMissingRows}
                  onChange={(value) => updateCleaning("removeMissingRows", value)}
                >
                  {t.removeMissingRows}
                </Toggle>
                <p>{t.removeMissingRowsHint || "Use only when blank rows should not be included."}</p>
              </div>
            </div>
          </details>

          <details>
            <summary>
              <span>{t.advancedCleaning}</span>
            </summary>

            <div className="daw-advanced-cleaning-grid">
              <section className="daw-cleaning-tool">
                <strong>{t.fillMissing}</strong>
                <p>{t.fillMissingHint || "Choose one column and decide what should replace empty cells."}</p>

                <div className="daw-form-grid">
                  <ColumnSelect
                    label={t.fillColumn}
                    value={cleaning.fillColumn}
                    columns={columns}
                    onChange={(value) => {
                      updateCleaning("fillColumn", value);
                      updateCleaning("fillMissing", Boolean(value));
                    }}
                    t={t}
                  />

                  {cleaning.fillColumn ? (
                    <>
                      <Field label={t.fillWith}>
                        <select
                          value={cleaning.fillMethod}
                          onChange={(event) => updateCleaning("fillMethod", event.target.value)}
                        >
                          <option value="mode">{t.mostCommonValue}</option>
                          <option value="mean">{t.average}</option>
                          <option value="median">{t.median}</option>
                          <option value="forward_fill">{t.previousValue}</option>
                          <option value="backward_fill">{t.nextValue}</option>
                          <option value="constant">{t.customValue}</option>
                        </select>
                      </Field>

                      {cleaning.fillMethod === "constant" ? (
                        <Field label={t.customValue}>
                          <input
                            type="text"
                            value={cleaning.fillValue}
                            onChange={(event) => updateCleaning("fillValue", event.target.value)}
                          />
                        </Field>
                      ) : null}
                    </>
                  ) : null}
                </div>
              </section>

              <section className="daw-cleaning-tool">
                <strong>{t.changeColumnType || "Fix a column type"}</strong>
                <p>{t.changeColumnTypeHint || "Use this if a number, date, or yes/no field was detected incorrectly."}</p>

                <div className="daw-form-grid">
                  <ColumnSelect
                    label={t.convertColumn}
                    value={cleaning.convertColumn}
                    columns={columns}
                    optional
                    onChange={(value) => updateCleaning("convertColumn", value)}
                    t={t}
                  />

                  {cleaning.convertColumn ? (
                    <Field label={t.convertTo}>
                      <select
                        value={cleaning.convertType}
                        onChange={(event) => updateCleaning("convertType", event.target.value)}
                      >
                        <option value="numeric">{t.number}</option>
                        <option value="datetime">{t.date}</option>
                        <option value="string">{t.text}</option>
                        <option value="category">{t.category}</option>
                        <option value="boolean">{t.yesNo}</option>
                      </select>
                    </Field>
                  ) : null}
                </div>
              </section>

              <section className="daw-cleaning-tool">
                <strong>{t.renameColumn}</strong>
                <p>{t.renameColumnHint || "Give a column a clearer name for the report."}</p>

                <div className="daw-form-grid">
                  <ColumnSelect
                    label={t.renameColumn}
                    value={cleaning.renameColumn}
                    columns={columns}
                    optional
                    onChange={(value) => updateCleaning("renameColumn", value)}
                    t={t}
                  />

                  {cleaning.renameColumn ? (
                    <Field label={t.newName}>
                      <input
                        type="text"
                        value={cleaning.renameTo}
                        onChange={(event) => updateCleaning("renameTo", event.target.value)}
                      />
                    </Field>
                  ) : null}
                </div>
              </section>

              <section className="daw-cleaning-tool daw-cleaning-tool-wide">
                <strong>{t.excludeColumns}</strong>
                <p>{t.excludeColumnsHint || "Remove columns you do not want to use in the cleaned data."}</p>

                <MultiColumnSelect
                  label={t.excludeColumns}
                  value={cleaning.dropColumns}
                  columns={columns}
                  hideLabel
                  onChange={(value) => {
                    updateCleaning("dropColumns", value);
                    updateCleaning("dropColumnsConfirmed", false);
                  }}
                  t={t}
                />

                {cleaning.dropColumns?.length ? (
                  <div className="daw-cleaning-confirm">
                    <button
                      type="button"
                      className={`daw-confirm-button ${
                        cleaning.dropColumnsConfirmed ? "is-confirmed" : ""
                      }`}
                      onClick={() => updateCleaning("dropColumnsConfirmed", true)}
                    >
                      {cleaning.dropColumnsConfirmed
                        ? t.dropColumnsConfirmed || "Columns will be removed"
                        : t.confirmDropColumns || "Remove selected columns"}
                    </button>
                    <p>
                      {t.confirmDropColumnsHint ||
                        "This only changes the cleaned copy used for analysis. Your original upload stays the same."}
                    </p>
                  </div>
                ) : null}
              </section>

              <section className="daw-cleaning-tool daw-cleaning-tool-wide">
                <strong>{t.labellingCard || "Make answers usable in charts"}</strong>
                <p>{t.labellingCardHint || "Use this when text answers need to become number fields."}</p>

                <div className="daw-form-grid">
                  <Field label={t.encodingMethod || "Choose how labels are created"}>
                    <select
                      value={cleaning.encodeMethod}
                      onChange={(event) => updateCleaning("encodeMethod", event.target.value)}
                    >
                      <option value="one_hot">{t.oneHotEncoding || "Create a yes/no column for each answer"}</option>
                      <option value="label">{t.labelEncoding || "Create one number column"}</option>
                    </select>
                  </Field>

                  <Toggle
                    checked={cleaning.keepEncodedOriginals}
                    onChange={(value) => updateCleaning("keepEncodedOriginals", value)}
                  >
                    {t.keepOriginalColumns || "Keep the original text columns too"}
                  </Toggle>
                </div>
                <p className="daw-cleaning-note">{labellingHelp}</p>

                <MultiColumnSelect
                  label={t.columnsToEncode || "Choose answer columns"}
                  value={cleaning.encodeColumns}
                  columns={textColumns?.length ? textColumns : columns}
                  hideLabel
                  onChange={(value) => updateCleaning("encodeColumns", value)}
                  t={t}
                />
              </section>
            </div>
          </details>
        </div>
      )}
    </section>
  );
}

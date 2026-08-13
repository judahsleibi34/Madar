import { Download } from 'lucide-react';
import EmptyState from './EmptyState';
import Field from './Field';
import Toggle from './Toggle';
import ColumnSelect from './ColumnSelect';
import MultiColumnSelect from './MultiColumnSelect';

export default function PrepareDataStep({
  dataset,
  columns,
  cleaning,
  updateCleaning,
  onSaveDataframes,
  onDownloadDataframe,
  dataframesSaved = false,
  canDownloadDataframes = false,
  isSavingDataframes = false,
  t,
}) {
  const labellingHelp =
    cleaning.encodeMethod === "label"
      ? t.labelEncodingHint ||
        "Use this when each row has one choice, like Status, Department, Priority, or Rating."
      : t.oneHotEncodingHint ||
        "Use this when one answer can include several choices, like Needed services = Website; Forms; Reports.";

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
          <details open>
            <summary>
              <span>{t.basicCleaning}</span>
            </summary>

            <div className="daw-cleaning-grid">
              <div className="daw-cleaning-option">
                <Toggle
                  checked={cleaning.trimText}
                  onChange={(value) => updateCleaning("trimText", value)}
                  description={t.trimTextHint || "Fix extra spaces before and after answers."}
                >
                  {t.trimText}
                </Toggle>
              </div>

              <div className="daw-cleaning-option">
                <Toggle
                  checked={cleaning.lowercaseText}
                  onChange={(value) => updateCleaning("lowercaseText", value)}
                  description={t.lowercaseTextHint || "Make text answers easier to group together."}
                >
                  {t.lowercaseText}
                </Toggle>
              </div>

              <div className="daw-cleaning-option">
                <Toggle
                  checked={cleaning.removeDuplicates}
                  onChange={(value) => updateCleaning("removeDuplicates", value)}
                  description={t.removeDuplicatesHint || "Remove repeated rows from the dataset."}
                >
                  {t.removeDuplicates}
                </Toggle>
              </div>

              <div className="daw-cleaning-option">
                <Toggle
                  checked={cleaning.removeMissingRows}
                  onChange={(value) => updateCleaning("removeMissingRows", value)}
                  description={t.removeMissingRowsHint || "Use only when blank rows should not be included."}
                >
                  {t.removeMissingRows}
                </Toggle>
              </div>
            </div>
          </details>

          <details open>
            <summary>
              <span>{t.advancedCleaning}</span>
            </summary>

            <div className="daw-advanced-cleaning-grid">
              <details className="daw-cleaning-tool" open={Boolean(cleaning.fillColumn)}>
                <summary>
                  <div>
                    <strong>{t.fillMissing}</strong>
                    <p>{t.fillMissingHint || "Choose one column and decide what should replace empty cells."}</p>
                  </div>
                </summary>

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
                          <option value="mean">{t.fillAverage}</option>
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
              </details>

              <details className="daw-cleaning-tool" open={Boolean(cleaning.convertColumn)}>
                <summary>
                  <div>
                    <strong>{t.changeColumnType || "Fix a column type"}</strong>
                    <p>{t.changeColumnTypeHint || "Use this if a number, date, or yes/no field was detected incorrectly."}</p>
                  </div>
                </summary>

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
              </details>

              <details className="daw-cleaning-tool" open={Boolean(cleaning.renameColumn)}>
                <summary>
                  <div>
                    <strong>{t.renameColumn}</strong>
                    <p>{t.renameColumnHint || "Give a column a clearer name for the report."}</p>
                  </div>
                </summary>

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
              </details>

              <details className="daw-cleaning-tool daw-cleaning-tool-wide" open={Boolean(cleaning.dropColumns?.length)}>
                <summary>
                  <div>
                    <strong>{t.excludeColumns}</strong>
                    <p>{t.excludeColumnsHint || "Remove columns you do not want to use in the cleaned data."}</p>
                  </div>
                </summary>

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
                    <div className="daw-cleaning-confirm-copy">
                      <strong>
                        {cleaning.dropColumns.length} selected column{cleaning.dropColumns.length === 1 ? "" : "s"}
                      </strong>
                      <p>
                        {t.confirmDropColumnsHint ||
                          "This only changes the cleaned copy used for analysis. Your original upload stays the same."}
                      </p>
                    </div>
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
                  </div>
                ) : null}
              </details>

              <details className="daw-cleaning-tool daw-cleaning-tool-wide" open={Boolean(cleaning.encodeColumns?.length)}>
                <summary>
                  <div>
                    <strong>{t.labellingCard || "Encode a column for reports"}</strong>
                    <p>
                      {t.labellingCardHint ||
                        "Choose the dataframe column and the encoding type to use in reports."}
                    </p>
                  </div>
                </summary>

                <div className="daw-form-grid">
                  <ColumnSelect
                    label={t.columnsToEncode || "Column"}
                    value={cleaning.encodeColumns?.[0] || ""}
                    columns={columns}
                    onChange={(value) => updateCleaning("encodeColumns", value ? [value] : [])}
                    t={t}
                  />

                  <Field label={t.encodingMethod || "Encoding type"}>
                    <select
                      value={cleaning.encodeMethod}
                      onChange={(event) => updateCleaning("encodeMethod", event.target.value)}
                    >
                      <option value="one_hot">{t.oneHotEncoding || "One-hot encoding"}</option>
                      <option value="label">{t.labelEncoding || "Label encoding"}</option>
                    </select>
                  </Field>
                </div>
                <p className="daw-cleaning-note">{labellingHelp}</p>
              </details>
            </div>
          </details>

          <div className="daw-save-dataframe-row">
            <div>
              <strong>{t.saveDataframesTitle || "Save dataframes"}</strong>
              <span>
                {t.saveDataframesHint ||
                  "Save both the original and cleaned dataframe."}
              </span>
            </div>
            <button
              type="button"
              className={`daw-primary daw-save-dataframe-button ${
                dataframesSaved ? "is-saved" : ""
              }`}
              data-action="save-dataframes"
              onClick={onSaveDataframes}
              disabled={isSavingDataframes}
            >
              {isSavingDataframes
                ? t.working
                : dataframesSaved
                ? t.dataframesSaved || "Dataframes saved"
                : t.saveDataframes || "Save dataframes"}
            </button>
          </div>

          {dataframesSaved ? (
            <div className="daw-generate-metrics-row is-ready">
              <div>
                <strong>{t.dataframesSaved || "Dataframes saved"}</strong>
                <span>{t.dataframesSavedHint || "Charts and Report are ready to use this saved data."}</span>
              </div>
              <div className="daw-dataframe-download-actions" aria-label={t.downloadDataframes || "Download saved dataset"}>
                <button
                  type="button"
                  className="daw-secondary"
                  onClick={() => onDownloadDataframe?.("csv")}
                  disabled={!canDownloadDataframes}
                  title={t.downloadCsv || "Download CSV"}
                >
                  <Download size={16} />
                  <span>{t.csv || "CSV"}</span>
                </button>
                <button
                  type="button"
                  className="daw-secondary"
                  onClick={() => onDownloadDataframe?.("xlsx")}
                  disabled={!canDownloadDataframes}
                  title={t.downloadXlsx || "Download XLSX"}
                >
                  <Download size={16} />
                  <span>{t.xlsx || "XLSX"}</span>
                </button>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}

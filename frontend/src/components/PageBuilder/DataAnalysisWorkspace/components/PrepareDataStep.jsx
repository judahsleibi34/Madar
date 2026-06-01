import EmptyState from './EmptyState';
import Field from './Field';
import Toggle from './Toggle';
import ColumnSelect from './ColumnSelect';
import MultiColumnSelect from './MultiColumnSelect';

export default function PrepareDataStep({
  dataset,
  columns,
  numericColumns,
  cleaning,
  updateCleaning,
  t,
}) {
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
            <summary>{t.basicCleaning}</summary>

            <div className="daw-cleaning-grid">
              <Toggle
                checked={cleaning.trimText}
                onChange={(value) => updateCleaning("trimText", value)}
              >
                {t.trimText}
              </Toggle>

              <Toggle
                checked={cleaning.lowercaseText}
                onChange={(value) => updateCleaning("lowercaseText", value)}
              >
                {t.lowercaseText}
              </Toggle>

              <Toggle
                checked={cleaning.removeDuplicates}
                onChange={(value) => updateCleaning("removeDuplicates", value)}
              >
                {t.removeDuplicates}
              </Toggle>

              <Toggle
                checked={cleaning.removeMissingRows}
                onChange={(value) => updateCleaning("removeMissingRows", value)}
              >
                {t.removeMissingRows}
              </Toggle>
            </div>
          </details>

          <details>
            <summary>{t.advancedCleaning}</summary>

            <div className="daw-form-grid">
              <Toggle
                checked={cleaning.fillMissing}
                onChange={(value) => updateCleaning("fillMissing", value)}
              >
                {t.fillMissing}
              </Toggle>

              <ColumnSelect
                label={t.fillColumn}
                value={cleaning.fillColumn}
                columns={columns}
                onChange={(value) => updateCleaning("fillColumn", value)}
                t={t}
              />

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

              <ColumnSelect
                label={t.convertColumn}
                value={cleaning.convertColumn}
                columns={columns}
                optional
                onChange={(value) => updateCleaning("convertColumn", value)}
                t={t}
              />

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

              <ColumnSelect
                label={t.renameColumn}
                value={cleaning.renameColumn}
                columns={columns}
                optional
                onChange={(value) => updateCleaning("renameColumn", value)}
                t={t}
              />

              <Field label={t.newName}>
                <input
                  type="text"
                  value={cleaning.renameTo}
                  onChange={(event) => updateCleaning("renameTo", event.target.value)}
                />
              </Field>

              <MultiColumnSelect
                label={t.removeOutliersFrom}
                value={cleaning.outlierColumns}
                columns={numericColumns}
                onChange={(value) => {
                  updateCleaning("outlierColumns", value);
                  updateCleaning("removeOutliers", value.length > 0);
                }}
                t={t}
              />

              <MultiColumnSelect
                label={t.excludeColumns}
                value={cleaning.dropColumns}
                columns={columns}
                onChange={(value) => updateCleaning("dropColumns", value)}
                t={t}
              />
            </div>
          </details>
        </div>
      )}
    </section>
  );
}

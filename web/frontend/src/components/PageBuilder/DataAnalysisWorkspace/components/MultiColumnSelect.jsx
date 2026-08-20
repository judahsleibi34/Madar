import { columnLabel, valueDir } from '../utils/formatters';

export default function MultiColumnSelect({ label, value, columns, onChange, activeLang, t, hideLabel = false }) {
  const selected = Array.isArray(value) ? value : [];

  const toggleColumn = (column) => {
    onChange(
      selected.includes(column)
        ? selected.filter((item) => item !== column)
        : [...selected, column]
    );
  };

  return (
    <div className="daw-field wide">
      {hideLabel ? null : <span>{label}</span>}

      <div className="daw-column-picker">
        {columns.length ? (
          columns.map((column) => (
            <label key={column} title={column}>
              <input
                type="checkbox"
                checked={selected.includes(column)}
                onChange={() => toggleColumn(column)}
              />
              <span dir={activeLang === "ar" ? "rtl" : valueDir(column)}>
                {columnLabel(column, activeLang)}
              </span>
            </label>
          ))
        ) : (
          <em>{t.loadDataToChooseColumns}</em>
        )}
      </div>
      {selected.length ? (
        <small>
          {t.selectedColumns}:{" "}
          {selected
            .map((column) => columnLabel(column, activeLang))
            .join(activeLang === "ar" ? "، " : ", ")}
        </small>
      ) : null}
    </div>
  );
}

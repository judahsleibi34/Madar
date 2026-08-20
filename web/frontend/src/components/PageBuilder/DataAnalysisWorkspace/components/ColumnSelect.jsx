import Field from './Field';
import { columnLabel, valueDir } from '../utils/formatters';

export default function ColumnSelect({ label, value, columns, optional, onChange, activeLang, t }) {
  return (
    <Field label={label}>
      <select
        value={value || ""}
        dir={activeLang === "ar" ? "rtl" : "ltr"}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">{optional ? t.noGrouping : t.selectColumn}</option>

        {columns.map((column) => (
          <option key={column} value={column}>
            {columnLabel(column, activeLang)}
          </option>
        ))}
      </select>
      {value ? (
        <small dir={activeLang === "ar" ? "rtl" : valueDir(value)}>
          {t.selectedColumn}: {columnLabel(value, activeLang)}
        </small>
      ) : null}
    </Field>
  );
}

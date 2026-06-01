import DataPreviewGrid from './DataPreviewGrid';
import { displayValue, valueDir } from '../utils/formatters';

export default function ReportTable({ table, t, variant = "preview" }) {
  const rows = Array.isArray(table?.rows)
    ? table.rows
    : Array.isArray(table?.data)
      ? table.data
      : Array.isArray(table)
        ? table
        : [];

  const title = table?.title || table?.name || t.tables;
  const columns = Array.from(new Set(rows.flatMap((row) => Object.keys(row || {}))));

  if (!rows.length || !columns.length) {
    return null;
  }

  if (variant === "compact") {
    return (
      <section className="daw-report-block daw-compact-report-block">
        <div className="daw-report-block-header">
          <h4>{title}</h4>
          <span>{t.itemCount ? t.itemCount(rows.length) : `${rows.length} item${rows.length === 1 ? "" : "s"}`}</span>
        </div>

        <div className="daw-compact-table-scroll">
          <table className="daw-compact-table">
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column} title={column} dir={valueDir(column)}>
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={`compact_${title}_${rowIndex}`}>
                  {columns.map((column) => {
                    const formatted = displayValue(row[column], t);

                    return (
                      <td key={column} title={formatted} dir={valueDir(row[column])}>
                        {formatted}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    );
  }

  return (
    <section className="daw-report-block">
      <h4>{title}</h4>
      <DataPreviewGrid columns={columns} rows={rows} t={t} />
    </section>
  );
}

import { useEffect, useMemo, useState } from 'react';
import DataPreviewGrid from './DataPreviewGrid';
import { displayValue, valueDir } from '../utils/formatters';

const COMPACT_PAGE_SIZE = 10;

export default function ReportTable({ table, t, variant = "preview" }) {
  const [compactPage, setCompactPage] = useState(1);
  const rows = Array.isArray(table?.rows)
    ? table.rows
    : Array.isArray(table?.data)
      ? table.data
      : Array.isArray(table)
        ? table
        : [];

  const title = table?.title || table?.name || t.tables;
  const columns = useMemo(
    () => Array.from(new Set(rows.flatMap((row) => Object.keys(row || {})))),
    [rows]
  );

  useEffect(() => {
    setCompactPage(1);
  }, [rows, title]);

  if (!rows.length || !columns.length) {
    return null;
  }

  if (variant === "compact") {
    const totalPages = Math.max(1, Math.ceil(rows.length / COMPACT_PAGE_SIZE));
    const safePage = Math.min(compactPage, totalPages);
    const startIndex = (safePage - 1) * COMPACT_PAGE_SIZE;
    const visibleRows = rows.slice(startIndex, startIndex + COMPACT_PAGE_SIZE);
    const startRow = startIndex + 1;
    const endRow = Math.min(startIndex + COMPACT_PAGE_SIZE, rows.length);
    const goToPage = (nextPage) => {
      setCompactPage(Math.min(Math.max(nextPage, 1), totalPages));
    };

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
              {visibleRows.map((row, rowIndex) => (
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

        {rows.length > COMPACT_PAGE_SIZE ? (
          <div className="daw-compact-pagination">
            <span>{t.showingRows(startRow, endRow, rows.length)}</span>

            <div>
              <button type="button" disabled={safePage === 1} onClick={() => goToPage(safePage - 1)}>
                {t.previous}
              </button>

              <span>{t.pageOf(safePage, totalPages)}</span>

              <button type="button" disabled={safePage === totalPages} onClick={() => goToPage(safePage + 1)}>
                {t.next}
              </button>
            </div>
          </div>
        ) : null}
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

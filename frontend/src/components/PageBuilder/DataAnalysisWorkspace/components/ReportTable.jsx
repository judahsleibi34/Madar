import { useEffect, useMemo, useState } from 'react';
import DataPreviewGrid from './DataPreviewGrid';
import { displayValue, valueDir } from '../utils/formatters';

const COMPACT_PAGE_SIZE = 10;

const COMPACT_DECIMAL_PLACES = 2;

const isFiniteNumber = (value) =>
  typeof value === "number" && Number.isFinite(value);

const deferEffectStateUpdate = (callback) => {
  let cancelled = false;
  queueMicrotask(() => {
    if (!cancelled) callback();
  });
  return () => {
    cancelled = true;
  };
};

const isNumericMetricColumn = (column, metricColumns = []) => {
  if (metricColumns.includes(column)) return true;

  const normalized = String(column || "").toLowerCase();

  return (
    normalized.includes("%") ||
    normalized.includes("average") ||
    normalized.includes("middle") ||
    normalized.includes("lowest") ||
    normalized.includes("highest") ||
    normalized.includes("total")
  );
};

const formatCompactValue = (value, column, t, metricColumns) => {
  if (!isNumericMetricColumn(column, metricColumns)) return displayValue(value, t);

  if (isFiniteNumber(value)) {
    return value.toFixed(COMPACT_DECIMAL_PLACES);
  }

  const text = displayValue(value, t);
  const numeric = Number(String(text).replace(/%$/, ""));

  if (!Number.isFinite(numeric)) return text;
  return String(text).endsWith("%")
    ? `${numeric.toFixed(COMPACT_DECIMAL_PLACES)}%`
    : numeric.toFixed(COMPACT_DECIMAL_PLACES);
};

const getCompactColumnKind = (column) => {
  const normalized = String(column || "").toLowerCase();

  if (
    normalized.includes("sample") ||
    normalized.includes("example") ||
    normalized.includes("most common")
  ) {
    return "sample";
  }

  if (
    normalized.includes("field") ||
    normalized.includes("column") ||
    normalized.includes("check")
  ) {
    return "label";
  }

  if (
    normalized.includes("%") ||
    normalized.includes("blank") ||
    normalized.includes("missing") ||
    normalized.includes("empty") ||
    normalized.includes("unique") ||
    normalized.includes("answer") ||
    normalized.includes("row") ||
    normalized.includes("total") ||
    normalized.includes("average") ||
    normalized.includes("middle") ||
    normalized.includes("lowest") ||
    normalized.includes("highest")
  ) {
    return "number";
  }

  return "text";
};

export default function ReportTable({ table, t, variant = "preview" }) {
  const [compactPage, setCompactPage] = useState(1);
  const rows = useMemo(
    () =>
      Array.isArray(table?.rows)
        ? table.rows
        : Array.isArray(table?.data)
          ? table.data
          : Array.isArray(table)
            ? table
            : [],
    [table]
  );

  const title = table?.title || table?.name || t.tables;
  const metricColumns = Array.isArray(table?.metricColumns)
    ? table.metricColumns
    : [];
  const columns = useMemo(
    () => Array.from(new Set(rows.flatMap((row) => Object.keys(row || {})))),
    [rows]
  );

  useEffect(() => {
    return deferEffectStateUpdate(() => {
      setCompactPage(1);
    });
  }, [rows, title]);

  if (!rows.length || !columns.length) {
    return null;
  }

  if (variant === "compact") {
    const isWideTable = columns.length > 6;
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
          <table className={`daw-compact-table ${isWideTable ? "daw-compact-table-wide" : ""}`}>
            <colgroup>
              {columns.map((column) => (
                <col
                  key={column}
                  className={`daw-compact-col-${getCompactColumnKind(column)}`}
                />
              ))}
            </colgroup>
            <thead>
              <tr>
                {columns.map((column) => (
                  <th
                    key={column}
                    className={`daw-compact-cell-${getCompactColumnKind(column)}`}
                    title={column}
                    dir={valueDir(column)}
                  >
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((row, rowIndex) => (
                <tr key={`compact_${title}_${rowIndex}`}>
                  {columns.map((column) => {
                    const formatted = formatCompactValue(row[column], column, t, metricColumns);

                    return (
                      <td
                        key={column}
                        className={`daw-compact-cell-${getCompactColumnKind(column)}`}
                        title={formatted}
                        dir={valueDir(row[column])}
                      >
                        <span>{formatted}</span>
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

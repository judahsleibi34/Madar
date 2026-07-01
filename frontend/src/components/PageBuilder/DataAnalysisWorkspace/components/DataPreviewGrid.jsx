import { useEffect, useMemo, useState } from 'react';
import EmptyState from './EmptyState';
import { displayValue, valueDir } from '../utils/formatters';

const deferEffectStateUpdate = (callback) => {
  let cancelled = false;
  queueMicrotask(() => {
    if (!cancelled) callback();
  });
  return () => {
    cancelled = true;
  };
};

export default function DataPreviewGrid({ columns = [], rows = [], t }) {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [visibleColumns, setVisibleColumns] = useState(columns.slice(0, 8));

  const pageSize = 10;

  useEffect(() => {
    return deferEffectStateUpdate(() => {
      setPage(1);
      setSearch("");
      setVisibleColumns(columns.slice(0, 8));
    });
  }, [columns]);

  const filteredRows = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return rows;

    return rows.filter((row) =>
      columns.some((column) =>
        String(row[column] ?? "").toLowerCase().includes(query)
      )
    );
  }, [rows, columns, search]);

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const startIndex = (safePage - 1) * pageSize;
  const visibleRows = filteredRows.slice(startIndex, startIndex + pageSize);
  const startRow = filteredRows.length ? startIndex + 1 : 0;
  const endRow = Math.min(startIndex + pageSize, filteredRows.length);

  const goToPage = (nextPage) => {
    setPage(Math.min(Math.max(nextPage, 1), totalPages));
  };

  if (!columns.length) {
    return <EmptyState title={t.noDataset}>{t.noDatasetHint}</EmptyState>;
  }

  return (
    <div className="daw-data-grid">
      <div className="daw-data-grid-toolbar">
        <input
          type="search"
          value={search}
          placeholder={t.searchRows}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
        />

        <details className="daw-column-menu">
          <summary>{t.columns}</summary>

          <div className="daw-column-menu-panel">
            <button
              type="button"
              onClick={() => setVisibleColumns(columns.slice(0, 8))}
            >
              {t.firstColumns || "First 8"}
            </button>

            <button type="button" onClick={() => setVisibleColumns(columns)}>
              {t.allColumns || "All"}
            </button>

            <div>
              {columns.map((column) => (
                <label key={column}>
                  <input
                    type="checkbox"
                    checked={visibleColumns.includes(column)}
                    onChange={() => {
                      setVisibleColumns((current) => {
                        if (current.includes(column)) {
                          if (current.length === 1) return current;
                          return current.filter((item) => item !== column);
                        }

                        return [...current, column];
                      });
                    }}
                  />
                  <span>{column}</span>
                </label>
              ))}
            </div>
          </div>
        </details>
      </div>

      <div className="daw-data-grid-meta">
        <span>{t.showingRows(startRow, endRow, filteredRows.length)}</span>
        <span>
          {visibleColumns.length} / {columns.length}
        </span>
      </div>

      <div className="daw-table-scroll">
        <table className="daw-table">
          <thead>
            <tr>
              {visibleColumns.map((column) => (
                <th key={column} title={column} dir={valueDir(column)}>
                  {column}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {visibleRows.length ? (
              visibleRows.map((row, rowIndex) => (
                <tr key={`row_${safePage}_${rowIndex}`}>
                  {visibleColumns.map((column) => {
                    const formatted = displayValue(row[column], t);

                    return (
                      <td key={column} title={formatted} dir={valueDir(row[column])}>
                        {formatted}
                      </td>
                    );
                  })}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={visibleColumns.length || 1}>
                  <EmptyState title={t.noRows}>{t.noRowsHint}</EmptyState>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="daw-pagination">
        <button type="button" disabled={safePage === 1} onClick={() => goToPage(1)}>
          {t.first}
        </button>

        <button
          type="button"
          disabled={safePage === 1}
          onClick={() => goToPage(safePage - 1)}
        >
          {t.previous}
        </button>

        <span>{t.pageOf(safePage, totalPages)}</span>

        <button
          type="button"
          disabled={safePage === totalPages}
          onClick={() => goToPage(safePage + 1)}
        >
          {t.next}
        </button>

        <button
          type="button"
          disabled={safePage === totalPages}
          onClick={() => goToPage(totalPages)}
        >
          {t.last}
        </button>
      </div>
    </div>
  );
}

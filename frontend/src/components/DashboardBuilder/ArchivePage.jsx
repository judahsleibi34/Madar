import { useEffect, useMemo, useState } from "react";
import {
  Archive,
  BarChart3,
  Database,
  Download,
  ExternalLink,
  FileText,
  RefreshCw,
  Trash2,
} from "lucide-react";

import {
  deleteArchiveItem,
  listArchiveItems,
} from "../PageBuilder/DataAnalysisWorkspace/utils/datasetStorage";

const FILTERS = [
  { id: "all", label: "All", icon: Archive },
  { id: "dataset", label: "Saved data", icon: Database },
  { id: "chart", label: "Plots", icon: BarChart3 },
  { id: "report", label: "Reports", icon: FileText },
];

const DATASET_TYPES = new Set(["dataset", "loaded_dataset", "cleaned_dataset"]);

function matchesFilter(item, filterId) {
  if (filterId === "all") return true;
  if (filterId === "dataset") return DATASET_TYPES.has(item.type);
  return item.type === filterId;
}

function getItemKindLabel(item, fallback = "Archived item") {
  if (item.type === "loaded_dataset") return "Loaded dataset";
  if (item.type === "cleaned_dataset" || item.type === "dataset") return "Cleaned dataset";
  if (item.type === "chart") return "Plot";
  if (item.type === "report") return "Report";
  return fallback;
}

function formatDate(value) {
  if (!value) return "Unknown date";

  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return "Unknown date";
  }
}

function getItemMeta(item) {
  if (DATASET_TYPES.has(item.type)) {
    const rows =
      item.payload?.cleanedDataframe?.rows ??
      item.payload?.loadedDataframe?.rows ??
      item.payload?.dataset?.rows;
    const columns =
      item.payload?.cleanedDataframe?.columns ||
      item.payload?.loadedDataframe?.columns ||
      item.payload?.dataset?.columns;

    return [
      rows ? `${rows.toLocaleString()} rows` : "",
      Array.isArray(columns) ? `${columns.length} columns` : "",
      item.payload?.cleanedDataframe ? "Cleaned dataframe" : "",
      item.payload?.loadedDataframe ? "Loaded dataframe" : "",
      item.payload?.sourceMode ? `Source: ${item.payload.sourceMode}` : "",
    ].filter(Boolean);
  }

  if (item.type === "chart") {
    return [
      item.payload?.chartType ? `Plot: ${item.payload.chartType}` : "Saved plot",
      item.payload?.datasetName || "",
    ].filter(Boolean);
  }

  if (item.type === "report") {
    const blocks = item.payload?.blocks;
    return [
      Array.isArray(blocks) ? `${blocks.length} blocks` : "Report draft",
      item.payload?.datasetName || "",
    ].filter(Boolean);
  }

  return [];
}

function exportJson(item) {
  const datasetCsv =
    item.payload?.cleanedDataframe?.csv || item.payload?.loadedDataframe?.csv;
  const isDatasetCsv = DATASET_TYPES.has(item.type) && datasetCsv;
  const contents = isDatasetCsv
    ? datasetCsv
    : JSON.stringify(item, null, 2);
  const blob = new Blob([contents], {
    type: isDatasetCsv ? "text/csv;charset=utf-8" : "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  const extension = isDatasetCsv ? "csv" : "json";
  const baseName = `${item.title || item.type || "archive-item"}`
    .replace(/[^\w.-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(new RegExp(`\\.${extension}$`, "i"), "");
  link.download = `${baseName}.${extension}`;
  link.click();
  URL.revokeObjectURL(url);
}

export default function ArchivePage({ user }) {
  const [items, setItems] = useState([]);
  const [activeFilter, setActiveFilter] = useState("all");
  const [status, setStatus] = useState("loading");

  const loadArchive = async () => {
    setStatus("loading");
    try {
      const archiveItems = await listArchiveItems({
        scope: user?.id ? `user-${user.id}` : "",
      });
      setItems(archiveItems);
      setStatus("ready");
    } catch {
      setStatus("error");
    }
  };

  useEffect(() => {
    loadArchive();
  }, [user?.id]);

  const filteredItems = useMemo(
    () =>
      items.filter((item) => matchesFilter(item, activeFilter)),
    [activeFilter, items]
  );

  const counts = useMemo(
    () =>
      FILTERS.reduce((summary, filter) => {
        summary[filter.id] =
          filter.id === "all"
            ? items.length
            : items.filter((item) => matchesFilter(item, filter.id)).length;
        return summary;
      }, {}),
    [items]
  );

  const removeItem = async (id) => {
    await deleteArchiveItem(id);
    setItems((current) => current.filter((item) => item.id !== id));
  };

  return (
    <section className="archive-page dashboard-page" aria-labelledby="archive-title">
      <header className="archive-header">
        <div>
          <span className="archive-kicker">Archive</span>
          <h1 id="archive-title">Saved work history</h1>
          <p>
            Keep old cleaned datasets, deleted charts, and report drafts so the
            next dataset does not erase useful previous work.
          </p>
        </div>

        <button type="button" className="archive-refresh-button" onClick={loadArchive}>
          <RefreshCw size={17} aria-hidden="true" />
          Refresh
        </button>
      </header>

      <div className="archive-summary-grid" aria-label="Archive summary">
        {FILTERS.slice(1).map((filter) => {
          const Icon = filter.icon;
          return (
            <article key={filter.id}>
              <span aria-hidden="true">
                <Icon size={19} />
              </span>
              <div>
                <strong>{counts[filter.id] || 0}</strong>
                <small>{filter.label}</small>
              </div>
            </article>
          );
        })}
      </div>

      <nav className="archive-filter-tabs" aria-label="Archive filters">
        {FILTERS.map((filter) => {
          const Icon = filter.icon;
          return (
            <button
              type="button"
              key={filter.id}
              className={activeFilter === filter.id ? "is-active" : ""}
              onClick={() => setActiveFilter(filter.id)}
            >
              <Icon size={16} aria-hidden="true" />
              <span>{filter.label}</span>
              <strong>{counts[filter.id] || 0}</strong>
            </button>
          );
        })}
      </nav>

      <section className="archive-list" aria-label="Archived items">
        {status === "loading" ? (
          <div className="archive-empty-state">Loading archived work...</div>
        ) : null}

        {status === "error" ? (
          <div className="archive-empty-state">
            Archive could not be loaded from this browser.
          </div>
        ) : null}

        {status === "ready" && !filteredItems.length ? (
          <div className="archive-empty-state">
            No archived items yet. Saved data, plots, and report drafts
            will appear here automatically.
          </div>
        ) : null}

        {filteredItems.map((item) => {
          const filter =
            FILTERS.find((entry) => matchesFilter(item, entry.id) && entry.id !== "all") ||
            FILTERS[0];
          const Icon = filter.icon;
          const meta = getItemMeta(item);
          const chartUrl = item.type === "chart" ? item.payload?.url : "";

          return (
            <article className="archive-item" key={item.id}>
              <span className="archive-item-icon" aria-hidden="true">
                <Icon size={20} />
              </span>

              <div className="archive-item-copy">
                <div className="archive-item-title-row">
                  <strong>{item.title || filter.label}</strong>
                  <span>{getItemKindLabel(item, filter.label)}</span>
                </div>
                <p>{item.description || "Archived from the data workspace."}</p>
                <div className="archive-item-meta">
                  <time>{formatDate(item.createdAt)}</time>
                  {meta.map((value) => (
                    <span key={value}>{value}</span>
                  ))}
                </div>
              </div>

              <div className="archive-item-actions">
                {chartUrl ? (
                  <a
                    href={chartUrl}
                    target="_blank"
                    rel="noreferrer"
                    title="Open plot"
                    aria-label="Open plot"
                  >
                    <ExternalLink size={16} />
                  </a>
                ) : null}
                <button
                  type="button"
                  onClick={() => exportJson(item)}
                  title={DATASET_TYPES.has(item.type) ? "Download dataframe CSV" : "Download archive item"}
                  aria-label={DATASET_TYPES.has(item.type) ? "Download dataframe CSV" : "Download archive item"}
                >
                  <Download size={16} />
                </button>
                <button
                  type="button"
                  className="archive-delete-button"
                  onClick={() => removeItem(item.id)}
                  title="Delete from archive"
                  aria-label="Delete from archive"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </article>
          );
        })}
      </section>
    </section>
  );
}

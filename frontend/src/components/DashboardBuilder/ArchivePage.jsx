import { useCallback, useEffect, useMemo, useState } from "react";
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
import { downloadCsv } from "../PageBuilder/DataAnalysisWorkspace/utils/dataframeExport";
import { getBuilderStorageKey } from "../PageBuilder/core/PageBuilder.constants";

const FILTERS = [
  { id: "all", label: "All", icon: Archive },
  { id: "dataset", label: "Saved data", description: "Cleaned and imported datasets", icon: Database },
  { id: "chart", label: "Plots", description: "Charts saved from analysis", icon: BarChart3 },
  { id: "report", label: "Reports", description: "Reusable report drafts", icon: FileText },
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
  const extension = isDatasetCsv ? "csv" : "json";
  const baseName = `${item.title || item.type || "archive-item"}`
    .replace(/[^\w.-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(new RegExp(`\\.${extension}$`, "i"), "");

  if (isDatasetCsv) {
    downloadCsv(datasetCsv, baseName);
    return;
  }

  const contents = JSON.stringify(item, null, 2);
  const blob = new Blob([contents], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${baseName}.${extension}`;
  link.click();
  URL.revokeObjectURL(url);
}

function getArchiveWorkspaceName(userId) {
  try {
    const rawProject = localStorage.getItem(getBuilderStorageKey(userId));
    if (!rawProject) return "Untitled Site";
    const project = JSON.parse(rawProject);
    return project.name || project.siteChrome?.brandName || "Untitled Site";
  } catch {
    return "Untitled Site";
  }
}

export default function ArchivePage({ user }) {
  const [items, setItems] = useState([]);
  const [activeFilter, setActiveFilter] = useState("all");
  const [status, setStatus] = useState("loading");
  const archiveScope = user?.id ? `user-${user.id}` : "";
  const workspaceName = useMemo(() => getArchiveWorkspaceName(user?.id), [user?.id]);

  const loadArchive = useCallback(async () => {
    setStatus("loading");
    try {
      const archiveItems = await listArchiveItems({
        scope: archiveScope,
      });
      setItems(archiveItems);
      setStatus("ready");
    } catch {
      setStatus("error");
    }
  }, [archiveScope]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadArchive();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [loadArchive]);

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
    <section className="page-builder archive-builder-page" aria-labelledby="archive-title">
      <div className="builder-desktop-shell archive-builder-shell">
        <header className="builder-topbar">
          <div className="builder-brand">
            <h1>{workspaceName}</h1>
            <p>Review, clean, and analyze your collected data.</p>
          </div>
        </header>

        <div className="archive-page daw-page">
          <header className="archive-header daw-header">
            <div>
              <span className="archive-kicker daw-kicker">Archive</span>
              <h1 id="archive-title">Saved work history</h1>
              <p>
                Keep old cleaned datasets, deleted charts, and report drafts so the
                next dataset does not erase useful previous work.
              </p>
            </div>
          </header>

      <div className="archive-summary-grid" aria-label="Archive summary">
        {FILTERS.slice(1).map((filter) => {
          const Icon = filter.icon;
          return (
            <article className="daw-card" key={filter.id}>
              <span aria-hidden="true">
                <Icon size={19} />
              </span>
              <div>
                <div className="archive-summary-heading">
                  <strong>{counts[filter.id] || 0}</strong>
                  <small>{filter.label}</small>
                </div>
                <p>{filter.description}</p>
              </div>
            </article>
          );
        })}
      </div>

      <section className="archive-filter-section daw-card" aria-labelledby="archive-browse-title">
        <div className="archive-section-heading">
          <div>
            <span>Saved items</span>
            <h2 id="archive-browse-title">Browse archive</h2>
          </div>
          <div className="archive-section-actions">
            <p>{filteredItems.length} of {items.length} items</p>
            <button
              type="button"
              className="archive-refresh-button"
              onClick={loadArchive}
              disabled={status === "loading"}
            >
              <RefreshCw className={status === "loading" ? "is-spinning" : ""} size={15} aria-hidden="true" />
              {status === "loading" ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>

        <nav className="archive-filter-tabs" aria-label="Archive filters">
          {FILTERS.map((filter) => {
            const Icon = filter.icon;
            return (
              <button
                type="button"
                key={filter.id}
                className={`daw-secondary ${activeFilter === filter.id ? "is-active" : ""}`}
                onClick={() => setActiveFilter(filter.id)}
                aria-pressed={activeFilter === filter.id}
              >
                <Icon size={16} aria-hidden="true" />
                <span>{filter.label}</span>
                <strong>{counts[filter.id] || 0}</strong>
              </button>
            );
          })}
        </nav>
      </section>

      <section className="archive-list daw-card" aria-labelledby="archive-items-title">
        <div className="archive-list-heading">
          <div>
            <span>History</span>
            <h2 id="archive-items-title">Archived items</h2>
          </div>
          <span>{filteredItems.length}</span>
        </div>
        {status === "loading" && !items.length ? (
          <div className="archive-empty-state" role="status">
            <span className="archive-empty-icon" aria-hidden="true"><RefreshCw className="is-spinning" size={24} /></span>
            <h3>Loading saved work</h3>
            <p>Checking this browser for datasets, plots, and report drafts.</p>
          </div>
        ) : null}

        {status === "error" ? (
          <div className="archive-empty-state" role="alert">
            <span className="archive-empty-icon" aria-hidden="true"><Archive size={24} /></span>
            <h3>Archive unavailable</h3>
            <p>Saved work could not be loaded from this browser.</p>
            <button type="button" onClick={loadArchive}>Try again</button>
          </div>
        ) : null}

        {status === "ready" && !filteredItems.length ? (
          <div className="archive-empty-state">
            <span className="archive-empty-icon" aria-hidden="true"><Archive size={24} /></span>
            <h3>{activeFilter === "all" ? "Your archive is ready" : `No ${FILTERS.find((filter) => filter.id === activeFilter)?.label.toLowerCase()} yet`}</h3>
            <p>
              {activeFilter === "all"
                ? "Saved data, plots, and report drafts will appear here automatically as you work."
                : "Try another filter or save new work from the data workspace."}
            </p>
            {activeFilter !== "all" ? (
              <button type="button" onClick={() => setActiveFilter("all")}>View all items</button>
            ) : null}
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
        </div>
      </div>
    </section>
  );
}

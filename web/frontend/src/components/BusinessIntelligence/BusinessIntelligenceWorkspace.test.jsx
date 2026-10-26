import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import BusinessIntelligenceWorkspace from "./BusinessIntelligenceWorkspace";
import { apiFetch } from "../../utils/apiClient";

vi.mock("../../utils/apiClient", () => ({
  apiFetch: vi.fn(),
  getApiUrl: (path) => `/api${path}`,
  readApiResponse: async (response) => response.json(),
}));

const json = (body, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
});

const datasetItems = [
  {
    id: "dataset-a",
    display_name: "General operations",
    updated_at: "2026-10-20T10:00:00Z",
    latest_version: {
      id: "version-a2",
      version_number: 2,
      version_kind: "checkpoint",
      content_hash: "abc123",
      file_metadata: { rows: 3, column_count: 3 },
    },
  },
  {
    id: "dataset-b",
    display_name: "Second dataset",
    latest_version: { id: "version-b1", version_number: 1, version_kind: "original" },
  },
];

const detailA = {
  persistent_dataset_id: "dataset-a",
  dataset_version_id: "version-a2",
  file_path: "general.csv",
  rows: 3,
  columns: ["category", "amount", "note"],
  preview: [
    { category: "North", amount: 12, note: "Ready" },
    { category: "South", amount: 7, note: "" },
    { category: "East", amount: 4, note: "Review" },
  ],
};
const versionsA = [
  datasetItems[0].latest_version,
  { id: "version-a1", version_number: 1, version_kind: "original", content_hash: "old123", file_metadata: { rows: 2, column_count: 3 } },
];
const explorationA = {
  rows: detailA.preview,
  columns: [{ name: "category", technical_type: "text" }, { name: "amount", technical_type: "number" }, { name: "note", technical_type: "text" }],
  pagination: { limit: 50, offset: 0, returned: 3, total: 3, has_more: false },
  provenance: { dataset_version_id: "version-a2" },
};

const profileResponses = {
  statistics: {
    rows: 3,
    numeric_columns: { amount: { count: 3, unique_count: 3, min: 4, max: 12, mean: 7.67, sum: 23 } },
    categorical_columns: { category: { count: 3, unique_count: 3 }, note: { count: 2, unique_count: 2 } },
  },
  "missing-report": { category: { missing_count: 0, missing_percentage: 0 }, amount: { missing_count: 0, missing_percentage: 0 }, note: { missing_count: 1, missing_percentage: 33.33 } },
  "column-types": { category: "object", amount: "float64", note: "object" },
};

function installDefaultApi() {
  apiFetch.mockImplementation(async (url, options = {}) => {
    if (url.endsWith("/datasets?limit=100")) return json({ available: true, items: datasetItems });
    if (url.endsWith("/dashboards?limit=100")) return json({ available: true, items: [] });
    if (url.endsWith("/report-schedules")) return json({ available: true, items: [] });
    if (url.endsWith("/reports?limit=50")) return json({ available: true, items: [] });
    if (url.endsWith("/dashboards") && options.method === "POST") return json({ id: "dashboard-1", name: "General operations dashboard", description: "", revision: 1 }, 201);
    if (url.endsWith("/dashboards/dashboard-1")) return json({ id: "dashboard-1", name: "General operations dashboard", description: "", revision: 1, widgets: [] });
    if (url.endsWith("/dashboards/dashboard-1/widgets") && options.method === "POST") return json({
      dashboard: { id: "dashboard-1", name: "General operations dashboard", revision: 2 },
      widget: { id: "widget-1", title: "Sum of selected column", widget_type: "kpi", dataset_id: "dataset-a", dataset_version_id: "version-a2", version_policy: "pinned", analysis_spec: { operation: "sum", value_column: "amount" } },
    }, 201);
    if (url.endsWith("/datasets/dataset-a/versions?limit=100")) return json({ available: true, items: versionsA });
    if (url.endsWith("/datasets/dataset-b/versions?limit=100")) return json({ available: true, items: [datasetItems[1].latest_version] });
    if (url.endsWith("/datasets/dataset-a/freshness")) return json({ available: true, source: { display_name: "Webhook source", last_successful_ingestion: "2026-10-20T09:00:00Z" } });
    if (url.endsWith("/datasets/dataset-b/freshness")) return json({ available: false, reason: "dataset_has_no_source" });
    if (url.includes("/datasets/dataset-a/versions/") && url.endsWith("/explore")) {
      const payload = JSON.parse(options.body);
      const rows = payload.filters?.[0]?.value === "South" ? [detailA.preview[1]] : detailA.preview;
      return json({ ...explorationA, rows, pagination: { ...explorationA.pagination, returned: rows.length, total: rows.length } });
    }
    if (url.includes("/datasets/dataset-b/versions/") && url.endsWith("/explore")) return json({ ...explorationA, rows: [], pagination: { limit: 50, offset: 0, returned: 0, total: 0, has_more: false } });
    if (url.endsWith("/datasets/dataset-a/versions/version-a2")) return json(detailA);
    if (url.endsWith("/datasets/dataset-a/versions/version-a1")) return json({ ...detailA, dataset_version_id: "version-a1", rows: 2, preview: detailA.preview.slice(0, 2) });
    if (url.endsWith("/datasets/dataset-b/versions/version-b1")) return json({ ...detailA, persistent_dataset_id: "dataset-b", dataset_version_id: "version-b1", file_path: "second.csv", rows: 0, preview: [] });
    for (const [path, body] of Object.entries(profileResponses)) {
      if (url.endsWith(`/cleaning/${path}`)) return json(body);
    }
    if (url.includes("/analysis/projects/project-1/datasets/dataset-a/versions/version-a2/assist")) {
      const payload = JSON.parse(options.body);
      return json({
        provenance: { project_id: "project-1", dataset_id: "dataset-a", dataset_version_id: "version-a2", content_hash: "abc123" },
        result: {
          title: payload.metric.label,
          summary: "The selected generic operation was calculated.",
          kpis: payload.metric.group_column ? [] : [{ label: payload.metric.label, value: 23, display_value: "23" }],
          tables: [{ title: payload.metric.label, rows: payload.metric.group_column ? [{ category: "North", value: 12 }, { category: "South", value: 7 }] : [{ value: 23 }] }],
          charts: payload.metric.group_column ? [{ title: payload.metric.label, type: "bar", x: "category", y: "value", data: [{ category: "North", value: 12 }, { category: "South", value: 7 }] }] : [],
        },
      });
    }
    throw new Error(`Unhandled request: ${url}`);
  });
}

const renderWorkspace = (props = {}) => render(
  <BusinessIntelligenceWorkspace
    lang="en"
    projectId="project-1"
    user={{ id: 7, tenant_id: 3 }}
    onChangeProject={vi.fn()}
    {...props}
  />,
);

beforeEach(() => {
  vi.clearAllMocks();
  installDefaultApi();
});
afterEach(cleanup);

describe("BusinessIntelligenceWorkspace", () => {
  it("loads only authorized project datasets and binds the latest immutable version", async () => {
    renderWorkspace();

    expect(await screen.findByRole("heading", { name: "General operations" })).toBeTruthy();
    expect(await screen.findByText("abc123")).toBeTruthy();
    expect(apiFetch).toHaveBeenCalledWith("/api/users/7/data/projects/project-1/datasets?limit=100", { credentials: "include" });
    expect(screen.getByRole("combobox", { name: "Immutable version" }).value).toBe("version-a2");
    expect(screen.getByText(/bound to the selected immutable version/i)).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Immutable version" }).options).toHaveLength(2);
    expect(screen.getByText(/No AI interpretation is active/i)).toBeTruthy();
  });

  it("explores a bounded preview with sorting, filtering, types, and missingness", async () => {
    renderWorkspace();
    await screen.findByRole("heading", { name: "General operations" });
    fireEvent.click(screen.getByRole("tab", { name: "Explore" }));

    expect(await screen.findByRole("heading", { name: "Bounded record preview" })).toBeTruthy();
    expect(await screen.findByText("South")).toBeTruthy();
    expect(screen.getByText(/allowlisted filters/i)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Filter field"), { target: { value: "category" } });
    fireEvent.change(screen.getByLabelText("Filter value"), { target: { value: "South" } });
    fireEvent.change(screen.getByLabelText("Sort preview by"), { target: { value: "amount" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply query" }));
    await waitFor(() => expect(screen.queryByText("North")).toBeNull());
    expect(screen.getByText("South")).toBeTruthy();
    const exploreCall = apiFetch.mock.calls.findLast(([url]) => url.endsWith("/explore"));
    expect(JSON.parse(exploreCall[1].body)).toMatchObject({ filters: [{ field: "category", operator: "eq", value: "South" }], sort: [{ field: "amount", direction: "asc" }] });
    expect(screen.getByText((_, element) => element.textContent === "1 (33.33%)")).toBeTruthy();
    expect(screen.getByText("float64")).toBeTruthy();
  });

  it("reopens a selected historical immutable version instead of silently using latest", async () => {
    renderWorkspace();
    const selector = await screen.findByRole("combobox", { name: "Immutable version" });
    await waitFor(() => expect(selector.options).toHaveLength(2));
    fireEvent.change(selector, { target: { value: "version-a1" } });
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith(
      expect.stringContaining("/datasets/dataset-a/versions/version-a1"), expect.any(Object),
    ));
    expect(selector.value).toBe("version-a1");
  });

  it("rejects incompatible fields and runs a version-bound generic grouped metric", async () => {
    renderWorkspace();
    await screen.findByRole("heading", { name: "General operations" });
    fireEvent.click(screen.getByRole("tab", { name: "Metrics" }));
    await waitFor(() => expect(screen.getByLabelText("Group by (optional)").options.length).toBeGreaterThan(1));

    const operationSelect = screen.getAllByLabelText("Operation").find((element) => element.tagName === "SELECT");
    fireEvent.change(operationSelect, { target: { value: "sum" } });
    expect(screen.getByLabelText("Numeric column").value).toBe("amount");
    expect([...screen.getByLabelText("Numeric column").options].map((option) => option.value)).not.toContain("note");
    fireEvent.change(screen.getByLabelText("Group by (optional)"), { target: { value: "category" } });
    fireEvent.click(screen.getByRole("button", { name: "Run calculation" }));

    expect(await screen.findByRole("heading", { name: "Sum of selected column" })).toBeTruthy();
    const analysisCall = apiFetch.mock.calls.find(([url]) => url.includes("/analysis/projects/"));
    expect(analysisCall[0]).toContain("/datasets/dataset-a/versions/version-a2/assist");
    expect(JSON.parse(analysisCall[1].body).metric).toEqual({
      operation: "sum",
      label: "Sum of selected column",
      value_column: "amount",
      group_column: "category",
    });
    expect(screen.getByText("Unit/currency: not declared")).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "Visualizations" }));
    expect(screen.getByRole("img", { name: "Sum of selected column" })).toBeTruthy();
    expect(screen.getAllByText("North").length).toBeGreaterThan(0);
  });

  it("clears prior results on version context changes and ignores stale responses", async () => {
    let resolveFirst;
    const firstDetail = new Promise((resolve) => { resolveFirst = resolve; });
    apiFetch.mockImplementation(async (url) => {
      if (url.endsWith("/datasets?limit=100")) return json({ available: true, items: datasetItems });
      if (url.endsWith("/dashboards?limit=100")) return json({ available: true, items: [] });
      if (url.endsWith("/datasets/dataset-a/versions?limit=100")) return json({ available: true, items: versionsA });
      if (url.endsWith("/datasets/dataset-b/versions?limit=100")) return json({ available: true, items: [datasetItems[1].latest_version] });
      if (url.endsWith("/datasets/dataset-a/freshness") || url.endsWith("/datasets/dataset-b/freshness")) return json({ available: false });
      if (url.endsWith("/datasets/dataset-a/versions/version-a2")) return firstDetail;
      if (url.endsWith("/datasets/dataset-b/versions/version-b1")) return json({ ...detailA, persistent_dataset_id: "dataset-b", file_path: "second.csv", rows: 0, preview: [] });
      if (url.includes("/datasets/dataset-a/") && url.endsWith("/explore")) return json(explorationA);
      if (url.includes("/datasets/dataset-b/") && url.endsWith("/explore")) return json({ ...explorationA, rows: [], pagination: { ...explorationA.pagination, returned: 0, total: 0 } });
      for (const [path, body] of Object.entries(profileResponses)) if (url.endsWith(`/cleaning/${path}`)) return json(body);
      throw new Error(url);
    });
    renderWorkspace();
    const selector = await screen.findByRole("combobox", { name: "Dataset" });
    fireEvent.change(selector, { target: { value: "dataset-b" } });
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith(expect.stringContaining("datasets/dataset-b/versions"), expect.any(Object)));
    resolveFirst(json(detailA));

    fireEvent.click(screen.getByRole("tab", { name: "Explore" }));
    expect(await screen.findByText("This dataset has no preview rows.")).toBeTruthy();
    expect(screen.queryByText("North")).toBeNull();
  });

  it("shows honest older-schema, empty, and API-failure states", async () => {
    apiFetch.mockResolvedValueOnce(json({ available: false, items: [] }));
    const first = renderWorkspace();
    expect(await screen.findByRole("heading", { name: "Business Intelligence is unavailable for this project" })).toBeTruthy();
    first.unmount();

    apiFetch.mockResolvedValueOnce(json({ available: true, items: [] }));
    const second = renderWorkspace();
    expect(await screen.findByRole("heading", { name: "No project datasets yet" })).toBeTruthy();
    second.unmount();

    apiFetch.mockResolvedValueOnce(json({ detail: "Data project was not found." }, 404));
    renderWorkspace();
    expect((await screen.findByRole("alert")).textContent).toContain("Data project was not found.");
  });

  it("preserves Arabic RTL and exposes persistent dashboard creation", async () => {
    const { container } = renderWorkspace({ lang: "ar" });
    await screen.findByRole("heading", { name: "General operations" });
    expect(container.querySelector(".bi-workspace").getAttribute("dir")).toBe("rtl");
    fireEvent.click(screen.getByRole("tab", { name: "لوحة المعلومات" }));
    expect(screen.getByRole("button", { name: "إنشاء لوحة معلومات" })).toBeTruthy();
  });

  it("creates a persistent dashboard and saves the current version-bound result as a widget", async () => {
    renderWorkspace();
    await screen.findByText("abc123");
    fireEvent.click(screen.getByRole("tab", { name: "Metrics" }));
    const operationSelect = screen.getAllByLabelText("Operation").find((element) => element.tagName === "SELECT");
    fireEvent.change(operationSelect, { target: { value: "sum" } });
    // The checksum is visible before async column selection is initialized.
    // A real user can run this metric only after that button becomes enabled.
    await waitFor(() => expect(screen.getByRole("button", { name: "Run calculation" }).disabled).toBe(false));
    fireEvent.click(screen.getByRole("button", { name: "Run calculation" }));
    await screen.findByRole("heading", { name: "Sum of selected column" });
    fireEvent.click(screen.getByRole("tab", { name: "Dashboard" }));
    fireEvent.click(screen.getByRole("button", { name: "Create dashboard" }));
    await screen.findByRole("button", { name: "Add current result" });
    fireEvent.click(screen.getByRole("button", { name: "Add current result" }));
    expect(await screen.findByRole("heading", { name: "Sum of selected column" })).toBeTruthy();
    const widgetCall = apiFetch.mock.calls.find(([url], index) => index > 0 && url.endsWith("/dashboards/dashboard-1/widgets"));
    expect(JSON.parse(widgetCall[1].body)).toMatchObject({
      expected_revision: 1, dataset_id: "dataset-a", dataset_version_id: "version-a2",
      version_policy: "pinned", analysis_spec: { operation: "sum", value_column: "amount" },
      layout_config: { x: 0, y: 0, w: 6, h: 4 },
    });
  });

  it("keeps tab controls keyboard focusable", async () => {
    renderWorkspace();
    await screen.findByRole("heading", { name: "General operations" });
    const metricsTab = screen.getByRole("tab", { name: "Metrics" });
    metricsTab.focus();
    expect(document.activeElement).toBe(metricsTab);
    fireEvent.click(metricsTab);
    expect(metricsTab.getAttribute("aria-selected")).toBe("true");
    expect(within(screen.getByRole("navigation", { name: "Business Intelligence" })).getAllByRole("tab")).toHaveLength(6);
  });

  it("configures recurring reports and renders immutable report provenance", async () => {
    const baseApi = apiFetch.getMockImplementation();
    apiFetch.mockImplementation(async (url, options = {}) => {
      if (url.endsWith("/dashboards?limit=100")) return json({ available: true, items: [{ id: "dashboard-1", name: "Operations" }] });
      if (url.endsWith("/dashboards/dashboard-1")) return json({ id: "dashboard-1", name: "Operations", description: "", revision: 2, auto_refresh_enabled: false, widgets: [] });
      if (url.endsWith("/report-schedules") && options.method === "POST") return json({ id: "schedule-1" }, 201);
      if (url.endsWith("/reports") && options.method === "POST") return json({ id: "report-1", status: "queued" }, 202);
      if (url.endsWith("/reports/report-1") && options.method === "DELETE") return json({ archived: true });
      if (url.endsWith("/reports/report-1")) return json({
        id: "report-1", status: "completed", dashboard_revision: 2, completed_at: "2026-10-25T08:00:00Z",
        definition_snapshot: { dashboard: { name: "Operations" } },
        version_vector: [{ widget_id: "widget-1", dataset_version_id: "version-a2", version_number: 2, content_hash: "abc123" }],
        result_snapshot: { title: "Operations", widgets: [{ widget_id: "widget-1", title: "Rows", status: "ready", result: { kpis: [{ label: "Rows", value: 3 }] } }] },
        warnings: [],
      });
      if (url.endsWith("/reports?limit=50")) return json({ available: true, items: [{ id: "report-1", trigger_type: "manual", status: "completed", dashboard_revision: 2, created_at: "2026-10-25T08:00:00Z", version_vector: [{ version_number: 2 }] }] });
      return baseApi(url, options);
    });
    renderWorkspace();
    await screen.findByRole("heading", { name: "General operations" });
    fireEvent.click(screen.getByRole("tab", { name: "Reports" }));
    fireEvent.change(screen.getByLabelText("Schedule name"), { target: { value: "Weekly operations" } });
    fireEvent.click(screen.getByRole("button", { name: "Create schedule" }));
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith(expect.stringContaining("/report-schedules"), expect.objectContaining({ method: "POST" })));
    const scheduleCall = apiFetch.mock.calls.find(([, options]) => options?.method === "POST" && options?.body?.includes("Weekly operations"));
    expect(JSON.parse(scheduleCall[1].body)).toMatchObject({ dashboard_id: "dashboard-1", cadence: "weekly", timezone: "UTC", weekday: 0 });
    fireEvent.click(screen.getByRole("button", { name: "Open report" }));
    expect(await screen.findByRole("heading", { name: "Operations" })).toBeTruthy();
    expect(screen.getByText(/version-a2/)).toBeTruthy();
    expect(screen.getByText(/business meaning, units, currencies/i)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Download CSV" }).getAttribute("href")).toContain("/reports/report-1/export.csv");
    vi.spyOn(window, "confirm").mockReturnValue(true);
    fireEvent.click(screen.getByRole("button", { name: "Archive report" }));
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith(
      expect.stringContaining("/reports/report-1"), expect.objectContaining({ method: "DELETE" }),
    ));
  });
});

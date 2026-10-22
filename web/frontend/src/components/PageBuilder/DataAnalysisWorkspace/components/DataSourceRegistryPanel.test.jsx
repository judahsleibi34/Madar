import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "../../../../utils/apiClient";
import { uiText } from "../constants/uiText";
import DataSourceRegistryPanel from "./DataSourceRegistryPanel";


vi.mock("../../../../utils/apiClient", async (importOriginal) => ({
  ...(await importOriginal()),
  apiFetch: vi.fn(),
}));

const response = (body, ok = true, status = ok ? 200 : 400) => ({
  ok,
  status,
  headers: { get: () => "application/json" },
  json: async () => body,
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("DataSourceRegistryPanel", () => {
  it("lists, creates, and archives project-bound spreadsheet sources", async () => {
    let created = false;
    let monthlyArchived = false;
    apiFetch.mockImplementation((url, options = {}) => {
      if (url.includes("/ingestions?")) return Promise.resolve(response({ available: true, items: [] }));
      if (options.method === "POST") {
        created = true;
        return Promise.resolve(response({
          id: "source-2", display_name: "Quarterly forecast",
          source_type: "spreadsheet_upload", status: "active",
        }, true, 201));
      }
      if (options.method === "PATCH") {
        monthlyArchived = true;
        return Promise.resolve(response({
          id: "source-1", display_name: "Monthly sales",
          source_type: "spreadsheet_upload", status: "archived",
        }));
      }
      const items = [
        ...(!monthlyArchived ? [{
          id: "source-1", display_name: "Monthly sales",
          source_type: "spreadsheet_upload", status: "active",
        }] : []),
        ...(created ? [{
          id: "source-2", display_name: "Quarterly forecast",
          source_type: "spreadsheet_upload", status: "active",
        }] : []),
      ];
      return Promise.resolve(response({
        available: true,
        items,
      }));
    });

    render(
      <DataSourceRegistryPanel
        projectId="project-1"
        user={{ id: 7 }}
        t={uiText.en}
      />
    );

    expect((await screen.findAllByText("Monthly sales")).length).toBeGreaterThan(0);
    expect(apiFetch.mock.calls[0][0]).toContain("/users/7/data/projects/project-1/sources?limit=100");

    fireEvent.change(screen.getByPlaceholderText(uiText.en.sourceRegistryPlaceholder), {
      target: { value: "Quarterly forecast" },
    });
    fireEvent.click(screen.getByRole("button", { name: uiText.en.sourceRegistryAdd }));
    expect((await screen.findAllByText("Quarterly forecast")).length).toBeGreaterThan(0);
    const createCall = apiFetch.mock.calls.find(([, options]) => options?.method === "POST");
    expect(JSON.parse(createCall[1].body)).toEqual({
      source_type: "spreadsheet_upload",
      display_name: "Quarterly forecast",
    });

    fireEvent.click(screen.getByRole("button", {
      name: `${uiText.en.sourceRegistryArchive} Monthly sales`,
    }));
    await waitFor(() => expect(screen.queryByText("Monthly sales")).toBeNull());
    const archiveCall = apiFetch.mock.calls.find(([, options]) => options?.method === "PATCH");
    expect(JSON.parse(archiveCall[1].body)).toEqual({ status: "archived" });
  });

  it("keeps legacy uploads available when migration 148 is missing", async () => {
    apiFetch.mockResolvedValueOnce(response({ available: false, items: [] }));
    render(
      <DataSourceRegistryPanel
        projectId="project-1"
        user={{ id: 7 }}
        t={uiText.en}
      />
    );
    expect(await screen.findByText(uiText.en.sourceRegistryUpgrade)).toBeTruthy();
    expect(screen.queryByRole("button", { name: uiText.en.sourceRegistryAdd })).toBeNull();
  });

  it("uploads to the selected source, shows history, and reopens its dataset", async () => {
    const onDatasetImported = vi.fn();
    const onReopenDataset = vi.fn();
    apiFetch.mockImplementation((url) => {
      if (url.includes("/ingestions/upload")) return Promise.resolve(response({
        ingestion_run_id: "run-2",
        ingestion_status: "succeeded",
        persistent_dataset_id: "dataset-2",
        dataset_version_id: "version-2",
      }, true, 201));
      if (url.includes("/ingestions?")) return Promise.resolve(response({
        available: true,
        items: [{ id: "run-1", status: "succeeded", result_dataset_id: "dataset-1" }],
      }));
      return Promise.resolve(response({
        available: true,
        items: [{
          id: "source-1",
          display_name: "Monthly sales",
          source_type: "spreadsheet_upload",
          status: "active",
          latest_dataset_id: "dataset-1",
        }],
      }));
    });

    render(
      <DataSourceRegistryPanel
        projectId="project-1"
        user={{ id: 7 }}
        t={uiText.en}
        onDatasetImported={onDatasetImported}
        onReopenDataset={onReopenDataset}
      />
    );

    expect(await screen.findByText(uiText.en.sourceIngestionHistory)).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: uiText.en.sourceIngestionOpen })[0]);
    expect(onReopenDataset).toHaveBeenCalledWith("dataset-1");

    const file = new File(["name,value\na,1\n"], "sales.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText(uiText.en.sourceIngestionFile), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: uiText.en.sourceIngestionUpload }));

    expect(await screen.findByText(uiText.en.sourceIngestionSucceeded)).toBeTruthy();
    const uploadCall = apiFetch.mock.calls.find(([url]) => url.includes("/ingestions/upload"));
    expect(uploadCall[1].headers["Idempotency-Key"].length).toBeGreaterThanOrEqual(8);
    expect(onDatasetImported).toHaveBeenCalledWith(expect.objectContaining({
      persistent_dataset_id: "dataset-2",
    }));
  });

  it("keeps the existing source registry usable before migration 149", async () => {
    apiFetch.mockImplementation((url) => Promise.resolve(response(
      url.includes("/ingestions?")
        ? { available: false, items: [] }
        : { available: true, items: [{ id: "source-1", display_name: "Monthly sales" }] }
    )));
    render(<DataSourceRegistryPanel projectId="project-1" user={{ id: 7 }} t={uiText.en} />);
    expect(await screen.findByText(uiText.en.sourceIngestionUpgrade)).toBeTruthy();
    expect(screen.queryByRole("button", { name: uiText.en.sourceIngestionUpload })).toBeNull();
  });

  it("shows synchronization management only for an API source", async () => {
    apiFetch.mockImplementation((url) => {
      if (url.includes("/ingestions?")) return Promise.resolve(response({ available: true, items: [] }));
      if (url.includes("/resources?")) return Promise.resolve(response({
        available: true,
        provider_registered: false,
        checkpoint_capable: true,
        items: [],
      }));
      if (url.endsWith("/credentials")) return Promise.resolve(response({ items: [] }));
      return Promise.resolve(response({
        available: true,
        items: [{
          id: "source-api",
          display_name: "Orders API",
          source_type: "api_provider",
          provider_key: "not_registered",
          resource_type: "orders",
          status: "active",
        }],
      }));
    });
    render(<DataSourceRegistryPanel projectId="project-1" user={{ id: 7 }} t={uiText.en} />);
    expect(await screen.findByText(uiText.en.sourceConnectionTitle)).toBeTruthy();
    expect(screen.getByText(/API source · not_registered/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: uiText.en.sourceIngestionUpload })).toBeNull();
  });

  it("translates a generic route 404 into an actionable backend mismatch", async () => {
    apiFetch.mockResolvedValue(response({ detail: "Not Found" }, false, 404));
    render(<DataSourceRegistryPanel projectId="project-1" user={{ id: 7 }} t={uiText.en} />);
    expect(await screen.findByText(uiText.en.sourceRegistryBackendMismatch)).toBeTruthy();
    expect(screen.queryByRole("button", { name: uiText.en.sourceRegistryAdd })).toBeNull();
  });

  it("registers only a server-advertised API provider and resource", async () => {
    let created = false;
    apiFetch.mockImplementation((url, options = {}) => {
      if (url.endsWith("/source-capabilities")) return Promise.resolve(response({
        source_registry_available: true,
        api_sources_available: true,
        credential_vault_available: true,
        automatic_sync_available: true,
        providers: [{
          key: "approved_provider", label: "Approved provider",
          resources: [{ key: "orders", label: "Orders" }],
        }],
      }));
      if (options.method === "POST") {
        created = true;
        return Promise.resolve(response({
          id: "source-api", display_name: "Business orders", source_type: "api_provider",
          provider_key: "approved_provider", resource_type: "orders", status: "active",
        }, true, 201));
      }
      if (url.includes("/ingestions?")) return Promise.resolve(response({ available: true, items: [] }));
      if (url.includes("/resources?")) return Promise.resolve(response({ available: true, provider_registered: true, items: [] }));
      if (url.endsWith("/credentials")) return Promise.resolve(response({ items: [] }));
      return Promise.resolve(response({ available: true, items: created ? [{
        id: "source-api", display_name: "Business orders", source_type: "api_provider",
        provider_key: "approved_provider", resource_type: "orders", status: "active",
      }] : [] }));
    });
    render(<DataSourceRegistryPanel projectId="project-1" user={{ id: 7 }} t={uiText.en} />);
    fireEvent.click(await screen.findByRole("button", { name: /Approved API connection/ }));
    fireEvent.change(screen.getByPlaceholderText(uiText.en.sourceRegistryPlaceholder), {
      target: { value: "Business orders" },
    });
    fireEvent.click(screen.getByRole("button", { name: uiText.en.sourceRegistryAddApi }));
    expect((await screen.findAllByText("Business orders")).length).toBeGreaterThan(0);
    const createCall = apiFetch.mock.calls.find(([, options]) => options?.method === "POST");
    expect(JSON.parse(createCall[1].body)).toEqual({
      source_type: "api_provider",
      display_name: "Business orders",
      provider_key: "approved_provider",
      resource_type: "orders",
    });
  });
});

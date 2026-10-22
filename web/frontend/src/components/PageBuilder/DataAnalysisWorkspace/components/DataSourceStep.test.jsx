import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import DataSourceStep from "./DataSourceStep";


const text = {
  source: "Source",
  sourceTitle: "Choose source",
  sourceSubtitle: "Choose one",
  forms: "Forms",
  upload: "Upload",
  external: "External",
  projectDatasets: "Project datasets",
  projectDatasetsHint: "Reopen an upload",
  loadingDatasets: "Loading datasets",
  noProjectDatasets: "No datasets",
  openDataset: "Open",
  datasetReady: "Ready",
};


describe("DataSourceStep persistent project datasets", () => {
  it("lists server datasets and reopens the selected identity", () => {
    const reopen = vi.fn();
    render(
      <DataSourceStep
        sourceMode="forms"
        setSourceMode={vi.fn()}
        availableForms={[]}
        setSelectedFormId={vi.fn()}
        setSelectedFile={vi.fn()}
        externalUrl=""
        setExternalUrl={vi.fn()}
        importFormResponses={vi.fn()}
        uploadFile={vi.fn()}
        loadExternalSource={vi.fn()}
        projectDatasets={[
          { id: "dataset-1", display_name: "sales.csv", latest_version: { size_bytes: 2048 } },
        ]}
        projectDatasetsStatus="ready"
        reopenProjectDataset={reopen}
        isLoading={false}
        t={text}
      />
    );

    expect(screen.getByText("sales.csv")).toBeTruthy();
    expect(screen.getByText("2 KB")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(reopen).toHaveBeenCalledWith("dataset-1");
  });

  it("shows the empty server state without browser storage", () => {
    render(
      <DataSourceStep
        sourceMode="forms"
        setSourceMode={vi.fn()}
        availableForms={[]}
        setSelectedFormId={vi.fn()}
        setSelectedFile={vi.fn()}
        externalUrl=""
        setExternalUrl={vi.fn()}
        importFormResponses={vi.fn()}
        uploadFile={vi.fn()}
        loadExternalSource={vi.fn()}
        projectDatasets={[]}
        projectDatasetsStatus="ready"
        reopenProjectDataset={vi.fn()}
        isLoading={false}
        t={text}
      />
    );

    expect(screen.getByText("No datasets")).toBeTruthy();
  });
});

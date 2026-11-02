import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import ReportBuilderStep from "./ReportBuilderStep";
import { archiveItem, listArchiveItems } from "../utils/datasetStorage";

vi.mock("../utils/datasetStorage", () => ({
  archiveItem: vi.fn(), listArchiveItems: vi.fn(),
}));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

it("reopens the saved report draft and saves its content in the original scope", async () => {
  const scope = "archive:v2:tenant:tenant-a:user:user-7:project:project-a";
  const document = {
    archiveId: "report-original", report: { title: "Saved quarterly draft" },
    blocks: [{ id: "report-block-8", type: "text", title: "Original heading", body: "Recoverable original content" }],
  };
  listArchiveItems.mockResolvedValue([{ id: "report-original", type: "report", title: document.report.title, payload: document }]);
  archiveItem.mockResolvedValue("report-original");
  render(<ReportBuilderStep archiveScope={scope} />);
  await screen.findByRole("option", { name: "Saved quarterly draft" });
  fireEvent.change(screen.getByLabelText("Work on saved report"), { target: { value: "report-original" } });
  expect(screen.getByText("Recoverable original content")).toBeTruthy();
  expect(screen.getByLabelText("Report file name").value).toBe("Saved quarterly draft");
  fireEvent.click(screen.getByRole("button", { name: "Save report" }));
  await waitFor(() => expect(archiveItem).toHaveBeenCalledWith(expect.objectContaining({
    id: "report-original", type: "report", scope,
    payload: expect.objectContaining({ report: expect.objectContaining(document.report), blocks: document.blocks }),
  })));
  expect(listArchiveItems).toHaveBeenCalledWith({ scope });
});

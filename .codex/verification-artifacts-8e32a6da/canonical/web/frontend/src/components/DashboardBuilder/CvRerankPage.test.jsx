import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import CvRerankPage from "./CvRerankPage";

afterEach(cleanup);

const upload = (container, files) => {
  const input = container.querySelector('input[type="file"]');
  fireEvent.change(input, { target: { files } });
};

describe("CvRerankPage", () => {
  it("accepts CV files, rejects unsupported files, and avoids duplicates", () => {
    const { container } = render(<CvRerankPage />);
    const cv = new File(["candidate"], "candidate.pdf", { type: "application/pdf", lastModified: 10 });
    const image = new File(["image"], "portrait.png", { type: "image/png", lastModified: 11 });

    upload(container, [cv, cv, image]);

    expect(screen.getByText("candidate.pdf")).toBeTruthy();
    expect(screen.getByText("1 uploaded · 0 ranked")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("1 unsupported file");
    expect(screen.getAllByText("candidate.pdf")).toHaveLength(1);
  });

  it("creates a deterministic client-side preview ranking", async () => {
    const { container } = render(<CvRerankPage />);
    upload(container, [
      new File(["one"], "amira.pdf", { type: "application/pdf", lastModified: 10 }),
      new File(["two"], "bassam.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", lastModified: 11 }),
    ]);

    fireEvent.change(screen.getByLabelText(/Requirements/), {
      target: { value: "Five years of analytics experience and strong SQL skills" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Rerank candidates" }));

    expect(screen.getByRole("button", { name: "Reranking…" }).disabled).toBe(true);
    await waitFor(() => expect(screen.getByText("2 uploaded · 2 ranked")).toBeTruthy());
    expect(screen.getAllByText("Ranked")).toHaveLength(2);
    expect(container.querySelectorAll(".cv-rerank-score")[0].textContent).toMatch(/^\d+%$/);
  });

  it("removes one candidate and clears the batch", () => {
    const { container } = render(<CvRerankPage />);
    upload(container, [
      new File(["one"], "first.pdf", { type: "application/pdf", lastModified: 10 }),
      new File(["two"], "second.doc", { type: "application/msword", lastModified: 11 }),
    ]);

    fireEvent.click(screen.getByRole("button", { name: "Remove first.pdf" }));
    expect(screen.queryByText("first.pdf")).toBeNull();
    expect(screen.getByText("second.doc")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Clear batch" }));
    expect(screen.getByText("No CVs in this batch")).toBeTruthy();
  });
});
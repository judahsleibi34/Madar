import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { uiText } from "../constants/uiText";
import DataWorkspaceChatbot from "./DataWorkspaceChatbot";

afterEach(cleanup);
beforeEach(() => window.localStorage.clear());

describe("DataWorkspaceChatbot", () => {
  it("opens from the AI icon and stays disabled until data is loaded", () => {
    const { container } = render(
      <DataWorkspaceChatbot
        dataset={null}
        onAsk={vi.fn()}
        t={uiText.en}
        isArabic={false}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: uiText.en.chatbotOpen }));

    expect(screen.getByRole("dialog", { name: uiText.en.chatbotTitle })).toBeTruthy();
    expect(screen.getByLabelText(uiText.en.chatbotQuestionLabel).disabled).toBe(true);
    expect(screen.getByRole("button", { name: uiText.en.chatbotSend }).disabled).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: uiText.en.chatbotEnterFullPage }));
    expect(container.querySelector(".daw-chatbot").classList.contains("is-full-page")).toBe(true);
    expect(container.querySelector(".daw-chatbot-history-sidebar")).toBeTruthy();
    expect(container.querySelector(".daw-chatbot-full-page-watermark")).toBeTruthy();
    expect(screen.queryByRole("button", { name: uiText.en.chatbotHistory })).toBeNull();
    expect(screen.getByRole("button", { name: uiText.en.chatbotExitFullPage })).toBeTruthy();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(container.querySelector(".daw-chatbot").classList.contains("is-full-page")).toBe(false);
  });

  it("sends a loaded-dataset question and renders the assistant response", async () => {
    const onAsk = vi.fn().mockResolvedValue({ summary: "The average cost is 42." });
    render(
      <DataWorkspaceChatbot
        dataset={{ file_path: "uploads/example.csv" }}
        onAsk={onAsk}
        t={uiText.en}
        isArabic={false}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: uiText.en.chatbotOpen }));
    expect(screen.getByPlaceholderText(uiText.en.chatbotPlaceholder)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(uiText.en.chatbotQuestionLabel), {
      target: { value: "What is the average cost?" },
    });
    fireEvent.click(screen.getByRole("button", { name: uiText.en.chatbotSend }));

    expect(onAsk).toHaveBeenCalledWith("What is the average cost?");
    expect(screen.getByText("What is the average cost?")).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByText("The average cost is 42.")).toBeTruthy();
    });
  });

  it("stores completed conversations in session history", async () => {
    const onAsk = vi.fn().mockResolvedValue({ summary: "Revenue increased." });
    render(
      <DataWorkspaceChatbot
        dataset={{ file_path: "uploads/report.csv", original_filename: "report.csv" }}
        onAsk={onAsk}
        t={uiText.en}
        isArabic={false}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: uiText.en.chatbotOpen }));
    fireEvent.change(screen.getByLabelText(uiText.en.chatbotQuestionLabel), {
      target: { value: "How did revenue change?" },
    });
    fireEvent.click(screen.getByRole("button", { name: uiText.en.chatbotSend }));
    await screen.findByText("Revenue increased.");

    fireEvent.click(screen.getByRole("button", { name: uiText.en.chatbotNewSession }));
    fireEvent.click(screen.getByRole("button", { name: uiText.en.chatbotHistory }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /How did revenue change\?/ })).toBeTruthy();
    });
  });
});

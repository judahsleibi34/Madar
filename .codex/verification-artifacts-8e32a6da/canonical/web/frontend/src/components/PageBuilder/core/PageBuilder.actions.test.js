import { describe, expect, it, vi } from "vitest";
import {
  getButtonActionIssue,
  normalizeElementAction,
  runPublicElementAction,
} from "./PageBuilder.actions";
import { getStoredUrlError } from "./PageBuilder.url";

const pages = [
  { id: "home", name: "Home", slug: "/", isDefault: true },
  { id: "form", name: "Form", slug: "/form" },
];

describe("published button actions", () => {
  it("normalizes legacy action fields to the canonical contract", () => {
    expect(normalizeElementAction({ actionType: "page", targetPageId: 42 })).toMatchObject({
      type: "goToPage",
      pageId: "42",
    });
  });

  it("navigates to an internal page by stable page id", () => {
    const goToPage = vi.fn();
    const result = runPublicElementAction({
      element: { type: "button", action: { type: "goToPage", pageId: "home" } },
      pages,
      goToPage,
      getStoredUrlError,
    });
    expect(result).toEqual({ handled: true, type: "goToPage" });
    expect(goToPage).toHaveBeenCalledWith(pages[0]);
  });

  it("applies the same validated page navigation contract to image buttons", () => {
    const goToPage = vi.fn();
    const result = runPublicElementAction({
      element: { type: "imageButton", action: { type: "goToPage", pageId: "form" } },
      pages,
      goToPage,
      getStoredUrlError,
    });
    expect(result).toEqual({ handled: true, type: "goToPage" });
    expect(goToPage).toHaveBeenCalledWith(pages[1]);
  });

  it("reports a missing internal target without navigating", () => {
    const goToPage = vi.fn();
    const showUnavailable = vi.fn();
    const result = runPublicElementAction({
      element: { type: "button", action: { type: "goToPage", pageId: "missing" } },
      pages,
      goToPage,
      getStoredUrlError,
      showUnavailable,
    });
    expect(result.issue.issue_type).toBe("invalid_button_page_target");
    expect(goToPage).not.toHaveBeenCalled();
    expect(showUnavailable).toHaveBeenCalledWith("This button action is unavailable.");
  });

  it("allows buttons with no destination to publish as no-action buttons", () => {
    const goToPage = vi.fn();
    const openExternal = vi.fn();
    const showUnavailable = vi.fn();

    for (const action of [
      { type: "goToPage", pageId: "" },
      { type: "openUrl", url: "" },
    ]) {
      expect(getButtonActionIssue({
        element: { type: "button", action },
        pages,
        getStoredUrlError,
      })).toBeNull();
      const result = runPublicElementAction({
        element: { type: "button", action },
        pages,
        goToPage,
        getStoredUrlError,
        openExternal,
        showUnavailable,
      });
      expect(result).toMatchObject({ handled: false, issue: { issue_type: "missing_button_action" } });
    }

    expect(goToPage).not.toHaveBeenCalled();
    expect(openExternal).not.toHaveBeenCalled();
  });

  it("opens an HTTPS URL with the saved new-tab policy", () => {
    const openExternal = vi.fn();
    runPublicElementAction({
      element: { type: "button", action: { type: "openUrl", url: "https://example.com", openInNewTab: true } },
      pages,
      getStoredUrlError,
      openExternal,
    });
    expect(openExternal).toHaveBeenCalledWith("https://example.com", true);
  });

  it.each(["javascript:alert(1)", "data:text/html,test", "file:///tmp/test", "http://example.com"])(
    "blocks unsafe external URL %s",
    (url) => {
      expect(getButtonActionIssue({
        element: { type: "button", action: { type: "openUrl", url } },
        pages,
        getStoredUrlError,
      })?.issue_type).toBe("invalid_button_url");
    }
  );

  it("displays a message as plain data without navigating", () => {
    const showMessage = vi.fn();
    const goToPage = vi.fn();
    runPublicElementAction({
      element: { type: "button", action: { type: "showMessage", message: "<b>Plain text</b>" } },
      pages,
      getStoredUrlError,
      showMessage,
      goToPage,
    });
    expect(showMessage).toHaveBeenCalledWith("<b>Plain text</b>");
    expect(goToPage).not.toHaveBeenCalled();
  });

  it("allows an empty message when publishing", () => {
    expect(getButtonActionIssue({
      element: { type: "button", action: { type: "showMessage", message: "  " } },
      pages,
      getStoredUrlError,
    })).toBeNull();
  });
});

import { describe, expect, it, vi } from "vitest";

import {
  createUploadHandlers,
  getBuilderAssetFileName,
} from "./PageBuilder.uploadHandlers";

describe("Page Builder image uploads", () => {
  it("shows only a decoded filename for stored asset paths", () => {
    expect(getBuilderAssetFileName("/uploads/tenant_4/builder_assets/My%20Photo.png?version=2"))
      .toBe("My Photo.png");
  });

  it("preserves the original upload filename separately from the server path", async () => {
    const updateSelectedElement = vi.fn();
    const handlers = createUploadHandlers({
      selectedElement: { id: "image-1", type: "image", name: "Image" },
      carouselElementTypes: new Set(),
      builderAssetMimeTypes: new Set(["image/png"]),
      builderAssetMaxBytes: 5_000_000,
      uploadBuilderAsset: vi.fn().mockResolvedValue({ url: "/uploads/hash.png" }),
      setAssetUploadBusy: vi.fn(),
      updateSelectedElement,
      showToast: vi.fn(),
      user: { id: "user-1" },
    });
    const file = { name: "team-photo.png", type: "image/png", size: 100 };

    await handlers.handleSelectedElementImageUpload({
      target: { files: [file], value: "selected" },
    });

    expect(updateSelectedElement).toHaveBeenCalledWith(expect.objectContaining({
      content: "/uploads/hash.png",
      assetFileName: "team-photo.png",
    }));
  });
});

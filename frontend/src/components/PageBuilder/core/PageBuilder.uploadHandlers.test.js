import { describe, expect, it, vi } from "vitest";

import {
  createUploadHandlers,
  fitMediaPositionsToAspectRatio,
  getBuilderAssetFileName,
  parsePhotoProofingContent,
  serializePhotoProofingContent,
} from "./PageBuilder.uploadHandlers";

describe("Page Builder image uploads", () => {
  it("fits every responsive boundary to the uploaded media aspect ratio", () => {
    expect(fitMediaPositionsToAspectRatio({
      desktop: { x: 10, y: 20, width: 600, height: 100 },
      mobile: { x: 5, y: 10, width: 300, height: 100 },
    }, 1.5)).toEqual({
      desktop: { x: 10, y: 20, width: 600, height: 400 },
      mobile: { x: 5, y: 10, width: 300, height: 200 },
    });
  });

  it("keeps descriptions only on the Photo Proofing cover", () => {
    const serialized = serializePhotoProofingContent([
      { title: "Cover", description: "Cover description", image: "/cover.jpg" },
      { title: "Gallery", description: "Must not be saved", image: "/gallery.jpg" },
    ]);

    expect(serialized).toContain("Cover description");
    expect(serialized).not.toContain("Must not be saved");
    expect(parsePhotoProofingContent(serialized)).toEqual([
      { title: "Cover", description: "Cover description", image: "/cover.jpg" },
      { title: "Gallery", description: "", image: "/gallery.jpg" },
    ]);
  });

  it("uploads every selected Photo Proofing image into one gallery", async () => {
    const updateSelectedElement = vi.fn();
    const uploadBuilderAsset = vi.fn()
      .mockResolvedValueOnce({ url: "/uploads/cover.jpg" })
      .mockResolvedValueOnce({ url: "/uploads/detail.jpg" })
      .mockResolvedValueOnce({ url: "/uploads/final.jpg" });
    const handlers = createUploadHandlers({
      selectedElement: { id: "proof-1", type: "photoProofing", content: "", proofing: { description: "Only the cover" } },
      carouselElementTypes: new Set(),
      builderAssetMimeTypes: new Set(["image/jpeg"]),
      builderAssetMaxBytes: 5_000_000,
      uploadBuilderAsset,
      setAssetUploadBusy: vi.fn(),
      updateSelectedElement,
      showToast: vi.fn(),
      user: { id: "user-1" },
    });
    const files = [
      { name: "cover.jpg", type: "image/jpeg", size: 100 },
      { name: "detail.jpg", type: "image/jpeg", size: 100 },
      { name: "final.jpg", type: "image/jpeg", size: 100 },
    ];

    await handlers.uploadPhotoProofingFiles(files);

    expect(uploadBuilderAsset).toHaveBeenCalledTimes(3);
    const saved = parsePhotoProofingContent(updateSelectedElement.mock.calls[0][0].content);
    expect(saved.map((photo) => photo.title)).toEqual(["cover", "detail", "final"]);
    expect(saved).toHaveLength(3);
  });

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

  it("uploads a PDF into the selected File Viewer", async () => {
    const updateSelectedElement = vi.fn();
    const showToast = vi.fn();
    const handlers = createUploadHandlers({
      selectedElement: { id: "document-1", type: "document", name: "File Viewer" },
      carouselElementTypes: new Set(),
      builderDocumentMimeTypes: new Set(["application/pdf"]),
      builderDocumentMaxBytes: 50_000_000,
      uploadBuilderAsset: vi.fn().mockResolvedValue("/uploads/tenant_1/builder_assets/hash.pdf"),
      setAssetUploadBusy: vi.fn(),
      updateSelectedElement,
      showToast,
      user: { id: "user-1" },
    });

    await handlers.handleSelectedElementDocumentUpload({
      target: {
        files: [{ name: "session-guide.pdf", type: "application/pdf", size: 1200 }],
        value: "selected",
      },
    });

    expect(updateSelectedElement).toHaveBeenCalledWith(expect.objectContaining({
      content: "/uploads/tenant_1/builder_assets/hash.pdf",
      assetFileName: "session-guide.pdf",
      documentMimeType: "application/pdf",
    }));
    expect(showToast).toHaveBeenCalledWith("File uploaded.");
  });

  it("rejects unsupported File Viewer uploads before sending them", async () => {
    const uploadBuilderAsset = vi.fn();
    const showToast = vi.fn();
    const handlers = createUploadHandlers({
      selectedElement: { id: "document-1", type: "document" },
      carouselElementTypes: new Set(),
      builderDocumentMimeTypes: new Set(["application/pdf"]),
      builderDocumentMaxBytes: 50_000_000,
      uploadBuilderAsset,
      setAssetUploadBusy: vi.fn(),
      updateSelectedElement: vi.fn(),
      showToast,
    });

    await handlers.handleSelectedElementDocumentUpload({
      target: { files: [{ name: "archive.zip", type: "application/zip", size: 100 }], value: "selected" },
    });

    expect(uploadBuilderAsset).not.toHaveBeenCalled();
    expect(showToast).toHaveBeenCalledWith("Use a PDF, DOC, or DOCX file.");
  });

  it("resizes a direct image boundary using the uploaded image dimensions", async () => {
    const updateSelectedElement = vi.fn();
    const handlers = createUploadHandlers({
      selectedElement: {
        id: "image-1",
        type: "image",
        mode: "direct",
        name: "Image",
        position: { desktop: { x: 20, y: 30, width: 800, height: 260 } },
      },
      carouselElementTypes: new Set(),
      builderAssetMimeTypes: new Set(["image/png"]),
      builderAssetMaxBytes: 5_000_000,
      uploadBuilderAsset: vi.fn().mockResolvedValue({ url: "/uploads/hash.png" }),
      readMediaAspectRatio: vi.fn().mockResolvedValue(2),
      setAssetUploadBusy: vi.fn(),
      updateSelectedElement,
      showToast: vi.fn(),
      user: { id: "user-1" },
    });

    await handlers.handleSelectedElementImageUpload({
      target: { files: [{ name: "wide.png", type: "image/png", size: 100 }], value: "selected" },
    });

    expect(updateSelectedElement).toHaveBeenCalledWith(expect.objectContaining({
      mediaAspectRatio: 2,
      position: { desktop: { x: 20, y: 30, width: 800, height: 400 } },
    }));
  });
  it("stores a custom loading image in site chrome", async () => {
    const updateProject = vi.fn();
    const handlers = createUploadHandlers({
      carouselElementTypes: new Set(),
      defaultSiteChrome: { logoUrl: "", loadingImageUrl: "" },
      builderAssetMimeTypes: new Set(["image/png"]),
      builderAssetMaxBytes: 5_000_000,
      uploadBuilderAsset: vi.fn().mockResolvedValue({ url: "/uploads/loading.png" }),
      setAssetUploadBusy: vi.fn(),
      updateProject,
      showToast: vi.fn(),
      user: { id: "user-1" },
    });

    await handlers.handleLoadingImageUpload({
      target: { files: [{ name: "loading.png", type: "image/png", size: 100 }], value: "selected" },
    });

    const updater = updateProject.mock.calls[0][0];
    expect(updater({ siteChrome: { logoUrl: "/logo.png" } }).siteChrome)
      .toMatchObject({ logoUrl: "/logo.png", loadingImageUrl: "/uploads/loading.png" });
  });
});

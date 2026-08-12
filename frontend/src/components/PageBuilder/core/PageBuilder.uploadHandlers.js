export const getBuilderAssetFileName = (value) => {
  const cleanValue = String(value || "").split(/[?#]/, 1)[0].replace(/\\/g, "/");
  const encodedName = cleanValue.slice(cleanValue.lastIndexOf("/") + 1);
  try {
    return decodeURIComponent(encodedName);
  } catch {
    return encodedName;
  }
};

export const parsePhotoProofingContent = (content = "") =>
  String(content)
    .split(/\n\s*\n/)
    .map((block, index) => {
      const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
      const image = lines.findLast((line) => /^(https:\/\/|\/)/i.test(line)) || "";
      const copy = image ? lines.filter((line) => line !== image) : lines;
      return {
        title: copy[0] || `Photo ${index + 1}`,
        description: copy.slice(1).join(" "),
        image,
      };
    })
    .filter((photo) => photo.image);

export const serializePhotoProofingContent = (photos = []) =>
  photos
    .filter((photo) => photo?.image)
    .map((photo, index) => [
      photo.title || `Photo ${index + 1}`,
      index === 0 ? photo.description || "" : "",
      photo.image,
    ].filter(Boolean).join("\n"))
    .join("\n\n");

export const fitMediaPositionsToAspectRatio = (positions = {}, aspectRatio = 0) => {
  const ratio = Number(aspectRatio);
  if (!Number.isFinite(ratio) || ratio <= 0) return positions;

  return Object.fromEntries(Object.entries(positions || {}).map(([viewportName, position]) => {
    const width = Number(position?.width) || 0;
    if (!width) return [viewportName, position];
    return [viewportName, {
      ...position,
      height: Math.max(48, Math.round(width / ratio)),
    }];
  }));
};

export const readBuilderMediaAspectRatio = async (file, mediaType) => {
  if (typeof Blob === "undefined" || !(file instanceof Blob)) return 0;
  const objectUrl = URL.createObjectURL(file);

  try {
    if (mediaType === "image") {
      const image = new Image();
      const dimensions = await new Promise((resolve) => {
        image.onload = () => resolve([image.naturalWidth, image.naturalHeight]);
        image.onerror = () => resolve([0, 0]);
        image.src = objectUrl;
      });
      return dimensions[0] > 0 && dimensions[1] > 0 ? dimensions[0] / dimensions[1] : 0;
    }

    const video = document.createElement("video");
    video.preload = "metadata";
    const dimensions = await new Promise((resolve) => {
      const finish = () => resolve([video.videoWidth, video.videoHeight]);
      video.onloadedmetadata = finish;
      video.onerror = () => resolve([0, 0]);
      video.src = objectUrl;
    });
    video.removeAttribute("src");
    video.load();
    return dimensions[0] > 0 && dimensions[1] > 0 ? dimensions[0] / dimensions[1] : 0;
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
};

export const createUploadHandlers = ({  selectedElement,
  carouselElementTypes,
  defaultSiteChrome,
  builderAssetMimeTypes,
  builderAssetMaxBytes,
  builderVideoMimeTypes,
  builderVideoMaxBytes,
  builderDocumentMimeTypes,
  builderDocumentMaxBytes,
  uploadBuilderAsset,
  user,
  setAssetUploadBusy,
  updateSelectedElement,
  updateProject,
  showToast,
  parseCarouselSlides,
  serializeCarouselSlides,
  readMediaAspectRatio = readBuilderMediaAspectRatio,
}) => {
  const uploadBuilderImageFile = async (file) => {
    if (!file) return "";

    const allowedMimeType = typeof builderAssetMimeTypes.has === "function"
      ? builderAssetMimeTypes.has(file.type)
      : builderAssetMimeTypes.includes(file.type);

    if (!allowedMimeType) {
      showToast("Use a PNG, JPG, or WebP image.");
      return "";
    }

    if (file.size > builderAssetMaxBytes) {
      showToast("Image is too large. Use an image under 5 MB.");
      return "";
    }

    setAssetUploadBusy(true);

    try {
      const uploaded = await uploadBuilderAsset(file, user?.id);

      const url =
        (typeof uploaded === "string" ? uploaded : "") ||
        uploaded?.url ||
        uploaded?.assetUrl ||
        uploaded?.imageUrl ||
        uploaded?.fileUrl ||
        uploaded?.path ||
        uploaded?.data?.url ||
        uploaded?.data?.assetUrl ||
        uploaded?.data?.imageUrl ||
        uploaded?.data?.fileUrl ||
        uploaded?.asset?.url ||
        uploaded?.file?.url ||
        "";

      if (!url) {
        throw new Error("Upload did not return a URL.");
      }

      return url;
    } catch {
      if (import.meta.env.DEV) {
        console.error("Could not upload builder image.");
      }
      showToast("Image upload failed.");
      return "";
    } finally {
      setAssetUploadBusy(false);
    }
  };

  const handleSelectedElementImageUpload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !selectedElement || !["image", "imageButton"].includes(selectedElement.type)) return;

    const [assetUrl, aspectRatio] = await Promise.all([
      uploadBuilderImageFile(file),
      readMediaAspectRatio(file, "image"),
    ]);
    if (!assetUrl) return;

    updateSelectedElement({
      content: assetUrl,
      assetFileName: file.name || getBuilderAssetFileName(assetUrl),
      name: selectedElement.name || file.name || "Image",
      mediaAspectRatio: aspectRatio || selectedElement.mediaAspectRatio || undefined,
      ...(selectedElement.mode === "direct" && aspectRatio
        ? { position: fitMediaPositionsToAspectRatio(selectedElement.position, aspectRatio) }
        : {}),
    });

    showToast("Image uploaded.");
  };

  const handleSiteLogoUpload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    const assetUrl = await uploadBuilderImageFile(file);
    if (!assetUrl) return;

    updateProject((prev) => ({
      ...prev,
      siteChrome: {
        ...(prev.siteChrome || defaultSiteChrome),
        logoUrl: assetUrl,
      },
    }));

    showToast("Logo uploaded.");
  };

  const handleLoadingImageUpload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    const assetUrl = await uploadBuilderImageFile(file);
    if (!assetUrl) return;

    updateProject((prev) => ({
      ...prev,
      siteChrome: {
        ...defaultSiteChrome,
        ...(prev.siteChrome || {}),
        loadingImageUrl: assetUrl,
      },
    }));

    showToast("Loading image uploaded.");
  };

  const handleCarouselSlideImageUpload = async (event, slideIndex) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !selectedElement || !carouselElementTypes.has(selectedElement.type)) return;

    const assetUrl = await uploadBuilderImageFile(file);
    if (!assetUrl) return;

    const slides = parseCarouselSlides(selectedElement.content).map((slide, index) =>
      index === slideIndex ? { ...slide, image: assetUrl } : slide
    );

    updateSelectedElement({ content: serializeCarouselSlides(slides) });
    showToast("Carousel image uploaded.");
  };

  const handleSelectedElementVideoUpload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !selectedElement || selectedElement.type !== "video") return;

    if (!builderVideoMimeTypes.has(file.type)) {
      showToast("Use an MP4 or WebM video.");
      return;
    }
    if (file.size > builderVideoMaxBytes) {
      showToast("Video is too large. Use a video under 250 MB.");
      return;
    }

    setAssetUploadBusy(true);
    try {
      const [assetUrl, aspectRatio] = await Promise.all([
        uploadBuilderAsset(file, user?.id),
        readMediaAspectRatio(file, "video"),
      ]);
      if (!assetUrl) throw new Error("Upload did not return a URL.");
      updateSelectedElement({
        content: assetUrl,
        assetFileName: file.name || getBuilderAssetFileName(assetUrl),
        name: selectedElement.name || file.name || "Video",
        mediaAspectRatio: aspectRatio || selectedElement.mediaAspectRatio || undefined,
        ...(selectedElement.mode === "direct" && aspectRatio
          ? { position: fitMediaPositionsToAspectRatio(selectedElement.position, aspectRatio) }
          : {}),
      });
      showToast("Video uploaded.");
    } catch {
      showToast("Video upload failed.");
    } finally {
      setAssetUploadBusy(false);
    }
  };

  const handleSelectedElementDocumentUpload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !selectedElement || selectedElement.type !== "document") return;

    if (!builderDocumentMimeTypes.has(file.type)) {
      showToast("Use a PDF, DOC, or DOCX file.");
      return;
    }
    if (file.size > builderDocumentMaxBytes) {
      showToast("File is too large. Use a file under 50 MB.");
      return;
    }

    setAssetUploadBusy(true);
    try {
      const assetUrl = await uploadBuilderAsset(file, user?.id);
      if (!assetUrl) throw new Error("Upload did not return a URL.");
      updateSelectedElement({
        content: assetUrl,
        assetFileName: file.name || getBuilderAssetFileName(assetUrl),
        documentMimeType: file.type,
        name: selectedElement.name || file.name || "File Viewer",
      });
      showToast("File uploaded.");
    } catch {
      showToast("File upload failed.");
    } finally {
      setAssetUploadBusy(false);
    }
  };

  const uploadPhotoProofingFiles = async (files, { replaceCover = false } = {}) => {
    const selectedFiles = Array.from(files || []);
    if (!selectedFiles.length || !selectedElement || selectedElement.type !== "photoProofing") return;

    const uploadedPhotos = [];
    for (const file of selectedFiles) {
      const assetUrl = await uploadBuilderImageFile(file);
      if (!assetUrl) continue;
      const fileName = String(file.name || "").replace(/\.[^.]+$/, "").trim();
      uploadedPhotos.push({
        title: fileName || `Photo ${uploadedPhotos.length + 1}`,
        description: "",
        image: assetUrl,
      });
    }
    if (!uploadedPhotos.length) return;

    const currentPhotos = parsePhotoProofingContent(selectedElement.content);
    const nextPhotos = replaceCover
      ? [
          { ...uploadedPhotos[0], description: selectedElement.proofing?.description || currentPhotos[0]?.description || "" },
          ...currentPhotos.slice(1),
        ]
      : [...currentPhotos, ...uploadedPhotos];
    updateSelectedElement({ content: serializePhotoProofingContent(nextPhotos) });
    showToast(uploadedPhotos.length === 1 ? "Photo uploaded." : `${uploadedPhotos.length} photos uploaded.`);
  };

  const handlePhotoProofingImagesUpload = async (event, options) => {
    const files = event.target.files;
    event.target.value = "";
    await uploadPhotoProofingFiles(files, options);
  };

  return {
    handleSelectedElementImageUpload,
    handleSelectedElementVideoUpload,
    handleSelectedElementDocumentUpload,
    handleSiteLogoUpload,
    handleLoadingImageUpload,
    handleCarouselSlideImageUpload,
    handlePhotoProofingImagesUpload,
    uploadPhotoProofingFiles,
  };
};

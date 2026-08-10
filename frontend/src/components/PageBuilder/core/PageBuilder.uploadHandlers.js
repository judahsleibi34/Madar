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

export const createUploadHandlers = ({  selectedElement,
  carouselElementTypes,
  defaultSiteChrome,
  builderAssetMimeTypes,
  builderAssetMaxBytes,
  uploadBuilderAsset,
  user,
  setAssetUploadBusy,
  updateSelectedElement,
  updateProject,
  showToast,
  parseCarouselSlides,
  serializeCarouselSlides,
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
    if (!file || !selectedElement || selectedElement.type !== "image") return;

    const assetUrl = await uploadBuilderImageFile(file);
    if (!assetUrl) return;

    updateSelectedElement({
      content: assetUrl,
      assetFileName: file.name || getBuilderAssetFileName(assetUrl),
      name: selectedElement.name || file.name || "Image",
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
    handleSiteLogoUpload,
    handleLoadingImageUpload,
    handleCarouselSlideImageUpload,
    handlePhotoProofingImagesUpload,
    uploadPhotoProofingFiles,
  };
};

export const getBuilderAssetFileName = (value) => {
  const cleanValue = String(value || "").split(/[?#]/, 1)[0].replace(/\\/g, "/");
  const encodedName = cleanValue.slice(cleanValue.lastIndexOf("/") + 1);
  try {
    return decodeURIComponent(encodedName);
  } catch {
    return encodedName;
  }
};

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

  return {
    handleSelectedElementImageUpload,
    handleSiteLogoUpload,
    handleLoadingImageUpload,
    handleCarouselSlideImageUpload,
  };
};

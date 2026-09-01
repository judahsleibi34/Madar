import {
  Files,
  LayoutPanelTop,
  Palette,
} from "lucide-react";

import {
  elementTypes,
} from "./PageBuilder.constants";

export const designPanelOptions = [
  { id: "Pages", icon: Files, hint: "Manage pages" },
  { id: "Sections", icon: LayoutPanelTop, hint: "Build with components" },
  { id: "Themes", icon: Palette, hint: "Whole website styles" },
];

export const elementGroups = [...new Set(elementTypes.map((item) => item.group))];

export const carouselElementTypes = new Set([
  "card",
  "carousel",
  "logoSlider",
  "carouselCards",
  "carouselSplit",
  "carouselSpotlight",
  "carouselStack",
  "carouselEditorial",
  "circularGallery",
]);

export const builderAssetMaxBytes = 25 * 1024 * 1024;

export const builderAssetMimeTypes = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
]);

export const builderVideoMaxBytes = 250 * 1024 * 1024;

export const builderVideoMimeTypes = new Set([
  "video/mp4",
  "video/webm",
]);

export const builderDocumentMaxBytes = 50 * 1024 * 1024;

export const builderDocumentMimeTypes = new Set([
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]);

export const builderInitialProjectLoadPromises = new Map();

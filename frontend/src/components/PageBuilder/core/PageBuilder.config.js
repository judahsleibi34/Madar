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
  { id: "Themes", icon: Palette, hint: "Builder themes only" },
];

export const elementGroups = [...new Set(elementTypes.map((item) => item.group))];

export const carouselElementTypes = new Set([
  "card",
  "carousel",
  "carouselCards",
  "carouselSplit",
  "carouselSpotlight",
  "carouselStack",
  "carouselEditorial",
  "circularGallery",
]);

export const builderAssetMaxBytes = 5 * 1024 * 1024;

export const builderAssetMimeTypes = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
]);

export const builderInitialProjectLoadPromises = new Map();

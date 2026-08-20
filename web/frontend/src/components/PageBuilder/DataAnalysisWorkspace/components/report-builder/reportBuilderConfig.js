import { BarChart3, FileText, Heading, Image, LayoutDashboard, Minus, Table2 } from "lucide-react";

export const REPORT_BLOCK_DRAG_TYPE = "application/x-madar-report-block";

export const reportBlockTypes = [
  { type: "heading", label: "Heading", description: "Section title.", icon: Heading },
  { type: "text", label: "Text", description: "Notes or findings.", icon: FileText },
  { type: "spacer", label: "Space", description: "Blank space between items.", icon: Minus },
  { type: "image", label: "Image", description: "Logo, photo, or attachment.", icon: Image },
  { type: "metric", label: "Key number", description: "Report variable.", icon: LayoutDashboard },
  { type: "chart", label: "Chart", description: "Saved chart.", icon: BarChart3 },
  { type: "table", label: "Table", description: "Saved table.", icon: Table2 },
];

export const reportBlockDefaults = {
  heading: { title: "Section heading", body: "" },
  text: { title: "Text block", body: "Write here." },
  spacer: { title: "Space", body: "", spacerHeight: 40 },
  image: { title: "Image", body: "", src: "" },
  metric: { title: "Metric", body: "Select a saved number." },
  chart: { title: "Chart", body: "Select a saved chart." },
  table: { title: "Table", body: "Select a saved table." },
};

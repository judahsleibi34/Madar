import { BarChart3, FileText, Heading, Image, LayoutDashboard, Minus, Table2 } from "lucide-react";

export const REPORT_BLOCK_DRAG_TYPE = "application/x-madar-report-block";

export const reportBlockTypes = [
  { type: "heading", label: "Heading", description: "Introduce a report section.", icon: Heading },
  { type: "text", label: "Text", description: "Write context, notes, or findings.", icon: FileText },
  { type: "spacer", label: "Space", description: "Add adjustable blank space between items.", icon: Minus },
  { type: "image", label: "Image", description: "Insert an image into the document.", icon: Image },
  { type: "metric", label: "Key number", description: "Show a total, average, rate, or other result.", icon: LayoutDashboard },
  { type: "chart", label: "Chart", description: "Show a generated visualization.", icon: BarChart3 },
  { type: "table", label: "Table", description: "Show detailed results in rows and columns.", icon: Table2 },
];

export const reportBlockDefaults = {
  heading: { title: "Section heading", body: "" },
  text: { title: "Text block", body: "Write your report content here." },
  spacer: { title: "Space", body: "", spacerHeight: 40 },
  image: { title: "Image", body: "", src: "" },
  metric: { title: "Metric", body: "Select a backend metric later." },
  chart: { title: "Chart", body: "Chart configuration will appear here." },
  table: { title: "Table", body: "Table configuration will appear here." },
};

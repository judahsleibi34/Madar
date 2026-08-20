export const fallbackSlides = [
  {
    title: "Design pages",
    description: "Build flexible page sections and arrange content visually.",
    image: "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1800&q=90&auto=format&fit=crop",
  },
  {
    title: "Collect responses",
    description: "Create forms and keep structured requests in one workspace.",
    image: "https://images.unsplash.com/photo-1556761175-b413da4baf72?w=1800&q=90&auto=format&fit=crop",
  },
  {
    title: "Manage operations",
    description: "Coordinate reservations, users, and daily work from one place.",
    image: "https://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=1800&q=90&auto=format&fit=crop",
  },
];

export const getHighQualityCarouselImageUrl = (value = "") => {
  const source = String(value || "").trim();
  if (!source) return "";

  try {
    const url = new URL(source);
    if (url.hostname !== "images.unsplash.com") return source;

    const requestedWidth = Number(url.searchParams.get("w")) || 0;
    if (requestedWidth < 1800) url.searchParams.set("w", "1800");
    url.searchParams.set("q", "90");
    return url.toString();
  } catch {
    return source;
  }
};

export const parseCarouselSlides = (content = "") => {
  const blocks = String(content || "")
    .split(/\n\s*\n/g)
    .filter((block) => /\S/.test(block));

  const slides = blocks.map((block) => {
    const lines = block.split("\n").map((line) => line.replace(/\r/g, ""));
    if (lines.length >= 5) {
      return { title: lines[0] || "", description: lines[1] || "", image: lines[4] || "" };
    }
    const [title = "", description = "", image = ""] = lines;
    return { title, description, image };
  });

  return slides.length > 0 ? slides : fallbackSlides;
};

export const serializeCarouselSlides = (slides = []) =>
  slides
    .map((slide) => [slide.title || "", slide.description || "", slide.image || ""].join("\n"))
    .join("\n\n");

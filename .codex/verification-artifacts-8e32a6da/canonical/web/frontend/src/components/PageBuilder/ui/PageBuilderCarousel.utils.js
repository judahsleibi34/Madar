export const fallbackSlides = [
  {
    title: "Design pages",
    description: "Build flexible page sections and arrange content visually.",
    image: "",
  },
  {
    title: "Collect responses",
    description: "Create forms and keep structured requests in one workspace.",
    image: "",
  },
  {
    title: "Manage operations",
    description: "Coordinate reservations, users, and daily work from one place.",
    image: "",
  },
];

export const getHighQualityCarouselImageUrl = (value = "") => String(value || "").trim();

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

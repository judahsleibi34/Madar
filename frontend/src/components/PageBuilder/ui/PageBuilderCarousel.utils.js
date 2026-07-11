const fallbackSlides = [
  {
    title: "Launch faster",
    description: "Showcase products, services, or featured content with a clean carousel.",
    image: "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&auto=format&fit=crop",
  },
  {
    title: "Collect attention",
    description: "Use large visuals, concise copy, and simple navigation for high-impact sections.",
    image: "https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=1200&auto=format&fit=crop",
  },
  {
    title: "Stay flexible",
    description: "Edit slide text and image URLs directly from the Page Builder inspector.",
    image: "https://images.unsplash.com/photo-1556761175-b413da4baf72?w=1200&auto=format&fit=crop",
  },
];

export const parseCarouselSlides = (content = "") => {
  const blocks = String(content || "")
    .split(/\n\s*\n/g)
    .filter((block) => /\S/.test(block));

  const slides = blocks.map((block) => {
    const [title = "", description = "", image = ""] = block
      .split("\n")
      .map((line) => line.replace(/\r/g, ""));

    return { title, description, image };
  });

  return slides.length > 0 ? slides : fallbackSlides;
};

export const serializeCarouselSlides = (slides = []) =>
  slides
    .map((slide) => [slide.title || "", slide.description || "", slide.image || ""].join("\n"))
    .join("\n\n");

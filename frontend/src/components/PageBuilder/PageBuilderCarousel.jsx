import { useEffect, useMemo, useState } from "react";
import "./PageBuilderCarousel.css";

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

const parseSlides = (content = "") => {
  const blocks = String(content || "")
    .split(/\n\s*\n/g)
    .map((block) => block.trim())
    .filter(Boolean);

  const slides = blocks.map((block) => {
    const [title = "", description = "", image = ""] = block
      .split("\n")
      .map((line) => line.trim());

    return { title, description, image };
  });

  return slides.length > 0 ? slides : fallbackSlides;
};

export default function PageBuilderCarousel({
  autoScroll = false,
  autoScrollMs = 4000,
  content,
  name = "Carousel",
  variant = "hero",
}) {
  const slides = useMemo(() => parseSlides(content), [content]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [rotation, setRotation] = useState(0);
  const [dragStart, setDragStart] = useState(null);

  const activeSlide = slides[activeIndex] || slides[0];
  const variantClass = `carousel-variant-${String(variant || "hero").replace(/[^a-zA-Z0-9-]/g, "")}`;
  const safeAutoScrollMs = Math.max(1000, Number(autoScrollMs) || 4000);

  const goToSlide = (direction) => {
    setActiveIndex((current) => {
      const nextIndex = current + direction;
      if (nextIndex < 0) return slides.length - 1;
      if (nextIndex >= slides.length) return 0;
      return nextIndex;
    });
  };

  useEffect(() => {
    if (!autoScroll || slides.length <= 1 || dragStart) return undefined;

    const interval = window.setInterval(() => {
      if (variant === "circular") {
        setRotation((current) => current - 360 / slides.length);
      }

      setActiveIndex((current) => (current + 1) % slides.length);
    }, safeAutoScrollMs);

    return () => window.clearInterval(interval);
  }, [autoScroll, dragStart, safeAutoScrollMs, slides.length, variant]);

  const handleGalleryPointerDown = (event) => {
    event.currentTarget.setPointerCapture?.(event.pointerId);
    setDragStart({ x: event.clientX, rotation });
  };

  const handleGalleryPointerMove = (event) => {
    if (!dragStart) return;
    setRotation(dragStart.rotation + (event.clientX - dragStart.x) * 0.35);
  };

  const handleGalleryPointerUp = () => {
    setDragStart(null);
  };

  if (variant === "circular") {
    const itemCount = Math.max(slides.length, 1);

    return (
      <div className={`page-builder-carousel ${variantClass}`} aria-label={name}>
        <div className="circular-gallery-header">
          <span>{name}</span>
          <strong>Drag to rotate</strong>
        </div>

        <div
          className={`circular-gallery-stage ${dragStart ? "is-dragging" : ""}`}
          onPointerDown={handleGalleryPointerDown}
          onPointerMove={handleGalleryPointerMove}
          onPointerUp={handleGalleryPointerUp}
          onPointerCancel={handleGalleryPointerUp}
        >
          <div className="circular-gallery-ring" style={{ transform: `rotateY(${rotation}deg)` }}>
            {slides.map((slide, index) => {
              const angle = (360 / itemCount) * index;

              return (
                <button
                  type="button"
                  className="circular-gallery-item"
                  key={`${slide.title}_${index}`}
                  style={{ transform: `rotateY(${angle}deg) translateZ(var(--gallery-depth, 360px))` }}
                  onClick={() => setActiveIndex(index)}
                  aria-label={`Open ${slide.title || `image ${index + 1}`}`}
                >
                  {slide.image && <img src={slide.image} alt={slide.title || name} />}
                  <span>{String(index + 1).padStart(3, "0")}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="circular-gallery-caption">
          <strong>{activeSlide.title}</strong>
          <p>{activeSlide.description}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`page-builder-carousel ${variantClass}`} aria-label={name}>
      <div className="carousel-stage">
        {activeSlide.image && (
          <img src={activeSlide.image} alt={activeSlide.title || name} />
        )}

        <div className="carousel-copy">
          <span>{activeIndex + 1} / {slides.length}</span>
          <h3>{activeSlide.title}</h3>
          <p>{activeSlide.description}</p>
        </div>
      </div>

      <div className="carousel-controls">
        <button type="button" onClick={() => goToSlide(-1)} aria-label="Previous slide">
          Prev
        </button>

        <div className="carousel-dots" aria-label="Carousel slides">
          {slides.map((slide, index) => (
            <button
              type="button"
              key={`${slide.title}_${index}`}
              className={index === activeIndex ? "active" : ""}
              onClick={() => setActiveIndex(index)}
              aria-label={`Open slide ${index + 1}`}
            />
          ))}
        </div>

        <button type="button" onClick={() => goToSlide(1)} aria-label="Next slide">
          Next
        </button>
      </div>
    </div>
  );
}

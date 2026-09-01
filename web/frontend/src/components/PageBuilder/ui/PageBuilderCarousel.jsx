import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { getResponsiveMediaProps } from "../../../utils/media";
import {
  getHighQualityCarouselImageUrl,
  parseCarouselSlides,
} from "./PageBuilderCarousel.utils";
import "./PageBuilderCarousel.css";

const getVisibleProducts = (products, startIndex, count) =>
  Array.from({ length: Math.min(count, products.length) }, (_, offset) => ({
    ...products[(startIndex + offset) % products.length],
    sourceIndex: (startIndex + offset) % products.length,
  }));

const getLogoFallback = (title = "") =>
  String(title || "Partner")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

export default function PageBuilderCarousel({
  autoScroll = false,
  autoScrollMs = 4000,
  content,
  logoSliderSubtitle = "",
  logoSliderTitle = "",
  name = "Card Carousel",
  variant = "cards",
}) {
  const products = useMemo(() => parseCarouselSlides(content), [content]);
  const [startIndex, setStartIndex] = useState(0);
  const safeAutoScrollMs = Math.max(1000, Number(autoScrollMs) || 4000);
  const isLogoSlider = variant === "logos";
  const visibleProducts = getVisibleProducts(products, startIndex, 5);
  const itemLabel = isLogoSlider ? "partners" : "products";

  const move = useCallback((direction) => {
    setStartIndex((current) => (current + direction + products.length) % products.length);
  }, [products.length]);

  useEffect(() => {
    if (!autoScroll || products.length <= 1) return undefined;
    const interval = window.setInterval(() => move(1), safeAutoScrollMs);
    return () => window.clearInterval(interval);
  }, [autoScroll, products.length, safeAutoScrollMs, move]);

  return (
    <section
      className={`page-builder-carousel workspace-card-carousel ${isLogoSlider ? "is-logo-slider" : ""}`}
      aria-label={logoSliderTitle || name}
    >
      {isLogoSlider && (logoSliderTitle || logoSliderSubtitle) ? (
        <header className="logo-slider-heading">
          {logoSliderTitle ? <h2>{logoSliderTitle}</h2> : null}
          {logoSliderSubtitle ? <p>{logoSliderSubtitle}</p> : null}
        </header>
      ) : null}

      <div className="product-carousel-rail">
        <button
          type="button"
          className="product-carousel-arrow is-previous"
          onClick={() => move(-1)}
          aria-label={`Previous ${itemLabel}`}
          disabled={products.length <= 1}
        >
          <ChevronLeft size={24} aria-hidden="true" />
        </button>

        <div className={isLogoSlider ? "product-carousel-grid logo-slider-grid" : "product-carousel-grid"}>
          {visibleProducts.map((product) => {
            const responsiveImageProps = getResponsiveMediaProps(product.image, {
              sizes: isLogoSlider
                ? "(max-width: 720px) 42vw, 16vw"
                : "(max-width: 720px) 86vw, 20vw",
            });
            const imageProps = responsiveImageProps.srcSet
              ? responsiveImageProps
              : { src: getHighQualityCarouselImageUrl(responsiveImageProps.src) };
            const imageUrl = imageProps.src;

            if (isLogoSlider) {
              return (
                <article
                  className="product-carousel-card logo-slider-card"
                  key={`${product.sourceIndex}_${product.title}`}
                  aria-label={product.title || `Partner ${product.sourceIndex + 1}`}
                >
                  {imageUrl ? (
                    <img
                      {...imageProps}
                      alt={product.title || "Partner logo"}
                      decoding="async"
                    />
                  ) : (
                    <span className="logo-slider-fallback" aria-hidden="true">
                      {getLogoFallback(product.title)}
                    </span>
                  )}
                  {product.title ? <span className="logo-slider-name">{product.title}</span> : null}
                </article>
              );
            }

            return (
              <article className="product-carousel-card" key={`${product.sourceIndex}_${product.title}`}>
                <div className="product-carousel-image">
                  {imageUrl ? (
                    <img
                      {...imageProps}
                      alt={product.title || "Featured product"}
                      decoding="async"
                    />
                  ) : (
                    <span>Add image</span>
                  )}
                </div>
                <h3>{product.title}</h3>
                {product.description ? <p>{product.description}</p> : null}
              </article>
            );
          })}
        </div>

        <button
          type="button"
          className="product-carousel-arrow is-next"
          onClick={() => move(1)}
          aria-label={`Next ${itemLabel}`}
          disabled={products.length <= 1}
        >
          <ChevronRight size={24} aria-hidden="true" />
        </button>
      </div>

      {!isLogoSlider ? (
        <div className="product-carousel-dots" aria-label="Product pages">
          {products.map((product, index) => (
            <button
              type="button"
              key={`${product.title}_${index}`}
              className={`product-carousel-dot ${index === startIndex ? "is-active" : ""}`}
              onClick={() => setStartIndex(index)}
              aria-label={`Show products from item ${index + 1}`}
            />
          ))}
        </div>
      ) : null}
    </section>
  );
}

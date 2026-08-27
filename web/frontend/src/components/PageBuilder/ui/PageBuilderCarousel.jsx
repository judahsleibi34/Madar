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

export default function PageBuilderCarousel({
  autoScroll = false,
  autoScrollMs = 4000,
  content,
  name = "Card Carousel",
}) {
  const products = useMemo(() => parseCarouselSlides(content), [content]);
  const [startIndex, setStartIndex] = useState(0);
  const safeAutoScrollMs = Math.max(1000, Number(autoScrollMs) || 4000);
  const visibleProducts = getVisibleProducts(products, startIndex, 5);

  const move = useCallback((direction) => {
    setStartIndex((current) => (current + direction + products.length) % products.length);
  }, [products.length]);

  useEffect(() => {
    if (!autoScroll || products.length <= 1) return undefined;
    const interval = window.setInterval(() => move(1), safeAutoScrollMs);
    return () => window.clearInterval(interval);
  }, [autoScroll, products.length, safeAutoScrollMs, move]);

  return (
    <section className="page-builder-carousel workspace-card-carousel" aria-label={name}>
      <div className="product-carousel-rail">
        <button type="button" className="product-carousel-arrow is-previous" onClick={() => move(-1)} aria-label="Previous products">
          <ChevronLeft size={24} aria-hidden="true" />
        </button>

        <div className="product-carousel-grid">
          {visibleProducts.map((product) => {
            const responsiveImageProps = getResponsiveMediaProps(product.image, {
              sizes: "(max-width: 720px) 86vw, 20vw",
            });
            const imageProps = responsiveImageProps.srcSet
              ? responsiveImageProps
              : { src: getHighQualityCarouselImageUrl(responsiveImageProps.src) };
            const imageUrl = imageProps.src;
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

        <button type="button" className="product-carousel-arrow is-next" onClick={() => move(1)} aria-label="Next products">
          <ChevronRight size={24} aria-hidden="true" />
        </button>
      </div>

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
    </section>
  );
}

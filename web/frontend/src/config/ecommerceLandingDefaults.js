export const DEMO_LANDING_SLIDES = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    image_url: "/demo/landing/editorial-essentials.webp",
    title_en: "Everyday, elevated.",
    title_ar: "أناقة يومية، بتفاصيل أرقى.",
    subtitle_en: "Relaxed silhouettes and thoughtful essentials designed to move with you.",
    subtitle_ar: "قصّات مريحة وقطع أساسية مصممة لترافقك في كل يوم.",
  },
  {
    id: "22222222-2222-4222-8222-222222222222",
    image_url: "/demo/landing/city-layers.webp",
    title_en: "Made for city days.",
    title_ar: "إطلالات صُممت للمدينة.",
    subtitle_en: "Easy layers, timeless denim, and confident style for wherever the day leads.",
    subtitle_ar: "طبقات عملية ودنيم خالد وأناقة واثقة لكل تفاصيل يومك.",
  },
  {
    id: "33333333-3333-4333-8333-333333333333",
    image_url: "/demo/landing/finishing-touches.webp",
    title_en: "The finishing touch.",
    title_ar: "تفاصيل تكمل إطلالتك.",
    subtitle_en: "Considered accessories and refined textures that make every look your own.",
    subtitle_ar: "إكسسوارات منتقاة وخامات راقية تمنح كل إطلالة طابعك الخاص.",
  },
];

export function createDemoLandingSlides() {
  return DEMO_LANDING_SLIDES.map((slide) => ({ ...slide }));
}

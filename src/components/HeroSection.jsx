const content = {
  en: {
    title: "About Madar",
    name: "Madar",
    description:
      "is a flexible digital management platform that helps businesses, stores, and clinics manage their daily operations from one place through a customizable system that combines simplicity, efficiency, and local identity.",
  },
  ar: {
    title: "عن مدار",
    name: "مدار",
    description:
      "منصة إدارة رقمية مرنة تساعد الشركات والمتاجر والعيادات على إدارة عملياتها اليومية من مكان واحد من خلال نظام قابل للتخصيص يجمع بين البساطة والكفاءة والهوية المحلية.",
  },
};

export default function HeroSection({ lang }) {
  const t = content[lang];

  return (
    <section id="about" className="hero-section">
      <h1 className="hero-title">{t.title}</h1>
      <p className="hero-description">
        <span className="arabic-name">{t.name}</span> {t.description}
      </p>
    </section>
  );
}
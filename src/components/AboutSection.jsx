import FadeIn from "./FadeIn";

const content = {
  en: {
    title: "About Madar",
    name: "Madar",
    description:
      "is an adaptive business management platform built by Palestinian youth to help organizations create digital systems that fit their real needs. It gives businesses a flexible way to manage records, users, operations, and workflows from one centralized place.",
    secondDescription:
      "Whether used by a store, clinic, supermarket, warehouse, school, or service center, Madar adapts to the way each organization works. With simplicity, flexibility, and local identity at its core, Madar helps businesses move from paper records and scattered tools to a smarter digital management experience.",

    purposeTitle: "Our Purpose",
    purpose:
      "Madar was created to support small and medium organizations that need simple, affordable, and flexible digital tools. Our purpose is to make business management easier by giving each organization the ability to shape its own system instead of being forced to use a fixed solution.",

    differenceTitle: "What Makes Madar Different?",
    difference:
      "Madar is not limited to one industry. It is designed as a customizable platform where organizations can define their own structure, modules, fields, records, permissions, and workflows while keeping a clean and consistent user experience.",

    visionTitle: "Our Vision",
    vision:
      "Our vision is to build a trusted Palestinian-made digital platform that helps organizations become more organized, efficient, and ready for growth. Madar aims to be a flexible foundation for businesses that want technology shaped around their real operations.",
  },

  ar: {
    title: "عن مدار",
    name: "مدار",
    description:
      "منصة إدارة أعمال تكيفية بُنيت بأيادٍ شبابية فلسطينية لمساعدة المؤسسات على إنشاء أنظمة رقمية تناسب احتياجاتها الفعلية. توفر المنصة طريقة مرنة لإدارة السجلات والمستخدمين والعمليات وسير العمل من مكان مركزي واحد.",
    secondDescription:
      "سواء تم استخدام مدار في متجر أو عيادة أو سوبرماركت أو مستودع أو مدرسة أو مركز خدمات، فهو يتكيف مع طريقة عمل كل مؤسسة. ومن خلال التركيز على البساطة والمرونة والهوية المحلية، يساعد مدار الأعمال على الانتقال من السجلات الورقية والأدوات المتفرقة إلى تجربة إدارة رقمية أكثر ذكاءً.",

    purposeTitle: "هدفنا",
    purpose:
      "تم إنشاء مدار لدعم المؤسسات الصغيرة والمتوسطة التي تحتاج إلى أدوات رقمية بسيطة ومرنة ومناسبة. هدفنا هو تسهيل إدارة الأعمال من خلال منح كل مؤسسة القدرة على تشكيل نظامها الخاص بدلًا من الاعتماد على حلول ثابتة لا تناسب طبيعة عملها.",

    differenceTitle: "ما الذي يجعل مدار مختلفًا؟",
    difference:
      "مدار ليس مخصصًا لمجال واحد فقط، بل هو منصة قابلة للتخصيص تتيح للمؤسسات تحديد هيكلها الخاص، وإنشاء الوحدات والحقول والسجلات والصلاحيات وسير العمل، مع الحفاظ على تجربة استخدام واضحة ومتناسقة.",

    visionTitle: "رؤيتنا",
    vision:
      "رؤيتنا هي بناء منصة رقمية فلسطينية موثوقة تساعد المؤسسات على أن تصبح أكثر تنظيمًا وكفاءة واستعدادًا للنمو. يهدف مدار إلى أن يكون أساسًا مرنًا للأعمال التي تحتاج إلى تقنية مصممة حول عملياتها الفعلية.",
  },
};

export default function AboutSection({ lang }) {
  const t = content[lang];

  return (
    <section id="about" className="about-section">
      <FadeIn delay={0}>
        <h1 className="hero-title">{t.title}</h1>
      </FadeIn>

      <FadeIn delay={0.15}>
        <p className="hero-description">
          <span className="arabic-name">{t.name}</span> {t.description}
        </p>
      </FadeIn>

      <FadeIn delay={0.25}>
        <p className="hero-description">{t.secondDescription}</p>
      </FadeIn>

      <FadeIn delay={0.35}>
        <h2 className="hero-subtitle">{t.purposeTitle}</h2>
        <p className="hero-description">{t.purpose}</p>
      </FadeIn>

      <FadeIn delay={0.45}>
        <h2 className="hero-subtitle">{t.differenceTitle}</h2>
        <p className="hero-description">{t.difference}</p>
      </FadeIn>

      <FadeIn delay={0.55}>
        <h2 className="hero-subtitle">{t.visionTitle}</h2>
        <p className="hero-description">{t.vision}</p>
      </FadeIn>
    </section>
  );
}
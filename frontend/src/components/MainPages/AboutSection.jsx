import FadeIn from "../Animations/FadeIn";
import GradientText from "../Animations/GradientText";
import SplitText from "../Animations/SplitText";

const content = {
  en: {
    title: "About Madar",
    name: "Madar",
    description:
      "helps organizations move beyond manual paperwork by turning daily operations into reliable digital workflows. From records and users to approvals and processes, Madar gives teams one organized platform to manage work with more clarity, speed, and control.",
    secondDescription:
      "Built for businesses that want to modernize without complexity, Madar adapts to different sectors such as stores, clinics, supermarkets, warehouses, schools, and service centers. It brings everything together in one simple experience, helping teams save time, reduce operational errors, and keep work moving smoothly.",

    purposeTitle: "Our Purpose",
    purpose:
      "Our purpose is to make digital transformation practical and accessible for small and medium organizations. Madar gives each business the flexibility to build a system around the way it actually works, instead of forcing teams into rigid tools that do not match their operations.",

    differenceTitle: "What Makes Madar Different?",
    difference:
      "Madar is designed to be flexible from the start. Organizations can customize modules, fields, records, permissions, users, and workflows while keeping a clean, professional, and easy-to-use experience. It is not just software; it is a foundation for better business control.",

    visionTitle: "Our Vision",
    vision:
      "Our vision is to become a trusted digital transformation platform for organizations that want to work smarter, grow faster, and operate with confidence. Madar aims to help businesses replace scattered paperwork with a modern system built for clarity, efficiency, and long-term growth.",
  },

  ar: {
    title: "عن مدار",
    name: "مدار",
    description:
      "يساعد المؤسسات على تجاوز العمل الورقي اليدوي من خلال تحويل العمليات اليومية إلى سير عمل رقمي موثوق. من السجلات والمستخدمين إلى الموافقات والإجراءات، يمنح مدار الفرق منصة واحدة منظمة لإدارة العمل بوضوح وسرعة وتحكم أفضل.",
    secondDescription:
      "صُمم مدار للأعمال التي ترغب في التطور الرقمي دون تعقيد، ويتناسب مع قطاعات مختلفة مثل المتاجر والعيادات والسوبرماركت والمستودعات والمدارس ومراكز الخدمات. يجمع مدار كل ما تحتاجه المؤسسة في تجربة بسيطة تساعد الفرق على توفير الوقت، وتقليل الأخطاء التشغيلية، والحفاظ على سير العمل بسلاسة.",

    purposeTitle: "هدفنا",
    purpose:
      "هدفنا هو جعل التحول الرقمي عمليًا ومتاحًا للمؤسسات الصغيرة والمتوسطة. يمنح مدار كل مؤسسة المرونة لبناء نظام يناسب طريقة عملها الفعلية، بدلًا من الاعتماد على أدوات جامدة لا تعكس احتياجاتها اليومية.",

    differenceTitle: "ما الذي يجعل مدار مختلفًا؟",
    difference:
      "تم تصميم مدار ليكون مرنًا من البداية. تستطيع المؤسسات تخصيص الوحدات والحقول والسجلات والصلاحيات والمستخدمين وسير العمل مع الحفاظ على تجربة استخدام واضحة واحترافية وسهلة. مدار ليس مجرد برنامج، بل أساس يمنح الأعمال تحكمًا أفضل.",

    visionTitle: "رؤيتنا",
    vision:
      "رؤيتنا هي أن يصبح مدار منصة موثوقة للتحول الرقمي للمؤسسات التي تريد العمل بذكاء أكبر، والنمو بسرعة، والإدارة بثقة. نهدف إلى مساعدة الأعمال على استبدال الأوراق والأدوات المتفرقة بنظام حديث مصمم للوضوح والكفاءة والنمو طويل المدى.",
  },
};

export default function AboutSection({ lang }) {
  const t = content[lang];

  return (
    <section id="about" className="about-section">
      <FadeIn delay={0}>
        <h1 className="hero-title">
          {lang === "en" ? <>About <GradientText pauseOnHover>Madar</GradientText></> : <GradientText pauseOnHover>{t.title}</GradientText>}
        </h1>
      </FadeIn>

      <FadeIn delay={0.15}>
        <p className="hero-description">
          <SplitText className="arabic-name">{t.name}</SplitText> {t.description}
        </p>
      </FadeIn>

      <FadeIn delay={0.25}>
        <p className="hero-description">{t.secondDescription}</p>
      </FadeIn>

      <FadeIn delay={0.35}>
        <h2 className="hero-subtitle"><GradientText pauseOnHover>{t.purposeTitle}</GradientText></h2>
        <p className="hero-description">{t.purpose}</p>
      </FadeIn>

      <FadeIn delay={0.45}>
        <h2 className="hero-subtitle"><GradientText pauseOnHover>{t.differenceTitle}</GradientText></h2>
        <p className="hero-description">{t.difference}</p>
      </FadeIn>

      <FadeIn delay={0.55}>
        <h2 className="hero-subtitle"><GradientText pauseOnHover>{t.visionTitle}</GradientText></h2>
        <p className="hero-description">{t.vision}</p>
      </FadeIn>
    </section>
  );
}

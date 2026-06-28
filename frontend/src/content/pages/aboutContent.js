export const aboutContent = {
  en: {
    hero: {
      title: "About Madar",
      titlePrefix: "About",
      titleHighlight: "Madar",
      name: "Madar",
      description:
        "helps organizations move beyond manual paperwork by turning daily operations into reliable digital workflows. From records and users to approvals and processes, Madar gives teams one organized platform to manage work with more clarity, speed, and control.",
      secondDescription:
        "Built for businesses that want to modernize without complexity, Madar adapts to different sectors such as stores, clinics, supermarkets, warehouses, schools, and service centers. It brings everything together in one simple experience, helping teams save time, reduce operational errors, and keep work moving smoothly.",
    },
    sections: [
      {
        title: "Our Purpose",
        body:
          "Our purpose is to make digital transformation practical and accessible for small and medium organizations. Madar gives each business the flexibility to build a system around the way it actually works, instead of forcing teams into rigid tools that do not match their operations.",
      },
      {
        title: "What Makes Madar Different?",
        body:
          "Madar is designed to be flexible from the start. Organizations can customize modules, fields, records, permissions, users, and workflows while keeping a clean, professional, and easy-to-use experience. It is not just software; it is a foundation for better business control.",
      },
      {
        title: "Our Vision",
        body:
          "Our vision is to become a trusted digital transformation platform for organizations that want to work smarter, grow faster, and operate with confidence. Madar aims to help businesses replace scattered paperwork with a modern system built for clarity, efficiency, and long-term growth.",
      },
    ],
  },

  ar: {
    hero: {
      title: "عن مدار",
      titlePrefix: "",
      titleHighlight: "عن مدار",
      name: "مدار",
      description:
        "يساعد المؤسسات على تجاوز العمل الورقي اليدوي من خلال تحويل العمليات اليومية إلى تدفقات عمل رقمية موثوقة. من السجلات والمستخدمين إلى الموافقات والإجراءات، يمنح مدار الفرق منصة واحدة منظمة لإدارة العمل بوضوح وسرعة وتحكم أفضل.",
      secondDescription:
        "صُمم مدار للأعمال التي ترغب في التطور الرقمي دون تعقيد، ويتناسب مع قطاعات مختلفة مثل المتاجر والعيادات والسوبرماركت والمستودعات والمدارس ومراكز الخدمات. يجمع مدار كل ما تحتاجه المؤسسة في تجربة بسيطة تساعد الفرق على توفير الوقت، وتقليل الأخطاء التشغيلية، والحفاظ على سير العمل بسلاسة.",
    },
    sections: [
      {
        title: "هدفنا",
        body:
          "هدفنا هو جعل التحول الرقمي عملياً ومتاحاً للمؤسسات الصغيرة والمتوسطة. يمنح مدار كل مؤسسة المرونة لبناء نظام يناسب طريقة عملها الفعلية، بدلاً من الاعتماد على أدوات جامدة لا تعكس احتياجاتها اليومية.",
      },
      {
        title: "ما الذي يجعل مدار مختلفاً؟",
        body:
          "تم تصميم مدار ليكون مرناً من البداية. تستطيع المؤسسات تخصيص الوحدات والحقول والسجلات والصلاحيات والمستخدمين وسير العمل مع الحفاظ على تجربة استخدام واضحة واحترافية وسهلة. مدار ليس مجرد برنامج، بل أساس يمنح الأعمال تحكماً أفضل.",
      },
      {
        title: "رؤيتنا",
        body:
          "رؤيتنا هي أن يصبح مدار منصة موثوقة للتحول الرقمي للمؤسسات التي تريد العمل بذكاء أكبر، والنمو بسرعة، والإدارة بثقة. نهدف إلى مساعدة الأعمال على استبدال الأوراق والأدوات المتفرقة بنظام حديث مصمم للوضوح والكفاءة والنمو طويل المدى.",
      },
    ],
  },
};

export const getAboutContent = (lang = "en") =>
  aboutContent[lang === "ar" ? "ar" : "en"];

import judahImage from "../../assets/TeamInformation/Judah.jpg";
import judahCv from "../../assets/TeamInformation/Judah_Sleibi_CV.pdf";
import salibaCv from "../../assets/TeamInformation/SalibaRishmawiCV.pdf";
import salibaImage from "../../assets/TeamInformation/Saliba.jpeg";

const judahLinksEn = [
  {
    label: "LinkedIn",
    type: "linkedin",
    href: "https://www.linkedin.com/in/judah-sleibi-b8578b321",
  },
  {
    label: "GitHub",
    type: "github",
    href: "https://github.com/judahsleibi34",
  },
  {
    label: "CV",
    type: "cv",
    href: judahCv,
  },
  {
    label: "Email",
    type: "email",
    href: "mailto:judahsleibi34@gmail.com",
  },
  {
    label: "Phone",
    type: "phone",
    href: "tel:+972599203857",
  },
];

const judahLinksAr = [
  {
    label: "لينكدإن",
    type: "linkedin",
    href: "https://www.linkedin.com/in/judah-sleibi-b8578b321",
  },
  {
    label: "GitHub",
    type: "github",
    href: "https://github.com/judahsleibi34",
  },
  {
    label: "السيرة الذاتية",
    type: "cv",
    href: judahCv,
  },
  {
    label: "البريد الإلكتروني",
    type: "email",
    href: "mailto:judahsleibi34@gmail.com",
  },
  {
    label: "الهاتف",
    type: "phone",
    href: "tel:+972599203857",
  },
];

const salibaLinksEn = [
  {
    label: "LinkedIn",
    type: "linkedin",
    href: "https://www.linkedin.com/in/saliba-rishmawi/",
  },
  {
    label: "GitHub",
    type: "github",
    href: "https://github.com/Saliba-codes",
  },
  {
    label: "CV",
    type: "cv",
    href: salibaCv,
  },
  {
    label: "Email",
    type: "email",
    href: "mailto:rishmawisaliba12@gmail.com",
  },
  {
    label: "Phone",
    type: "phone",
    href: "tel:+970568691617",
  },
];

const salibaLinksAr = [
  {
    label: "لينكدإن",
    type: "linkedin",
    href: "https://www.linkedin.com/in/saliba-rishmawi/",
  },
  {
    label: "GitHub",
    type: "github",
    href: "https://github.com/Saliba-codes",
  },
  {
    label: "السيرة الذاتية",
    type: "cv",
    href: salibaCv,
  },
  {
    label: "البريد الإلكتروني",
    type: "email",
    href: "mailto:rishmawisaliba12@gmail.com",
  },
  {
    label: "الهاتف",
    type: "phone",
    href: "tel:+970568691617",
  },
];

export const teamContent = {
  en: {
    title: "Meet the Team",
    subtitle:
      "The people behind Madar, combining AI, software engineering, and business insight to build smarter management tools.",
    members: [
      {
        name: "Judah Sleibi",
        role: "AI Engineer & Full-Stack Developer",
        description:
          "Leads the technical development of Madar, with a focus on AI-powered features, backend architecture, authentication systems, data workflows, and user experience.",
        initials: "JS",
        image: judahImage,
        links: judahLinksEn,
      },
      {
        name: "Saliba Rishmawi",
        role: "AI & Full-Stack Developer",
        description:
          "Supports Madar's backend and AI direction, bringing experience in computer vision, medical imaging AI, and system-level problem solving.",
        initials: "SR",
        image: salibaImage,
        links: salibaLinksEn,
      },
    ],
  },

  ar: {
    title: "تعرّف على الفريق",
    subtitle:
      "الفريق وراء مدار، يجمع بين الذكاء الاصطناعي وهندسة البرمجيات وفهم الأعمال لبناء أدوات إدارة أكثر ذكاء.",
    members: [
      {
        name: "جودا صليبي",
        role: "مهندس ذكاء اصطناعي ومطوّر Full-Stack",
        description:
          "يقود التطوير التقني لمدار، مع تركيز على ميزات الذكاء الاصطناعي، وبنية الخلفية، وأنظمة المصادقة، وتدفقات البيانات، وتجربة المستخدم.",
        initials: "JS",
        image: judahImage,
        links: judahLinksAr,
      },
      {
        name: "صليبا ريشماوي",
        role: "مطوّر ذكاء اصطناعي وFull-Stack",
        description:
          "يدعم اتجاه مدار في الخلفية والذكاء الاصطناعي، بخبرة في الرؤية الحاسوبية، والذكاء الاصطناعي للتصوير الطبي، وحل المشكلات على مستوى الأنظمة.",
        initials: "SR",
        image: salibaImage,
        links: salibaLinksAr,
      },
    ],
  },
};

export const getTeamContent = (lang = "en") =>
  teamContent[lang === "ar" ? "ar" : "en"];

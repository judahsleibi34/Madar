const copy = {
  en: {
    title: "Privacy Policy",
    updated: "Last updated: July 13, 2026",
    intro:
      "Madar collects the information needed to provide accounts, tenant workspaces, website builder features, contact forms, and support workflows.",
    sections: [
      {
        title: "Information we process",
        body:
          "Account details may include name, email, phone, tenant profile data, website settings, uploaded assets, form submissions, billing selections, and operational logs such as IP address and user agent.",
      },
      {
        title: "How we use information",
        body:
          "We use this data to authenticate users, operate tenant workspaces, publish customer sites, process contact and form submissions, secure the service, troubleshoot issues, and respond to support requests.",
      },
      {
        title: "Cookies and security",
        body:
          "The application uses first-party authentication and CSRF cookies to keep sessions working and protect unsafe requests. Analytics and payment SDK cookies are not currently integrated in the frontend.",
      },
      {
        title: "Third-party services",
        body:
          "The application uses Supabase-backed authentication and data services. Public links may open Instagram, and builder starter content may reference external Unsplash image URLs until replaced by workspace content.",
      },
      {
        title: "Contact",
        body:
          "For privacy or security questions, contact info@madar.com.",
      },
    ],
  },
  ar: {
    title: "سياسة الخصوصية",
    updated: "آخر تحديث: 13 يوليو 2026",
    intro:
      "تجمع مدار المعلومات اللازمة لتوفير الحسابات ومساحات عمل المؤسسات وأدوات بناء المواقع ونماذج التواصل وطلبات الدعم.",
    sections: [
      {
        title: "المعلومات التي نعالجها",
        body:
          "قد تشمل بيانات الحساب الاسم والبريد الإلكتروني ورقم الهاتف وبيانات المؤسسة وإعدادات الموقع والملفات المرفوعة وإجابات النماذج واختيارات الفوترة وسجلات التشغيل مثل عنوان IP ووكيل المستخدم.",
      },
      {
        title: "كيف نستخدم المعلومات",
        body:
          "نستخدم هذه البيانات لتسجيل الدخول وتشغيل مساحات العمل ونشر مواقع العملاء ومعالجة رسائل التواصل وإجابات النماذج وتأمين الخدمة واستكشاف المشكلات والرد على طلبات الدعم.",
      },
      {
        title: "ملفات تعريف الارتباط والأمان",
        body:
          "يستخدم التطبيق ملفات تعريف ارتباط خاصة بالمصادقة وحماية CSRF للحفاظ على الجلسات وحماية الطلبات الحساسة. لا توجد حالياً ملفات تعريف ارتباط من أدوات تحليلات أو حزم دفع مدمجة في الواجهة.",
      },
      {
        title: "الخدمات الخارجية",
        body:
          "يستخدم التطبيق خدمات مصادقة وبيانات مدعومة من Supabase. قد تفتح الروابط العامة إنستغرام، وقد تحتوي قوالب البناء الأولية على روابط صور خارجية من Unsplash إلى أن يستبدلها المستخدم بمحتوى مساحة العمل.",
      },
      {
        title: "التواصل",
        body:
          "لأسئلة الخصوصية أو الأمان، تواصل عبر info@madar.com.",
      },
    ],
  },
};

export default function PrivacyPolicyPage({ lang = "en" }) {
  const currentLang = lang === "ar" ? "ar" : "en";
  const page = copy[currentLang];

  return (
    <main className="privacy-policy-page" dir={currentLang === "ar" ? "rtl" : "ltr"} lang={currentLang}>
      <header className="privacy-policy-hero">
        <p>{page.updated}</p>
        <h1>{page.title}</h1>
        <span>{page.intro}</span>
      </header>

      <div className="privacy-policy-content">
        {page.sections.map((section) => (
          <section className="privacy-policy-section" key={section.title}>
            <h2>{section.title}</h2>
            <p>{section.body}</p>
          </section>
        ))}
      </div>
    </main>
  );
}

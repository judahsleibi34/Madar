const labels = {
  en: {
    core: "Madar",
    one: "Records",
    two: "Users",
    three: "Workflows",
  },
  ar: {
    core: "مدار",
    one: "السجلات",
    two: "المستخدمون",
    three: "سير العمل",
  },
};

export default function OrbitVisual({ lang = "en" }) {
  const t = labels[lang] || labels.en;

  return (
    <div className="orbit-wrapper">
      <div className="center-core">
        <span>{t.core}</span>
      </div>

      <div className="orbit orbit-one">
        <span className="orbit-dot">{t.one}</span>
      </div>

      <div className="orbit orbit-two">
        <span className="orbit-dot">{t.two}</span>
      </div>

      <div className="orbit orbit-three">
        <span className="orbit-dot">{t.three}</span>
      </div>
    </div>
  );
}
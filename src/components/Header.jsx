import LanguageSwitcher from "./LanguageSwitcher";
import logo from "../assets/logo.png";

const navItems = {
  en: [
    { id: "home",     label: "Home" },
    { id: "about",    label: "About Us" },
    { id: "features", label: "Features" },
    { id: "contact",  label: "Contact Us" },
    { id: "pricing",  label: "Plans and Pricing" },
  ],
  ar: [
    { id: "home",     label: "الرئيسية" },
    { id: "about",    label: "من نحن" },
    { id: "features", label: "المميزات" },
    { id: "contact",  label: "تواصل معنا" },
    { id: "pricing",  label: "الخطط والأسعار" },
  ],
};

export default function Header({ lang, onLanguageChange }) {
  const items = navItems[lang];

  return (
    <header className="site-header">
      <div className="brand">
        <img className="logo" src={logo} alt="Madar logo" />
        <h1 className="brand-name">{lang === "ar" ? "مدار" : "Madar"}</h1>
      </div>

      <nav className="nav-menu">
        {items.map((item) => (
          <a key={item.id} href={`#${item.id}`}>
            {item.label}
          </a>
        ))}
      </nav>

      <LanguageSwitcher current={lang} onChange={onLanguageChange} />
    </header>
  );
}
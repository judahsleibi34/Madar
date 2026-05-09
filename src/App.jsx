import { useState } from "react";
import Header from "./components/Header";
import HeroSection from "./components/HeroSection";

export default function App() {
  const [lang, setLang] = useState("en");

  const handleLanguageChange = (code) => {
    setLang(code);
    document.documentElement.lang = code;
    document.documentElement.dir = code === "ar" ? "rtl" : "ltr";
  };

  return (
    <>
      <Header lang={lang} onLanguageChange={handleLanguageChange} />
      <HeroSection lang={lang} />
    </>
  );
}
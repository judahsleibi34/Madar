import { useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Header from "./components/Header";
import HeroSection from "./components/HeroSection";
import AboutSection from "./components/AboutSection";
import ContactPage from "./components/ContactPage";
import Footer from "./components/Footer";
import ScrollToTop from "./components/ScrollToTop";

export default function App() {
  const [lang, setLang] = useState("en");

  const handleLanguageChange = (code) => {
    setLang(code);
    document.documentElement.lang = code;
    document.documentElement.dir = code === "ar" ? "rtl" : "ltr";
  };

  return (
    <BrowserRouter>
      <ScrollToTop />

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          minHeight: "100vh",
        }}
      >
        <Header lang={lang} onLanguageChange={handleLanguageChange} />

        <main style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          <Routes>
            <Route path="/" element={<HeroSection lang={lang} />} />
            <Route path="/about" element={<AboutSection lang={lang} />} />
            <Route path="/contact" element={<ContactPage lang={lang} />} />
          </Routes>
        </main>

        <Footer lang={lang} />
      </div>
    </BrowserRouter>
  );
}
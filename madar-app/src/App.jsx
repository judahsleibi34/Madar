import { useEffect, useState } from "react";
import { Routes, Route, useNavigate } from "react-router-dom";

import Header from "./components/Header";
import HeroSection from "./components/HeroSection";
import AboutSection from "./components/AboutSection";
import ContactPage from "./components/ContactPage";
import Footer from "./components/Footer";
import ScrollToTop from "./components/ScrollToTop";

import LoginPage from "./components/LoginPage";
import SignUpPage from "./components/SignUpPage";
import ForgotPasswordPage from "./components/ForgotPasswordPage";
import PricingPage from "./components/PricingPage";
import ResetPasswordPage from "./components/ResetPasswordPage";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export default function App() {
  const [lang, setLang] = useState("en");
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await fetch(`${API_URL}/user_status`, {
          method: "GET",
          credentials: "include",
        });

        const data = await response.json();
        setIsLoggedIn(data.logged_in === true);
      } catch (error) {
        console.error("Auth check failed:", error);
        setIsLoggedIn(false);
      }
    };

    checkAuth();
  }, []);

  const handleLanguageChange = (code) => {
    setLang(code);
    document.documentElement.lang = code;
    document.documentElement.dir = code === "ar" ? "rtl" : "ltr";
  };

  const handleLoginSuccess = () => {
    setIsLoggedIn(true);
  };

  const handleLogout = async () => {
    try {
      await fetch(`${API_URL}/log_out`, {
        method: "POST",
        credentials: "include",
      });
    } catch (error) {
      console.error("Logout failed:", error);
    } finally {
      setIsLoggedIn(false);
      navigate("/");
    }
  };

  return (
    <>
      <ScrollToTop />

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          minHeight: "100vh",
        }}
      >
        <Header
          lang={lang}
          onLanguageChange={handleLanguageChange}
          isLoggedIn={isLoggedIn}
          onLogout={handleLogout}
        />

        <main style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          <Routes>
            <Route path="/" element={<HeroSection key={lang} lang={lang} />} />
            <Route path="/about" element={<AboutSection key={lang} lang={lang} />} />
            <Route path="/contact" element={<ContactPage key={lang} lang={lang} />} />
            <Route path="/pricing" element={<PricingPage key={lang} lang={lang} />} />
            <Route path="/reset-password" element={<ResetPasswordPage key={lang} lang={lang} />} />

            <Route
              path="/login"
              element={
                <LoginPage key={lang} lang={lang} onLoginSuccess={handleLoginSuccess} />
              }
            />

            <Route path="/signup" element={<SignUpPage key={lang} lang={lang} />} />

            <Route
              path="/forgot-password"
              element={<ForgotPasswordPage key={lang} lang={lang} />}
            />
          </Routes>
        </main>

        <Footer lang={lang} />
      </div>
    </>
  );
}

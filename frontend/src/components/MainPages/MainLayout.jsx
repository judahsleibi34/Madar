import { Outlet } from "react-router-dom";
import Footer from "./Footer";
import Header from "./Header";

export default function MainLayout({
  authChecked,
  isLoggedIn,
  lang,
  onLanguageChange,
  onLogout,
  onThemeModeChange,
  themeMode,
  user,
}) {
  return (
    <>
      <Header
        authChecked={authChecked}
        isLoggedIn={isLoggedIn}
        lang={lang}
        onLanguageChange={onLanguageChange}
        onLogout={onLogout}
        onThemeModeChange={onThemeModeChange}
        themeMode={themeMode}
        user={user}
      />

      <Outlet />

      <Footer lang={lang} />
    </>
  );
}

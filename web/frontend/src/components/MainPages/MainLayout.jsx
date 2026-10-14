import { Outlet } from "react-router-dom";
import Footer from "./Footer";
import Header from "./Header";

export default function MainLayout({
  authChecked,
  isLoggedIn,
  lang,
  onLanguageChange,
  onLogout,
  user,
}) {
  return (
    <div className="public-app-shell">
      <Header
        authChecked={authChecked}
        isLoggedIn={isLoggedIn}
        lang={lang}
        onLanguageChange={onLanguageChange}
        onLogout={onLogout}
        user={user}
      />

      <Outlet />

      <Footer lang={lang} />
    </div>
  );
}

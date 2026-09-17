import { useCallback, useEffect, useState } from "react";
import AuthToast from "../AuthPages/AuthToast";
import { useCommerceI18n } from "../../utils/commerceI18n";

// Kept outside route suspense so completion feedback survives navigation.
export default function CommerceActionToast() {
  const [notifications, setNotifications] = useState([]);
  const { direction } = useCommerceI18n();
  useEffect(() => {
    let nextId = 0;
    const receive = (event) => {
      const notification = { ...event.detail, id: ++nextId };
      setNotifications((current) => [...current, notification]);
    };
    window.addEventListener("madar-commerce-action-toast", receive);
    return () => window.removeEventListener("madar-commerce-action-toast", receive);
  }, []);
  const dismiss = useCallback(() => setNotifications((current) => current.slice(1)), []);
  const notification = notifications[0];
  return <AuthToast key={notification?.id} {...notification} dir={direction} onDismiss={dismiss} />;
}

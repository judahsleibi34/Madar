import { createContext, useContext } from "react";

export const NotificationContext = createContext(null);

export function useNotifications() {
  const value = useContext(NotificationContext);
  if (!value) throw new Error("useNotifications must be used within NotificationProvider");
  return value;
}

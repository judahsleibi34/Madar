import { useEffect } from "react";
import {
  fetchCurrentBackendUser,
  mapBackendUserToBuilderUser,
} from "./PageBuilder.api";

export const useCurrentBuilderUser = (setProject) => {
  useEffect(() => {
    let cancelled = false;

    const syncCurrentUser = async () => {
      try {
        const backendUser = await fetchCurrentBackendUser();

        if (cancelled || !backendUser?.email) return;

        setProject((prev) => {
          const adminRole =
            prev.roles.find((role) => role.name.toLowerCase() === "admin") ||
            prev.roles[0];

          const currentUser = mapBackendUserToBuilderUser(
            backendUser,
            adminRole?.id || ""
          );

          const otherUsers = (prev.users || []).filter((user) => {
            if (user.isCurrentUser) return false;
            if (user.email === "admin@madar.local") return false;
            if (backendUser.email && user.email === backendUser.email) return false;
            if (backendUser.auth_id && user.authId === backendUser.auth_id) return false;
            if (backendUser.id && user.backendUserId === backendUser.id) return false;

            return true;
          });

          return {
            ...prev,
            users: [currentUser, ...otherUsers],
          };
        });
      } catch {
        if (import.meta.env.DEV) {
          console.warn("Could not sync current builder user.");
        }
      }
    };

    syncCurrentUser();

    return () => {
      cancelled = true;
    };
  }, [setProject]);
};

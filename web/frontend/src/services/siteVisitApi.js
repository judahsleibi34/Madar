import { apiFetch, getApiUrl, readApiResponse } from "../utils/apiClient";

export const recordPublicSiteVisit = async (subdomain, surface) => {
  const response = await apiFetch(
    getApiUrl(`/public/sites/${encodeURIComponent(subdomain)}/visits`),
    {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ surface }),
    },
  );
  if (!response.ok) throw new Error("Visit tracking failed");
  return readApiResponse(response);
};

export const fetchSiteVisitMetrics = async () => {
  const response = await apiFetch(getApiUrl("/builder/visit-metrics"), {
    method: "GET",
    cache: "no-store",
  });
  const data = await readApiResponse(response);
  if (!response.ok) throw new Error("Could not load visit metrics");
  return data;
};

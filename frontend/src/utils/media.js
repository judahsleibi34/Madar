const API_URL = import.meta.env.VITE_API_URL || "/api";
const API_BASE_URL = API_URL.replace(/\/+$/, "");

export const resolveMediaUrl = (value) => {
  const source = String(value || "").trim();

  if (!source) return "";

  if (
    source.startsWith("http://") ||
    source.startsWith("https://") ||
    source.startsWith("data:")
  ) {
    return source;
  }

  return source.startsWith("/")
    ? `${API_BASE_URL}${source}`
    : `${API_BASE_URL}/${source}`;
};

export {
  API_URL,
  apiFetch as authFetch,
  getApiUrl,
  readApiError,
  readApiResponse,
} from "../../../../utils/apiClient";

export const getFriendlyExternalError = (detail) => {
  const message = String(detail || "");
  const lowerMessage = message.toLowerCase();

  if (
    lowerMessage.includes("google sheet") ||
    lowerMessage.includes("google returned")
  ) {
    return message.replace(/^Failed to read data:\s*/i, "");
  }

  if (
    lowerMessage.includes("http error 400") ||
    lowerMessage.includes("bad request")
  ) {
    return "The link could not be read. For Google Sheets, share it with anyone who has the link or publish it to the web, then paste the full sheet URL.";
  }

  if (lowerMessage.includes("could not detect data format")) {
    return "The link was reachable, but it does not look like CSV, Excel, JSON, or Google Sheets data.";
  }

  return message || "The external data could not be loaded.";
};

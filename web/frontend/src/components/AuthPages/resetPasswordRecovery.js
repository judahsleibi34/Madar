export const readRecoveryContext = (locationLike = window.location) => {
  const hash = locationLike.hash || "";
  const params = new URLSearchParams(hash.replace(/^#/, ""));
  const query = new URLSearchParams(String(locationLike.search || "").replace(/^\?/, ""));
  const accessToken = params.get("access_token") || query.get("access_token");
  const type = params.get("type") || query.get("type");
  const providerError =
    params.get("error_description") ||
    query.get("error_description") ||
    params.get("error") ||
    query.get("error") ||
    "";

  return {
    accessToken: accessToken && type === "recovery" ? accessToken : null,
    requestToken: query.get("request_token") || "",
    providerError: Boolean(providerError),
  };
};

export const readRecoveryContext = (locationLike = window.location) => {
  const hash = locationLike.hash || "";
  const params = new URLSearchParams(hash.replace("#", ""));
  const accessToken = params.get("access_token");
  const type = params.get("type");
  const query = new URLSearchParams(String(locationLike.search || "").replace(/^\?/, ""));

  return {
    accessToken: accessToken && type === "recovery" ? accessToken : null,
    requestToken: query.get("request_token") || "",
  };
};

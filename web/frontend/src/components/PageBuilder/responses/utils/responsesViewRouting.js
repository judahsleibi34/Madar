const RESPONSE_VIEW_PATTERN = /\/responses\/(completed|incomplete)\/?$/;

export function getResponseView(pathname = "", search = "") {
  const routeView = String(pathname).match(RESPONSE_VIEW_PATTERN)?.[1];
  if (routeView) return routeView;

  return new URLSearchParams(search).get("view") === "incomplete"
    ? "incomplete"
    : "completed";
}

export function getResponseViewPath(pathname = "", view = "completed") {
  const safeView = view === "incomplete" ? "incomplete" : "completed";
  const basePath = String(pathname)
    .replace(/\/(?:completed|incomplete)\/?$/, "")
    .replace(/\/+$/, "");

  return `${basePath}/${safeView}`;
}

export function hasResponseViewPath(pathname = "") {
  return RESPONSE_VIEW_PATTERN.test(String(pathname));
}
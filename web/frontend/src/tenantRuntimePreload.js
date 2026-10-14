import { getBrandedMadarSubdomain } from "./utils/hostedAddress";
import { getStorefrontPrimaryRequest } from "./components/EcommerceStore/storefrontPrimaryRequest";
import {
  loadTranslationBundles,
  TRANSLATION_LANGUAGES,
  TRANSLATION_NAMESPACES,
  translationLanguagesFor,
} from "./i18n/translationBundles";

// Hosted tenant pages otherwise load code in sequence (entry -> tenant entry ->
// route chunk) and only then start their primary read. This module lets the
// entry start the one route chunk the URL needs and that route's primary read
// in parallel with the tenant entry. Rendering, loading and error presentation
// stay with the existing route components, which adopt these in-flight
// requests through their normal fetch functions.

const ROUTE_MODULE_LOADERS = {
  site: () => import("./components/PageBuilder/runtime/TenantSiteRuntime"),
  store: () => import("./components/EcommerceStore/EcommerceStorefront"),
};

const loadedRouteModules = {};
const pendingRouteModules = {};

export const loadTenantRouteModule = (kind) => {
  if (!pendingRouteModules[kind]) {
    pendingRouteModules[kind] = ROUTE_MODULE_LOADERS[kind]().then(
      (module) => {
        loadedRouteModules[kind] = module;
        return module;
      },
      (error) => {
        // Let the route's lazy loader retry exactly as it did before preloading.
        pendingRouteModules[kind] = null;
        throw error;
      },
    );
  }
  return pendingRouteModules[kind];
};

export const getLoadedTenantRouteModule = (kind) => loadedRouteModules[kind] || null;

// Translation namespaces each hosted route renders. Academy and any other
// hosted route keep every namespace in both languages.
export const ROUTE_TRANSLATION_NAMESPACES = {
  site: ["common", "dashboard"],
  store: ["common", "commerce"],
};

let initialTenantTranslations = null;
let primaryReadSettled = null;

// Resolves once the hosted page's primary read has finished (or failed), so
// background work can wait until the page has what it needs to render.
export const whenPrimaryReadSettled = () => (primaryReadSettled || Promise.resolve()).catch(() => {});
let hostedTenantRuntime = null;

const startTenantTranslations = (runtime) => {
  const route = runtime ? (runtime.kind === "store" ? "store" : "site") : null;
  initialTenantTranslations = route
    ? loadTranslationBundles(translationLanguagesFor(readInitialLanguage()), ROUTE_TRANSLATION_NAMESPACES[route])
    : loadTranslationBundles(TRANSLATION_LANGUAGES, TRANSLATION_NAMESPACES);
  initialTenantTranslations.catch(() => {}); // routes load their own namespaces again if this fails
};

export const getInitialTenantTranslations = () =>
  initialTenantTranslations || loadTranslationBundles(TRANSLATION_LANGUAGES, TRANSLATION_NAMESPACES);

export const getHostedTenantRuntime = () => hostedTenantRuntime;

export const getPendingTenantRouteModule = (kind) => pendingRouteModules[kind] || null;

// Values that TenantSiteRuntime's getCleanSubdomain() returns unchanged, so the
// prefetched request targets the same tenant URL the runtime will request.
const CANONICAL_RUNTIME_SUBDOMAIN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
// Form ids that need no URL decoding, so the router's decoded param and the
// runtime's decodePathSegment() both yield this exact value.
const PLAIN_FORM_ID = /^[A-Za-z0-9_-]+$/;
// i18n starts in the stored language only when it is exactly a supported code
// (see getStoredLanguage); the storefront locale follows that language.
const LANGUAGE_STORAGE_KEY = "madar.language";

const readInitialLanguage = () => {
  try {
    return window.localStorage.getItem(LANGUAGE_STORAGE_KEY) === "ar" ? "ar" : "en";
  } catch {
    return "en";
  }
};

// Mirrors the hosted branch of TenantSiteRoutes (react-router paths are
// case-insensitive). Academy routes are not preloaded.
export const detectHostedTenantRuntime = ({ hostname, pathname, search = "" }) => {
  const tenant = getBrandedMadarSubdomain(hostname);
  if (!tenant) return null;
  const path = String(pathname || "/");
  if (/^\/(?:academy|my-learning)(?:\/|$)/i.test(path)) return null;
  if (/^\/shop(?:\/|$)/i.test(path)) {
    const routeTail = path.replace(/^\/shop\/?/i, "");
    return { tenant, kind: "store", routeTail, search };
  }
  const formMatch = path.match(/^\/forms\/([^/]+)\/?$/i);
  if (formMatch) return { tenant, kind: "form", formSegment: formMatch[1] };
  return { tenant, kind: "site" };
};

const prefetchPrimaryRead = (runtime) => {
  if (runtime.kind === "store") {
    // Undecoded or encoded tails are left to the component.
    if (runtime.routeTail.includes("%")) return;
    const request = getStorefrontPrimaryRequest({
      routeTail: runtime.routeTail,
      search: runtime.search,
      locale: readInitialLanguage(),
    });
    // Order confirmations have no shared cache entry to adopt.
    if (request.type === "confirmation") return;
    primaryReadSettled = import("./services/ecommerceApi")
      .then((api) => {
        if (request.type === "product") return api.fetchPublicEcommerceProduct(runtime.tenant, request.slug, request.locale);
        if (request.type === "profile") return api.fetchPublicEcommerceProfile(runtime.tenant);
        return api.fetchPublicEcommerceCatalog(runtime.tenant, request.filters);
      })
      .catch(() => {}); // The storefront owns error presentation.
    return;
  }
  if (!CANONICAL_RUNTIME_SUBDOMAIN.test(runtime.tenant)) return;
  if (runtime.kind === "form" && !PLAIN_FORM_ID.test(runtime.formSegment)) return;
  import("./components/PageBuilder/services/PageBuilder.publicApi")
    .then((api) => {
      if (runtime.kind === "form") api.prefetchPublicForm(runtime.tenant, runtime.formSegment);
      else api.prefetchPublicSiteRuntime(runtime.tenant);
    })
    .catch(() => {}); // The runtime owns error presentation.
};

export const startHostedTenantPreload = (location = window.location) => {
  if (!getBrandedMadarSubdomain(location.hostname)) return;
  const runtime = detectHostedTenantRuntime(location);
  hostedTenantRuntime = runtime;
  // Request order matters under HTTP/1.1 connection limits: the primary read
  // first, then the route's two small translation bundles, then the larger
  // route code graph. The page needs all three before it can render.
  if (runtime) prefetchPrimaryRead(runtime);
  startTenantTranslations(runtime);
  if (runtime) loadTenantRouteModule(runtime.kind === "store" ? "store" : "site").catch(() => {});
};

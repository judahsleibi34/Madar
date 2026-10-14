// Registers every translation namespace in both languages synchronously.
// The portal entry imports this before anything else, and tests load it as a
// setup file, so both keep exactly the resources they always had at startup.
import { registerTranslationBundles } from "./index";

import enCommon from "./locales/en/common.json";
import enAuth from "./locales/en/auth.json";
import enPublic from "./locales/en/public.json";
import enDashboard from "./locales/en/dashboard.json";
import enPageBuilder from "./locales/en/pageBuilder.json";
import enCommerce from "./locales/en/commerce.json";
import enDataAnalysis from "./locales/en/dataAnalysis.json";

import arCommon from "./locales/ar/common.json";
import arAuth from "./locales/ar/auth.json";
import arPublic from "./locales/ar/public.json";
import arDashboard from "./locales/ar/dashboard.json";
import arPageBuilder from "./locales/ar/pageBuilder.json";
import arDataAnalysis from "./locales/ar/dataAnalysis.json";
import arCommerce from "./locales/ar/commerce.json";

registerTranslationBundles({
  en: {
    common: enCommon,
    auth: enAuth,
    public: enPublic,
    dashboard: enDashboard,
    commerce: enCommerce,
    pageBuilder: enPageBuilder,
    dataAnalysis: enDataAnalysis,
  },
  ar: {
    common: arCommon,
    auth: arAuth,
    public: arPublic,
    dashboard: arDashboard,
    commerce: arCommerce,
    pageBuilder: arPageBuilder,
    dataAnalysis: arDataAnalysis,
  },
});

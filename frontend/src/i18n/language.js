import i18n from "i18next";

export const SUPPORTED_LANGUAGES = {
  en: {
    label: "English",
    direction: "ltr",
  },
  ar: {
    label: "العربية",
    direction: "rtl",
  },
};

export function getCurrentLanguage() {
  const activeLanguage = i18n.language?.split("-")[0];

  if (activeLanguage && SUPPORTED_LANGUAGES[activeLanguage]) {
    return activeLanguage;
  }

  const savedLanguage = localStorage.getItem("appLanguage");

  if (savedLanguage && SUPPORTED_LANGUAGES[savedLanguage]) {
    return savedLanguage;
  }

  return "en";
}

export function setAppLanguage(lang) {
  if (!SUPPORTED_LANGUAGES[lang]) {
    return getCurrentLanguage();
  }

  const { direction } = SUPPORTED_LANGUAGES[lang];

  i18n.changeLanguage(lang);
  localStorage.setItem("appLanguage", lang);

  document.documentElement.lang = lang;
  document.documentElement.dir = direction;

  Object.keys(SUPPORTED_LANGUAGES).forEach((code) => {
    document.body.classList.remove(`lang-${code}`);
  });

  document.body.classList.add(`lang-${lang}`);

  return lang;
}

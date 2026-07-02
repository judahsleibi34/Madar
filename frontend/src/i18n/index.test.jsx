import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  LANGUAGE_STORAGE_KEY,
  LanguageProvider,
  appLocales,
  applyDocumentLanguage,
  getStoredLanguage,
  useLanguage,
} from "./index";

function LanguageProbe() {
  const { direction, language, setLanguage, t } = useLanguage();

  return (
    <div>
      <span data-testid="language">{language}</span>
      <span data-testid="direction">{direction}</span>
      <span data-testid="label">{t("sidebar.dashboard")}</span>
      <button type="button" onClick={() => setLanguage("ar")}>
        Arabic
      </button>
      <button type="button" onClick={() => setLanguage("en")}>
        English
      </button>
    </div>
  );
}

describe("i18n language system", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    applyDocumentLanguage("en");
    delete appLocales.en.__testOnly;
    delete appLocales.ar.__testOnly;
  });

  it("falls back to English when an Arabic key is missing", () => {
    appLocales.en.__testOnly = { fallback: "English fallback" };

    render(
      <LanguageProvider>
        <LanguageProbe />
      </LanguageProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Arabic" }));

    function FallbackProbe() {
      const { t } = useLanguage();
      return <span>{t("__testOnly.fallback")}</span>;
    }

    render(
      <LanguageProvider>
        <FallbackProbe />
      </LanguageProvider>,
    );

    expect(screen.getByText("English fallback").textContent).toBe(
      "English fallback",
    );
  });

  it("resets an invalid stored language to English", () => {
    const storage = {
      value: "fr",
      getItem: () => storage.value,
      setItem: (key, value) => {
        if (key === LANGUAGE_STORAGE_KEY) {
          storage.value = value;
        }
      },
    };

    expect(getStoredLanguage(storage)).toBe("en");
    expect(storage.value).toBe("en");
  });

  it("updates document direction for Arabic and English", () => {
    applyDocumentLanguage("ar");

    expect(document.documentElement.lang).toBe("ar");
    expect(document.documentElement.dir).toBe("rtl");
    expect(document.documentElement.classList.contains("is-rtl")).toBe(true);

    applyDocumentLanguage("en");

    expect(document.documentElement.lang).toBe("en");
    expect(document.documentElement.dir).toBe("ltr");
    expect(document.documentElement.classList.contains("is-ltr")).toBe(true);
  });

  it("language switch updates active language", () => {
    render(
      <LanguageProvider>
        <LanguageProbe />
      </LanguageProvider>,
    );

    expect(screen.getByTestId("language").textContent).toBe("en");
    expect(screen.getByTestId("direction").textContent).toBe("ltr");

    fireEvent.click(screen.getByRole("button", { name: "Arabic" }));

    expect(screen.getByTestId("language").textContent).toBe("ar");
    expect(screen.getByTestId("direction").textContent).toBe("rtl");
    expect(screen.getByTestId("label").textContent).toBe(
      "\u0644\u0648\u062D\u0629 \u0627\u0644\u062A\u062D\u0643\u0645",
    );

    fireEvent.click(screen.getByRole("button", { name: "English" }));

    expect(screen.getByTestId("language").textContent).toBe("en");
    expect(screen.getByTestId("direction").textContent).toBe("ltr");
  });
});

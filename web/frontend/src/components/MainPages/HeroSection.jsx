import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Trans, useTranslation } from "react-i18next";

import GradientText from "../Animations/GradientText";
import SplitText from "../Animations/SplitText";

const OrbitVisual = lazy(() => import("./OrbitVisual"));

function canCreateWebGL2Context() {
  try {
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("webgl2", {
      antialias: true,
      alpha: true,
    });

    if (!context) return false;

    context.getExtension("WEBGL_lose_context")?.loseContext();
    return true;
  } catch {
    return false;
  }
}

function OrbitVisualPlaceholder() {
  return (
    <div className="hero-visual-placeholder" aria-hidden="true">
      <span className="hero-visual-placeholder-core" />
      <span className="hero-visual-placeholder-ring hero-visual-placeholder-ring-one" />
      <span className="hero-visual-placeholder-ring hero-visual-placeholder-ring-two" />
      <span className="hero-visual-placeholder-ring hero-visual-placeholder-ring-three" />
    </div>
  );
}

function LazyOrbitVisual({ lang }) {
  const prefersReducedMotion = useReducedMotion();
  const [shouldLoad, setShouldLoad] = useState(false);
  const [webGLUnavailable, setWebGLUnavailable] = useState(false);
  const handleWebGLUnavailable = useCallback(() => {
    setWebGLUnavailable(true);
  }, []);

  useEffect(() => {
    if (prefersReducedMotion) {
      return undefined;
    }

    const load = () => {
      if (!canCreateWebGL2Context()) {
        setWebGLUnavailable(true);
        return;
      }

      setShouldLoad(true);
    };

    if ("requestIdleCallback" in window) {
      const id = window.requestIdleCallback(load, { timeout: 1500 });
      return () => window.cancelIdleCallback(id);
    }

    const id = window.setTimeout(load, 800);
    return () => window.clearTimeout(id);
  }, [prefersReducedMotion]);

  if (prefersReducedMotion || webGLUnavailable || !shouldLoad) {
    return <OrbitVisualPlaceholder />;
  }

  return (
    <Suspense fallback={<OrbitVisualPlaceholder />}>
      <div className="hero-visual-ready">
        <OrbitVisual lang={lang} onUnavailable={handleWebGLUnavailable} />
      </div>
    </Suspense>
  );
}

export default function HeroSection({ lang }) {
  const { t } = useTranslation("public");
  const isRTL = lang === "ar";

  return (
    <section id="home" className="hero-section" dir={isRTL ? "rtl" : "ltr"}>
      <div className="hero-content">
        <motion.h1
          className="hero-title"
          dir={isRTL ? "rtl" : "ltr"}
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0, ease: [0.25, 0.1, 0.25, 1] }}
        >
          <Trans
            ns="public"
            i18nKey="hero.titleRich"
            components={{
              brand: <GradientText pauseOnHover />,
            }}
          />
        </motion.h1>
        <motion.p
          className="hero-description"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.15, ease: [0.25, 0.1, 0.25, 1] }}
        >
          {isRTL ? (
            <span className="arabic-name">{t("hero.name")}</span>
          ) : (
            <SplitText className="arabic-name">{t("hero.name")}</SplitText>
          )}{" "}
          {t("hero.description")}
        </motion.p>
      </div>
      <motion.div
        className="hero-visual"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.3, ease: [0.25, 0.1, 0.25, 1] }}
      >
        <LazyOrbitVisual lang={lang} />
      </motion.div>
    </section>
  );
}

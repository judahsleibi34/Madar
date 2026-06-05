import { motion } from "framer-motion";
import { Trans, useTranslation } from "react-i18next";

import GradientText from "../Animations/GradientText";
import OrbitVisual from "../Animations/OrbitVisual";
import SplitText from "../Animations/SplitText";

export default function HeroSection({ lang }) {
  const { t } = useTranslation("public");

  return (
    <section id="home" className="hero-section">
      <div className="hero-content">
        <motion.h1
          className="hero-title"
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
          <SplitText className="arabic-name">{t("hero.name")}</SplitText>{" "}
          {t("hero.description")}
        </motion.p>
      </div>
      <motion.div
        className="hero-visual"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.3, ease: [0.25, 0.1, 0.25, 1] }}
      >
        <OrbitVisual lang={lang} />
      </motion.div>
    </section>
  );
}

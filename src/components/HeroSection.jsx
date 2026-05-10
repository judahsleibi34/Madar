import { motion } from "framer-motion";
import OrbitVisual from "./OrbitVisual";

const content = {
  en: {
    title: "Welcome to Madar",
    name: "Madar",
    description: "is an adaptive business management platform designed to help organizations create and manage their own digital systems based on their unique needs.",
  },
  ar: {
    title: "أهلاً بك في مدار",
    name: "مدار",
    description: "منصة إدارة أعمال تكيفية صُممت لمساعدة المؤسسات على إنشاء وإدارة أنظمتها الرقمية الخاصة بناءً على احتياجاتها الفعلية.",
  },
};

export default function HeroSection({ lang }) {
  const t = content[lang];

  return (
    <section id="home" className="hero-section">
      <div className="hero-content">
        <motion.h1
          className="hero-title"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0, ease: [0.25, 0.1, 0.25, 1] }}
        >
          {t.title}
        </motion.h1>
        <motion.p
          className="hero-description"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.15, ease: [0.25, 0.1, 0.25, 1] }}
        >
          <span className="arabic-name">{t.name}</span> {t.description}
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
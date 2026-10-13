// Runs inside the snapshot DOM; static navigation must work without JavaScript.
export function replaceStaticNavigation({ site, lang }) {
  const routes = [
    ["/", "Home", "الرئيسية"],
    ["/course", "Course", "الدورة", "Explore the Course", "اكتشف الدورة"],
    ["/how-it-works", "How It Works", "كيف نعمل", "How EduHope Works", "كيف تعمل إديوهوب"],
    ["/become-an-affiliate", "Become an Affiliate", "برنامج الإحالة", "Apply as an Affiliate", "قدّم طلب الإحالة", "انضم لبرنامج الإحالة"],
    ["/about", "About EduHope", "عن إديوهوب"],
    ["/tuition-support", "Tuition Support", "دعم الرسوم", "Understand the requirements", "تعرّف على الشروط"],
    ["/exchange", "Exchange Programme", "التبادل", "برنامج التبادل"],
    ["/contact", "Contact", "تواصل معنا", "Start your journey", "ابدأ رحلتك"],
    ["/faq", "FAQ", "الأسئلة الشائعة", "Read all FAQs", "اقرأ الأسئلة الشائعة"],
    ["/terms", "Terms", "الشروط"],
    ["/privacy", "Privacy", "الخصوصية"],
    ["/courses", "Open the real course", "افتح الدورة"],
  ];
  for (const button of document.querySelectorAll("button")) {
    const text = button.textContent.trim();
    const path = button.classList.contains("built-site-brand") || button.classList.contains("academy-menu")
      ? "/" : routes.find(([, ...labels]) => labels.includes(text))?.[0];
    if (!path) continue; // Language and form controls are handled by the exporter.
    const anchor = document.createElement("a");
    for (const { name, value } of button.attributes) {
      if (!["type", "aria-expanded", "disabled"].includes(name)) anchor.setAttribute(name, value);
    }
    anchor.href = `${site}${lang === "ar" ? "/ar" : ""}${path === "/" ? "" : path}/`;
    anchor.setAttribute("data-eduhope-static-link", "");
    anchor.innerHTML = button.innerHTML;
    button.replaceWith(anchor);
  }
  if (!document.querySelector("style[data-eduhope-static-navigation]")) {
    const style = document.createElement("style");
    style.setAttribute("data-eduhope-static-navigation", "");
    style.textContent = `a[data-eduhope-static-link]{text-decoration:none;color:inherit;font:inherit;cursor:pointer}
      .built-site-nav a[data-eduhope-static-link]{display:inline-flex;align-items:center;padding:10px 12px;font-weight:850}
      .built-site-nav a[data-eduhope-static-link]:is(:hover,.active){color:var(--madar-red)}
      .built-site-mobile-menu-panel a[data-eduhope-static-link]{display:block;padding:10px 12px}
      .ecommerce-footer-links-grid a[data-eduhope-static-link]{display:block;padding:6px 0}
      a[data-eduhope-static-link]:focus-visible{outline:2px solid currentColor;outline-offset:3px}`;
    document.head.append(style);
  }
}

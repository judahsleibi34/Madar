const contactText = {
  en: {
    title: "Contact Us",
    subtitle:
      "We’d love to hear from you. Send us a message and we’ll get back to you soon.",
    name: "Full Name",
    phone: "Phone Number",
    message: "Issue / Message",
    button: "Send Message",
    infoTitle: "Contact Information",
    emailLabel: "Email",
    phoneLabel: "Phone",
  },
  ar: {
    title: "تواصل معنا",
    subtitle: "يسعدنا سماعك. أرسل لنا رسالة وسنرد عليك قريبًا.",
    name: "الاسم الكامل",
    phone: "رقم الهاتف",
    message: "المشكلة / الرسالة",
    button: "إرسال الرسالة",
    infoTitle: "معلومات التواصل",
    emailLabel: "البريد الإلكتروني",
    phoneLabel: "رقم الهاتف",
  },
};

export default function ContactPage({ lang = "en" }) {
  const t = contactText[lang] || contactText.en;

  return (
    <main className="contact-page">
      <section className="contact-hero">
        <h1>{t.title}</h1>
        <p>{t.subtitle}</p>
      </section>

      <section className="contact-content">
        <form className="contact-form">
          <label>
            {t.name}
            <input type="text" name="name" />
          </label>

          <label>
            {t.phone}
            <input type="tel" name="phone" dir="ltr" />
          </label>

          <label>
            {t.message}
            <textarea name="message" rows="6" />
          </label>

          <button type="submit">{t.button}</button>
        </form>

        <div className="contact-info-card">
          <h2>{t.infoTitle}</h2>

          <div>
            <strong>{t.emailLabel}</strong>
            <p>info@madar.com</p>
          </div>

          <div>
            <strong>{t.phoneLabel}</strong>
            <p dir="ltr" className="phone-number">
              +972 0599203857
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
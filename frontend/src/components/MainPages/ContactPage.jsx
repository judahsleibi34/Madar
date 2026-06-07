import { useState } from "react";

import GradientText from "../Animations/GradientText";

const API_URL = import.meta.env.VITE_API_URL || "/api";

const contactText = {
  en: {
    title: "Contact Us",
    subtitle:
      "We'd love to hear from you. Send us a message and we'll get back to you soon.",
    name: "Full Name",
    phone: "Phone Number",
    message: "Issue / Message",
    button: "Send Message",
    sending: "Sending...",
    success: "Thanks. Your message has been received.",
    error: "Could not send your message. Please check the form and try again.",
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
    sending: "جاري الإرسال...",
    success: "شكرًا لك. تم استلام رسالتك.",
    error: "تعذر إرسال رسالتك. يرجى مراجعة النموذج والمحاولة مرة أخرى.",
    infoTitle: "معلومات التواصل",
    emailLabel: "البريد الإلكتروني",
    phoneLabel: "رقم الهاتف",
  },
};

export default function ContactPage({ lang = "en" }) {
  const t = contactText[lang] || contactText.en;
  const [form, setForm] = useState({ name: "", phone: "", message: "" });
  const [status, setStatus] = useState({ type: "", message: "" });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const updateField = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
    if (status.type) setStatus({ type: "", message: "" });
  };

  const submitContact = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    setStatus({ type: "", message: "" });

    try {
      const response = await fetch(`${API_URL}/public/contact`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name,
          phone: form.phone || null,
          message: form.message,
        }),
      });

      if (!response.ok) {
        throw new Error("Contact request failed");
      }

      setForm({ name: "", phone: "", message: "" });
      setStatus({ type: "success", message: t.success });
    } catch {
      setStatus({ type: "error", message: t.error });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="contact-page">
      <section className="contact-hero">
        <h1>
          <GradientText pauseOnHover>{t.title}</GradientText>
        </h1>
        <p>{t.subtitle}</p>
      </section>

      <section className="contact-content">
        <form className="contact-form" onSubmit={submitContact}>
          <label>
            {t.name}
            <input
              type="text"
              name="name"
              maxLength="120"
              required
              value={form.name}
              onChange={(event) => updateField("name", event.target.value)}
            />
          </label>

          <label>
            {t.phone}
            <input
              type="tel"
              name="phone"
              dir="ltr"
              maxLength="40"
              value={form.phone}
              onChange={(event) => updateField("phone", event.target.value)}
            />
          </label>

          <label>
            {t.message}
            <textarea
              name="message"
              rows="6"
              maxLength="5000"
              required
              value={form.message}
              onChange={(event) => updateField("message", event.target.value)}
            />
          </label>

          {status.message && (
            <p className={`contact-form-status contact-form-status-${status.type}`}>
              {status.message}
            </p>
          )}

          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? t.sending : t.button}
          </button>
        </form>

        <div className="contact-info-card">
          <h2>
            <GradientText pauseOnHover>{t.infoTitle}</GradientText>
          </h2>

          <div>
            <strong>{t.emailLabel}</strong>
            <p>info@madar.com</p>
          </div>

          <div>
            <strong>{t.phoneLabel}</strong>
            <p dir="ltr" className="phone-number">
              +972599203857
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}

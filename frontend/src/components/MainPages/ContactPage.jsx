import { useState } from "react";

import GradientText from "../Animations/GradientText";
import { getContactContent } from "../../content";
import { FormBlock, HeroBlock, SectionBlock } from "../../blocks";
import { postPublicJson, readApiError } from "../../utils/apiClient";

export default function ContactPage({ lang = "en" }) {
  const t = getContactContent(lang);
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
      const { response, data } = await postPublicJson(
        "/public/contact",
        {
          name: form.name,
          phone: form.phone || null,
          message: form.message,
        }
      );

      if (!response.ok) {
        throw new Error(readApiError(data, "Contact request failed"));
      }

      setForm({ name: "", phone: "", message: "" });
      setStatus({ type: "success", message: t.form.success });
    } catch {
      setStatus({ type: "error", message: t.form.error });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="contact-page">
      <HeroBlock className="contact-hero">
        <h1>
          <GradientText pauseOnHover>{t.hero.title}</GradientText>
        </h1>
        <p>{t.hero.subtitle}</p>
      </HeroBlock>

      <SectionBlock className="contact-content">
        <FormBlock className="contact-form" onSubmit={submitContact}>
          <label>
            {t.form.name}
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
            {t.form.phone}
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
            {t.form.message}
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
            {isSubmitting ? t.form.sending : t.form.button}
          </button>
        </FormBlock>

        <div className="contact-info-card">
          <h2>
            <GradientText pauseOnHover>{t.info.title}</GradientText>
          </h2>

          <div>
            <strong>{t.info.emailLabel}</strong>
            <p>{t.info.email}</p>
          </div>

          <div>
            <strong>{t.info.phoneLabel}</strong>
            <p dir="ltr" className="phone-number">
              {t.info.phone}
            </p>
          </div>
        </div>
      </SectionBlock>
    </main>
  );
}

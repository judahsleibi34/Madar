import { useState } from "react";
import { useTranslation } from "react-i18next";

import GradientText from "../Animations/GradientText";
import { FormBlock, HeroBlock, SectionBlock } from "../../blocks";
import { PUBLIC_API_ROUTES } from "../../services/apiRoutes";
import { postPublicJson, readApiErrorCode } from "../../utils/apiClient";

export default function ContactPage({ lang = "en" }) {
  const { t } = useTranslation("public");
  const content = t("contact", { returnObjects: true });
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
        PUBLIC_API_ROUTES.contact,
        {
          name: form.name,
          phone: form.phone || null,
          message: form.message,
        }
      );

      if (!response.ok) {
        const errorCode = readApiErrorCode(data);
        throw new Error(content.form.errors?.[errorCode] || content.form.error);
      }

      setForm({ name: "", phone: "", message: "" });
      setStatus({ type: "success", message: content.form.success });
    } catch (error) {
      setStatus({ type: "error", message: error.message || content.form.error });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="contact-page" dir={lang === "ar" ? "rtl" : "ltr"}>
      <HeroBlock className="contact-hero">
        <h1>
          <GradientText pauseOnHover>{content.hero.title}</GradientText>
        </h1>
        <p>{content.hero.subtitle}</p>
      </HeroBlock>

      <SectionBlock className="contact-content">
        <FormBlock className="contact-form" onSubmit={submitContact}>
          <label>
            {content.form.name}
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
            {content.form.phone}
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
            {content.form.message}
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
            {isSubmitting ? content.form.sending : content.form.button}
          </button>
        </FormBlock>

        <div className="contact-info-card">
          <h2>
            <GradientText pauseOnHover>{content.info.title}</GradientText>
          </h2>

          <div>
            <strong>{content.info.emailLabel}</strong>
            <p>{content.info.email}</p>
          </div>

          <div>
            <strong>{content.info.phoneLabel}</strong>
            <p dir="ltr" className="phone-number">
              {content.info.phone}
            </p>
          </div>
        </div>
      </SectionBlock>
    </main>
  );
}

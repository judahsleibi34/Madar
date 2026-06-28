export const contactContent = {
  en: {
    hero: {
      title: "Contact Us",
      subtitle:
        "We'd love to hear from you. Send us a message and we'll get back to you soon.",
    },
    form: {
      name: "Full Name",
      phone: "Phone Number",
      message: "Issue / Message",
      button: "Send Message",
      sending: "Sending...",
      success: "Thanks. Your message has been received.",
      error: "Could not send your message. Please check the form and try again.",
    },
    info: {
      title: "Contact Information",
      emailLabel: "Email",
      phoneLabel: "Phone",
      email: "info@madar.com",
      phone: "+972599203857",
    },
  },
  ar: {
    hero: {
      title: "تواصل معنا",
      subtitle:
        "يسعدنا سماعك. أرسل لنا رسالة وسنرد عليك قريباً.",
    },
    form: {
      name: "الاسم الكامل",
      phone: "رقم الهاتف",
      message: "المشكلة / الرسالة",
      button: "إرسال الرسالة",
      sending: "جارٍ الإرسال...",
      success: "شكراً لك. تم استلام رسالتك.",
      error:
        "تعذر إرسال رسالتك. يرجى مراجعة النموذج والمحاولة مرة أخرى.",
    },
    info: {
      title: "معلومات التواصل",
      emailLabel: "البريد الإلكتروني",
      phoneLabel: "رقم الهاتف",
      email: "info@madar.com",
      phone: "+972599203857",
    },
  },
};

export const getContactContent = (lang = "en") =>
  contactContent[lang === "ar" ? "ar" : "en"];

export const pageDeleteConfirmContent = {
  en: {
    title: "Delete this page?",
    messageSuffix: "will be removed from this website. This cannot be undone.",
    keepPage: "Keep page",
    cancel: "Cancel",
    deletePage: "Delete page",
    delete: "Delete",
    icon: "!",
  },
  ar: {
    title: "حذف هذه الصفحة؟",
    messageSuffix: "سيتم حذفها من هذا الموقع. لا يمكن التراجع عن هذا الإجراء.",
    keepPage: "إبقاء الصفحة",
    cancel: "إلغاء",
    deletePage: "حذف الصفحة",
    delete: "حذف",
    icon: "!",
  },
};

export const getPageDeleteConfirmContent = (lang = "en") =>
  pageDeleteConfirmContent[lang] || pageDeleteConfirmContent.en;

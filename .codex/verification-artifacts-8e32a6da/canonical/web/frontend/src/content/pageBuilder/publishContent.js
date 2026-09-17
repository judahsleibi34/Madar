const publishContentEn = {
  scope: "Builder site",
  title: "Publish site",
  description:
    "Publish the Builder website and its standalone form links from one place.",
  statusTitle: "Site status",
  projectLabel: "Builder project",
  stateLabel: "Site state",
  lastSavedLabel: "Last saved",
  lastPublishedLabel: "Last published",
  notSaved: "Not saved yet",
  notPublished: "Not published yet",
  noPublicLink: "Configure a website subdomain before sharing the live site.",
  siteNotPublished: "Publish the site to activate its public link.",
  publishSite: "Publish site",
  publishingSite: "Publishing...",
  unpublishSite: "Take site offline",
  unpublishingSite: "Taking site offline...",
  checklistTitle: "Site publish checklist",
  bilingualOptional: " (only for bilingual forms)",
  checklist: {
    pageTitle: "Site page has a title",
    activeForm: "Builder has an active form",
    formTitle: "Active form has a title",
    formQuestion: "Active form has at least one question",
    requiredLabels: "Required form fields have labels",
    bilingualComplete: "Active bilingual form content is complete",
    previewReady: "Public site preview is ready to check",
  },
  publicLinkTitle: "Public site link",
  websiteLabel: "Website",
  copyLink: "Copy link",
  shareWhatsApp: "Share on WhatsApp",
  previewSite: "Preview site",
  publicQrAlt: "QR code preview for public site link",
  qrPreview: "QR preview",
  formLinkTitle: "Live form link",
  formLabel: "Form",
  formPrefix: "Form:",
  untitledForm: "Untitled form",
  shareForm: "Share form",
  previewForm: "Preview form",
  formQrAlt: "QR code preview for live form link",
  formQrPreview: "Form QR preview",
  noFormToShare: "Create and save a form before sharing its live link.",
  noPublishedFormLink: "Configure a workspace address before sharing the live form.",
  formNotPublished: "Publish this saved form to create its live link.",
};

export const publishContent = {
  en: publishContentEn,
  ar: publishContentEn,
};

export function getPublishContent(lang = "en") {
  return publishContent[lang] || publishContent.en;
}

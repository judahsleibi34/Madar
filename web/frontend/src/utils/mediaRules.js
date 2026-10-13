// File rules for owner media slots (match the owner media-list guidelines).
export const MEDIA_RULES = {
  audio: { types: ["audio/mpeg", "audio/wav", "audio/x-wav", "audio/wave"], accept: ".mp3,.wav", maxBytes: 50 * 1024 * 1024 },
  image: { types: ["image/jpeg", "image/png", "image/webp"], accept: ".jpg,.jpeg,.png,.webp", maxBytes: 5 * 1024 * 1024 },
};
// Photo guideline from the media list: landscape, at least 1200 x 900.
export const MIN_PHOTO = { width: 1200, height: 900 };

export function checkMediaFile(kind, file) {
  const rule = MEDIA_RULES[kind];
  if (!file?.size) return "empty";
  if (!rule.types.includes(file.type)) return "type";
  if (file.size > rule.maxBytes) return "size";
  return "";
}


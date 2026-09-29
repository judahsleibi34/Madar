const HTML_TAG_PATTERN = /<\s*\/?\s*[a-z][^>]*>/iu;
const LETTER_PATTERN = /\p{L}/u;
const isUnsupportedControlCharacter = (character) => {
  const code = character.codePointAt(0);
  return code <= 8 || code === 11 || code === 12 || (code >= 14 && code <= 31) || code === 127;
};

export const normalizePlainText = (value = "") =>
  Array.from(String(value)).filter((character) => !isUnsupportedControlCharacter(character)).join("").trim();

export const isPlainText = (value = "") => !HTML_TAG_PATTERN.test(String(value));

export const containsLetter = (value = "") => LETTER_PATTERN.test(normalizePlainText(value));

export const isValidName = (value = "") =>
  containsLetter(value) && isPlainText(value);
